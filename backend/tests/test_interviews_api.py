import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, get_db
from app.db.models import Document, InterviewQuestion
from app.interview.rubric import load_rubric
from app.interview.state_machine import MAX_QUESTIONS
from app.main import app
from tests.auth_helpers import authenticate, create_user


class ScriptedLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, system_prompt, user_prompt):
        if not self.responses:
            raise AssertionError("LLM called more times than expected")
        return self.responses.pop(0)


def no_followup_response(score=4):
    return json.dumps(
        {
            "criteria_scores": {c: score for c in load_rubric("system_design").criteria},
            "strengths": ["Good."],
            "weaknesses": ["Could improve."],
            "feedback": "Solid.",
            "ask_follow_up": False,
            "follow_up_question": None,
        }
    )


def summary_response():
    return json.dumps({"strengths": ["Clear thinker."], "weaknesses": ["Depth."], "recommendations": ["Practice."]})


@pytest.fixture
def client_factory(monkeypatch):
    def make(llm_responses):
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        TestingSession = sessionmaker(bind=engine)
        session = TestingSession()

        user_id = create_user(session).id
        document = Document(user_id=user_id, filename="sample.docx", content_hash="hash", status="done")
        session.add(document)
        session.commit()
        for i in range(MAX_QUESTIONS):
            session.add(
                InterviewQuestion(
                    document_id=document.id, company="Amazon", role="Backend Engineer",
                    round_type="system_design", question=f"System design question {i}",
                    difficulty="medium", source_type="user_reported", extraction_confidence=0.9,
                )
            )
        session.commit()
        session.close()

        def override_get_db():
            db = TestingSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        fake_llm = ScriptedLLM(llm_responses)
        monkeypatch.setattr("app.api.routers.interviews.get_llm_provider", lambda settings: fake_llm)

        client = TestClient(app)
        authenticate(client, user_id)
        return client

    yield make
    app.dependency_overrides.clear()


def test_create_interview_returns_session_and_first_question(client_factory):
    client = client_factory([])
    response = client.post("/api/v1/interviews", json={"company": "Amazon", "role": "Backend Engineer"})

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["status"] == "active"
    assert body["session"]["round_type"] == "system_design"
    assert body["type"] == "message"
    assert body["message"]["role"] == "interviewer"
    assert body["message"]["content"].startswith("System design question")


def test_rejects_unsupported_round_type(client_factory):
    client = client_factory([])
    response = client.post("/api/v1/interviews", json={"round_type": "behavioral"})
    assert response.status_code == 400


def test_full_interview_flow_reaches_a_summary(client_factory):
    responses = [no_followup_response() for _ in range(MAX_QUESTIONS)] + [summary_response()]
    client = client_factory(responses)

    created = client.post("/api/v1/interviews", json={"company": "Amazon"}).json()
    session_id = created["session"]["id"]

    result = None
    for _ in range(MAX_QUESTIONS):
        resp = client.post(f"/api/v1/interviews/{session_id}/answers", json={"answer": "my answer"})
        assert resp.status_code == 200
        result = resp.json()

    assert result["type"] == "summary"
    assert result["summary"]["overall_score"] == pytest.approx(4.0)
    assert result["summary"]["strengths"] == ["Clear thinker."]
    breakdown = result["summary"]["criteria_breakdown"]
    assert set(breakdown.keys()) == set(load_rubric("system_design").criteria)
    assert all(score == pytest.approx(4.0) for score in breakdown.values())

    session_status = client.get(f"/api/v1/interviews/{session_id}").json()
    assert session_status["status"] == "completed"
    assert session_status["current_state"] == "COMPLETED"

    summary = client.get(f"/api/v1/interviews/{session_id}/summary").json()
    assert summary["overall_score"] == pytest.approx(4.0)
    assert summary["criteria_breakdown"] == breakdown

    transcript = client.get(f"/api/v1/interviews/{session_id}/transcript").json()
    assert len(transcript) == MAX_QUESTIONS * 2  # one interviewer + one candidate message per question


def test_summary_404s_before_interview_completes(client_factory):
    client = client_factory([])
    created = client.post("/api/v1/interviews", json={"company": "Amazon"}).json()
    response = client.get(f"/api/v1/interviews/{created['session']['id']}/summary")
    assert response.status_code == 404


def test_answers_to_unknown_session_returns_404(client_factory):
    client = client_factory([])
    response = client.post("/api/v1/interviews/does-not-exist/answers", json={"answer": "hi"})
    assert response.status_code == 404


def test_rejects_empty_answer(client_factory):
    client = client_factory([])
    created = client.post("/api/v1/interviews", json={"company": "Amazon"}).json()
    response = client.post(
        f"/api/v1/interviews/{created['session']['id']}/answers", json={"answer": "   "}
    )
    assert response.status_code == 400


def test_answering_a_completed_session_returns_400(client_factory):
    responses = [no_followup_response() for _ in range(MAX_QUESTIONS)] + [summary_response()]
    client = client_factory(responses)
    created = client.post("/api/v1/interviews", json={"company": "Amazon"}).json()
    session_id = created["session"]["id"]

    for _ in range(MAX_QUESTIONS):
        client.post(f"/api/v1/interviews/{session_id}/answers", json={"answer": "my answer"})

    response = client.post(f"/api/v1/interviews/{session_id}/answers", json={"answer": "one more"})
    assert response.status_code == 400


class ExplodingLLM:
    """Mimics a real provider unreachable at .complete()-time, not construction —
    exactly what OllamaProvider/OpenAIProvider/AnthropicProvider do: none of them
    make a network call until complete() actually runs."""

    def complete(self, system_prompt, user_prompt):
        raise ConnectionError("Connection refused")


def test_answer_returns_503_rather_than_500_when_llm_unreachable(client_factory, monkeypatch):
    client = client_factory([])  # first question comes from a stored question, no LLM call needed
    monkeypatch.setattr("app.api.routers.interviews.get_llm_provider", lambda settings: ExplodingLLM())
    created = client.post("/api/v1/interviews", json={"company": "Amazon"}).json()

    response = client.post(
        f"/api/v1/interviews/{created['session']['id']}/answers", json={"answer": "my answer"}
    )
    assert response.status_code == 503


def test_create_interview_returns_503_when_llm_unreachable_and_no_stored_question(monkeypatch):
    # No questions seeded at all -> start_interview must fall back to
    # generating one via the LLM, which is where the unreachable provider
    # actually surfaces (get_llm_provider() itself never raises).
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("app.api.routers.interviews.get_llm_provider", lambda settings: ExplodingLLM())

    try:
        client = TestClient(app)
        authenticate(client, create_user(TestingSession()).id)
        response = client.post("/api/v1/interviews", json={"company": "BrandNewCo"})
        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_list_interviews_is_empty_when_none_started(client_factory):
    client = client_factory([])
    assert client.get("/api/v1/interviews").json() == []


def test_list_interviews_shows_most_recent_first_with_score_once_completed(client_factory):
    responses = [no_followup_response() for _ in range(MAX_QUESTIONS)] + [summary_response()]
    client = client_factory(responses)

    first = client.post("/api/v1/interviews", json={"company": "Amazon"}).json()
    second = client.post("/api/v1/interviews", json={"company": "Amazon"}).json()

    for _ in range(MAX_QUESTIONS):
        client.post(f"/api/v1/interviews/{first['session']['id']}/answers", json={"answer": "a"})

    history = client.get("/api/v1/interviews").json()
    assert [s["id"] for s in history] == [second["session"]["id"], first["session"]["id"]]

    completed_entry = next(s for s in history if s["id"] == first["session"]["id"])
    assert completed_entry["status"] == "completed"
    assert completed_entry["overall_score"] == pytest.approx(4.0)

    active_entry = next(s for s in history if s["id"] == second["session"]["id"])
    assert active_entry["status"] == "active"
    assert active_entry["overall_score"] is None
