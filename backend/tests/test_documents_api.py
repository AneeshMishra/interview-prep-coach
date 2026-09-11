import json

import docx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db.base import Base, get_db
from app.main import app


class FakeLLM:
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            [
                {
                    "company": "Amazon",
                    "role": "Backend Engineer",
                    "round_type": "system_design",
                    "question": "Design a URL shortener.",
                    "answer_notes": None,
                    "difficulty": "medium",
                    "tags": ["scaling"],
                    "source_type": "user_reported",
                    "source_section": None,
                    "extraction_confidence": 0.9,
                }
            ]
        )


class FakeVectorStore:
    def __init__(self):
        self.upserted = []

    def upsert_question(self, question_id, text, metadata):
        self.upserted.append((question_id, text, metadata))

    def search(self, query, company=None, role=None, round_type=None, limit=20):
        return []


def make_docx_bytes(tmp_path):
    document = docx.Document()
    document.add_heading("Amazon - Backend Engineer", level=1)
    document.add_paragraph("Round 2: Design a URL shortener.")
    path = tmp_path / "sample.docx"
    document.save(path)
    return path.read_bytes()


def make_client(tmp_path, monkeypatch):
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

    fake_vector_store = FakeVectorStore()
    monkeypatch.setattr("app.ingestion.pipeline.get_llm_provider", lambda settings: FakeLLM())
    monkeypatch.setattr("app.ingestion.pipeline.get_vector_store", lambda: fake_vector_store)

    client = TestClient(app)
    return client, fake_vector_store


def test_upload_ingests_and_questions_are_searchable(tmp_path, monkeypatch):
    client, fake_vector_store = make_client(tmp_path, monkeypatch)
    try:
        file_bytes = make_docx_bytes(tmp_path)

        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("sample.docx", file_bytes, "application/octet-stream")},
        )
        assert response.status_code == 200
        body = response.json()
        document_id = body["document_id"]

        docs = client.get("/api/v1/documents").json()
        assert docs[0]["id"] == document_id
        assert docs[0]["status"] == "done"

        questions = client.get("/api/v1/questions", params={"company": "Amazon"}).json()
        assert len(questions) == 1
        assert questions[0]["question"] == "Design a URL shortener."
        assert questions[0]["tags"] == ["scaling"]

        assert len(fake_vector_store.upserted) == 1
    finally:
        app.dependency_overrides.clear()


def test_duplicate_upload_is_detected_by_content_hash(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    try:
        file_bytes = make_docx_bytes(tmp_path)

        first = client.post(
            "/api/v1/documents/upload",
            files={"file": ("sample.docx", file_bytes, "application/octet-stream")},
        ).json()
        second = client.post(
            "/api/v1/documents/upload",
            files={"file": ("sample.docx", file_bytes, "application/octet-stream")},
        ).json()

        assert second["status"] == "duplicate"
        assert second["document_id"] == first["document_id"]
    finally:
        app.dependency_overrides.clear()


def test_rejects_non_docx_upload(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    try:
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("sample.txt", b"not a docx", "text/plain")},
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_rejects_upload_over_size_limit(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    app.dependency_overrides[get_settings] = lambda: Settings(max_upload_size_bytes=10)
    try:
        file_bytes = make_docx_bytes(tmp_path)
        assert len(file_bytes) > 10

        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("sample.docx", file_bytes, "application/octet-stream")},
        )
        assert response.status_code == 413

        assert client.get("/api/v1/documents").json() == []
    finally:
        app.dependency_overrides.clear()


def test_upload_sanitizes_path_traversal_filename(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    try:
        file_bytes = make_docx_bytes(tmp_path)

        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("../../etc/passwd.docx", file_bytes, "application/octet-stream")},
        )
        assert response.status_code == 200

        docs = client.get("/api/v1/documents").json()
        assert docs[0]["filename"] == "passwd.docx"
    finally:
        app.dependency_overrides.clear()
