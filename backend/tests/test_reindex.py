import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Document, InterviewQuestion
from app.ingestion.reindex import reindex_all_questions


class FakeVectorStore:
    def __init__(self):
        self.upserted = []

    def upsert_question(self, question_id, text, metadata):
        self.upserted.append((question_id, text, metadata))


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_reindex_upserts_every_persisted_question(db_session):
    document = Document(filename="sample.docx", content_hash="hash1", status="done")
    db_session.add(document)
    db_session.commit()

    q1 = InterviewQuestion(
        document_id=document.id, company="Amazon", role="Backend Engineer",
        round_type="system_design", question="Design a URL shortener.",
        difficulty="medium", source_type="user_reported", extraction_confidence=0.9,
    )
    q2 = InterviewQuestion(
        document_id=document.id, company="Google", role="SRE",
        round_type="behavioral", question="Tell me about a conflict.",
        difficulty="easy", source_type="ai_generated", extraction_confidence=0.99,
    )
    db_session.add_all([q1, q2])
    db_session.commit()

    vector_store = FakeVectorStore()
    count = reindex_all_questions(db=db_session, vector_store=vector_store)

    assert count == 2
    upserted_ids = {item[0] for item in vector_store.upserted}
    assert upserted_ids == {q1.id, q2.id}

    q1_upsert = next(item for item in vector_store.upserted if item[0] == q1.id)
    assert q1_upsert[1] == "Design a URL shortener."
    assert q1_upsert[2] == {
        "company": "Amazon",
        "role": "Backend Engineer",
        "round_type": "system_design",
        "difficulty": "medium",
        "source_type": "user_reported",
        "source_document_id": document.id,
    }


def test_reindex_with_no_questions_returns_zero(db_session):
    vector_store = FakeVectorStore()
    count = reindex_all_questions(db=db_session, vector_store=vector_store)

    assert count == 0
    assert vector_store.upserted == []
