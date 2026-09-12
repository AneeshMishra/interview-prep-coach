import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, get_db
from app.db.models import Document, InterviewQuestion
from app.main import app


class FakeLLM:
    def __init__(self, response):
        self.response = response

    def complete(self, system_prompt, user_prompt):
        return self.response


class FakeVectorStore:
    def __init__(self, hit_ids):
        self.hit_ids = hit_ids
        self.searched_with = None

    def search(self, query, company=None, role=None, round_type=None, limit=20):
        self.searched_with = query

        class Hit:
            def __init__(self, question_id):
                self.question_id = question_id
                self.score = 0.9

        return [Hit(qid) for qid in self.hit_ids]


@pytest.fixture
def client_factory(tmp_path, monkeypatch):
    def make(hit_ids, llm_response):
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        TestingSession = sessionmaker(bind=engine)
        session = TestingSession()

        document = Document(filename="sample.docx", content_hash="hash", status="done")
        session.add(document)
        session.commit()

        question = InterviewQuestion(
            document_id=document.id,
            company="Nagarro",
            role="Backend Engineer",
            round_type="technical",
            question="What is a virtual thread in Java?",
            answer_notes="JVM-scheduled, not OS-scheduled.",
            difficulty="medium",
            source_type="user_reported",
            extraction_confidence=0.9,
        )
        session.add(question)
        session.commit()
        question_id = question.id
        session.close()

        def override_get_db():
            db = TestingSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        fake_vector_store = FakeVectorStore(hit_ids or [question_id])
        fake_llm = FakeLLM(llm_response)
        monkeypatch.setattr("app.api.routers.chat.get_vector_store", lambda: fake_vector_store)
        monkeypatch.setattr("app.api.routers.chat.get_llm_provider", lambda settings: fake_llm)

        return TestClient(app), question_id, fake_vector_store, fake_llm

    yield make
    app.dependency_overrides.clear()


def test_create_session_and_send_message_returns_grounded_answer(client_factory):
    client, question_id, fake_vector_store, _fake_llm = client_factory(
        None, json.dumps({"answer": "Virtual threads are JVM-scheduled.", "cited_question_ids": []})
    )
    session = client.post("/api/v1/chat/sessions").json()
    assert "id" in session
    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages", json={"message": "What is a virtual thread?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "assistant"
    assert body["content"] == "Virtual threads are JVM-scheduled."
    assert fake_vector_store.searched_with == "What is a virtual thread?"

    history = client.get(f"/api/v1/chat/sessions/{session['id']}/messages").json()
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[0]["content"] == "What is a virtual thread?"


def test_citation_is_included_when_llm_cites_a_real_question_id(client_factory):
    client, question_id, _fake_vector_store, fake_llm = client_factory(None, "{}")
    # Now that we know the real (freshly generated) question id for this
    # client's database, bake it into the fake LLM's response.
    fake_llm.response = json.dumps(
        {"answer": "See the cited question.", "cited_question_ids": [question_id]}
    )

    session = client.post("/api/v1/chat/sessions").json()
    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages", json={"message": "virtual threads?"}
    )
    assert response.json()["cited_question_ids"] == [question_id]


def test_send_message_to_unknown_session_returns_404(client_factory):
    client, _, _, _ = client_factory(None, "{}")
    response = client.post("/api/v1/chat/sessions/does-not-exist/messages", json={"message": "hi"})
    assert response.status_code == 404


def test_rejects_empty_message(client_factory):
    client, _, _, _ = client_factory(None, "{}")
    session = client.post("/api/v1/chat/sessions").json()
    response = client.post(f"/api/v1/chat/sessions/{session['id']}/messages", json={"message": "   "})
    assert response.status_code == 400


def test_multi_turn_conversation_increments_sequence(client_factory):
    client, _, _, _ = client_factory(
        None, json.dumps({"answer": "ok", "cited_question_ids": []})
    )
    session = client.post("/api/v1/chat/sessions").json()

    client.post(f"/api/v1/chat/sessions/{session['id']}/messages", json={"message": "first"})
    client.post(f"/api/v1/chat/sessions/{session['id']}/messages", json={"message": "second"})

    history = client.get(f"/api/v1/chat/sessions/{session['id']}/messages").json()
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    assert [m["content"] for m in history if m["role"] == "user"] == ["first", "second"]


def test_no_matching_candidates_gives_a_plain_no_results_answer_without_calling_llm(tmp_path, monkeypatch):
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

    class NoHitsVectorStore:
        def search(self, query, company=None, role=None, round_type=None, limit=20):
            return []

    class ExplodingLLM:
        def complete(self, system_prompt, user_prompt):
            raise AssertionError("LLM should not be called when there are no candidates")

    monkeypatch.setattr("app.api.routers.chat.get_vector_store", lambda: NoHitsVectorStore())
    monkeypatch.setattr("app.api.routers.chat.get_llm_provider", lambda settings: ExplodingLLM())

    try:
        client = TestClient(app)
        session = client.post("/api/v1/chat/sessions").json()
        response = client.post(
            f"/api/v1/chat/sessions/{session['id']}/messages", json={"message": "anything"}
        )
        assert response.status_code == 200
        assert "couldn't find anything relevant" in response.json()["content"].lower()
    finally:
        app.dependency_overrides.clear()


def test_vector_store_failure_returns_503(tmp_path, monkeypatch):
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

    class BrokenVectorStore:
        def search(self, *args, **kwargs):
            raise RuntimeError("qdrant unreachable")

    monkeypatch.setattr("app.api.routers.chat.get_vector_store", lambda: BrokenVectorStore())

    try:
        client = TestClient(app)
        session = client.post("/api/v1/chat/sessions").json()
        response = client.post(
            f"/api/v1/chat/sessions/{session['id']}/messages", json={"message": "anything"}
        )
        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()
