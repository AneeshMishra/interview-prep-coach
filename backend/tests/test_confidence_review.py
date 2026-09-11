import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db.base import Base, get_db
from app.db.models import Document, InterviewQuestion
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    session = TestingSession()
    document = Document(filename="sample.docx", content_hash="hash", status="done")
    session.add(document)
    session.commit()

    def make_question(question_text: str, confidence: float | None) -> InterviewQuestion:
        question = InterviewQuestion(
            document_id=document.id,
            company="Amazon",
            role="Backend Engineer",
            round_type="system_design",
            question=question_text,
            extraction_confidence=confidence,
        )
        session.add(question)
        session.commit()
        return question

    high_id = make_question("Design a URL shortener.", 0.95).id
    low_id = make_question("Design something vague.", 0.4).id

    # The ORM's column default (1.0) fires even for an explicit None, so a
    # genuine NULL confidence — the legacy/hand-edited-row case the code
    # guards against — has to be forced in with raw SQL.
    unknown_id = make_question("Unclear extraction.", 0.5).id
    session.execute(
        text("UPDATE interview_questions SET extraction_confidence = NULL WHERE id = :id"),
        {"id": unknown_id},
    )
    session.commit()
    session.close()

    test_client = TestClient(app)
    yield test_client, high_id, low_id, unknown_id

    app.dependency_overrides.clear()


def test_low_and_unknown_confidence_are_flagged_for_review(client):
    test_client, high_id, low_id, unknown_id = client

    high = test_client.get(f"/api/v1/questions/{high_id}").json()
    low = test_client.get(f"/api/v1/questions/{low_id}").json()
    unknown = test_client.get(f"/api/v1/questions/{unknown_id}").json()

    assert high["needs_review"] is False
    assert low["needs_review"] is True
    assert unknown["needs_review"] is True


def test_needs_review_filter_returns_only_flagged_questions(client):
    test_client, high_id, low_id, unknown_id = client

    flagged = test_client.get("/api/v1/questions", params={"needs_review": True}).json()
    flagged_ids = {q["id"] for q in flagged}
    assert flagged_ids == {low_id, unknown_id}

    clean = test_client.get("/api/v1/questions", params={"needs_review": False}).json()
    clean_ids = {q["id"] for q in clean}
    assert clean_ids == {high_id}


def test_threshold_is_configurable(client):
    test_client, high_id, low_id, unknown_id = client

    # Raise the bar so even the 0.95-confidence question gets flagged.
    app.dependency_overrides[get_settings] = lambda: Settings(low_confidence_threshold=0.99)
    try:
        flagged = test_client.get("/api/v1/questions", params={"needs_review": True}).json()
        flagged_ids = {q["id"] for q in flagged}
        assert flagged_ids == {high_id, low_id, unknown_id}
    finally:
        del app.dependency_overrides[get_settings]


def test_unknown_question_id_returns_404(client):
    test_client, *_ = client
    response = test_client.get("/api/v1/questions/does-not-exist")
    assert response.status_code == 404
