"""Regression tests for the core property multi-user support exists to
guarantee: one user can never read, list, or retrieve-against another
user's documents, questions, chat sessions or interview sessions."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, get_db
from app.db.models import Document, InterviewQuestion
from app.main import app
from tests.auth_helpers import authenticate, create_user


@pytest.fixture
def two_users_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    alice_id = create_user(session, email="alice@example.com").id
    bob_id = create_user(session, email="bob@example.com").id

    alice_doc = Document(user_id=alice_id, filename="alice.docx", content_hash="hash-alice", status="done")
    session.add(alice_doc)
    session.commit()
    alice_question = InterviewQuestion(
        document_id=alice_doc.id,
        company="Amazon",
        role="Backend Engineer",
        round_type="system_design",
        question="Alice's private question.",
        difficulty="medium",
        source_type="user_reported",
        extraction_confidence=0.9,
    )
    session.add(alice_question)
    session.commit()
    alice_document_id, alice_question_id = alice_doc.id, alice_question.id
    session.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    yield client, alice_id, bob_id, alice_document_id, alice_question_id
    app.dependency_overrides.clear()


def test_two_users_uploading_identical_content_are_not_treated_as_duplicates(two_users_client):
    """content_hash dedup is per-user now (see the 8a1c7e4f2b3d migration) —
    two different users uploading the same file content get independent
    documents, not a "duplicate" collision."""
    client, alice_id, bob_id, _, _ = two_users_client

    authenticate(client, alice_id)
    alice_upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("same.docx", b"identical bytes", "application/octet-stream")},
    ).json()
    assert alice_upload["status"] == "pending"

    authenticate(client, bob_id)
    bob_upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("same.docx", b"identical bytes", "application/octet-stream")},
    ).json()
    assert bob_upload["status"] == "pending"
    assert bob_upload["document_id"] != alice_upload["document_id"]


def test_document_list_only_shows_the_signed_in_users_documents(two_users_client):
    client, alice_id, bob_id, _, _ = two_users_client

    authenticate(client, alice_id)
    assert len(client.get("/api/v1/documents").json()) == 1

    authenticate(client, bob_id)
    assert client.get("/api/v1/documents").json() == []


def test_question_list_excludes_other_users_questions(two_users_client):
    client, alice_id, bob_id, _, _ = two_users_client

    authenticate(client, bob_id)
    assert client.get("/api/v1/questions").json() == []

    authenticate(client, alice_id)
    questions = client.get("/api/v1/questions").json()
    assert len(questions) == 1
    assert questions[0]["question"] == "Alice's private question."


def test_get_question_by_id_404s_for_a_different_user(two_users_client):
    client, alice_id, bob_id, _, alice_question_id = two_users_client

    authenticate(client, alice_id)
    assert client.get(f"/api/v1/questions/{alice_question_id}").status_code == 200

    authenticate(client, bob_id)
    assert client.get(f"/api/v1/questions/{alice_question_id}").status_code == 404


def test_chat_session_is_not_reachable_by_a_different_user(two_users_client):
    client, alice_id, bob_id, _, _ = two_users_client

    authenticate(client, alice_id)
    session = client.post("/api/v1/chat/sessions").json()

    authenticate(client, bob_id)
    response = client.get(f"/api/v1/chat/sessions/{session['id']}/messages")
    assert response.status_code == 404


def test_interview_session_is_not_reachable_by_a_different_user(two_users_client, monkeypatch):
    client, alice_id, bob_id, _, _ = two_users_client

    class ScriptedLLM:
        def complete(self, system_prompt, user_prompt):
            raise AssertionError("A stored question exists — the LLM should not be called")

    monkeypatch.setattr("app.api.routers.interviews.get_llm_provider", lambda settings: ScriptedLLM())

    authenticate(client, alice_id)
    created = client.post("/api/v1/interviews", json={"company": "Amazon"}).json()
    session_id = created["session"]["id"]
    # Alice's interview opens with her own stored question, not an LLM fallback.
    assert created["message"]["content"] == "Alice's private question."

    authenticate(client, bob_id)
    assert client.get(f"/api/v1/interviews/{session_id}").status_code == 404
    assert client.get(f"/api/v1/interviews/{session_id}/transcript").status_code == 404
    assert client.post(f"/api/v1/interviews/{session_id}/answers", json={"answer": "hi"}).status_code == 404


def test_interview_never_asks_another_users_stored_question(two_users_client, monkeypatch):
    """_pick_next_question (state_machine.py) must scope by user_id — Bob
    starting a mock interview must never surface Alice's uploaded question."""
    client, alice_id, bob_id, _, _ = two_users_client

    class OpeningLLM:
        def complete(self, system_prompt, user_prompt):
            return "Bob gets an LLM-generated opener since he has no questions of his own."

    monkeypatch.setattr("app.api.routers.interviews.get_llm_provider", lambda settings: OpeningLLM())

    authenticate(client, bob_id)
    created = client.post("/api/v1/interviews", json={"company": "Amazon"}).json()
    assert created["message"]["content"] != "Alice's private question."
    assert created["message"]["question_id"] is None
