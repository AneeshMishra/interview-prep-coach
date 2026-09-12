"""
Rebuild the Qdrant index from the relational database.

ADR-002 (docs/architecture.md) and CLAUDE.md are explicit that Qdrant is a
retrieval index, not the source of truth, and must be reconstructable from
the relational DB alone — e.g. after wiping its volume, moving to a new
Qdrant instance, or switching the embedding model. This is that rebuild.

Usage:
    cd backend && python -m app.ingestion.reindex
"""
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.models import InterviewQuestion
from app.ingestion.pipeline import question_qdrant_metadata
from app.retrieval.vector_store import VectorStore, get_vector_store


def reindex_all_questions(db: Session | None = None, vector_store: VectorStore | None = None) -> int:
    """Clear the collection and upsert every persisted question into Qdrant.
    Returns the count reindexed."""
    vector_store = vector_store or get_vector_store()
    vector_store.clear()
    owns_session = db is None
    db = db or SessionLocal()
    try:
        questions = db.query(InterviewQuestion).all()
        for question in questions:
            vector_store.upsert_question(
                question_id=question.id,
                text=question.question,
                metadata=question_qdrant_metadata(question),
            )
        return len(questions)
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    count = reindex_all_questions()
    print(f"Reindexed {count} question(s) into Qdrant.")
