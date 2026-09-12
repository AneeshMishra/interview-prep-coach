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

        document = Document(filename="sample.docx", content_hash="hash", status="done")
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

        return TestClient(app)

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

    session_status = client.get(f"/api/v1/interviews/{session_id}").json()
    assert session_status["status"] == "completed"
    assert session_status["current_state"] == "COMPLETED"

    summary = client.get(f"/api/v1/interviews/{session_id}/summary").json()
    assert summary["overall_score"] == pytest.approx(4.0)

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
