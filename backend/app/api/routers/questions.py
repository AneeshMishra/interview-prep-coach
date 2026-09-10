"""
GET /questions — company/role/round filtered + optional semantic search.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import InterviewQuestion
from app.retrieval.vector_store import get_vector_store

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("")
def search_questions(
    company: str | None = Query(default=None),
    role: str | None = Query(default=None),
    round_type: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    query: str | None = Query(default=None, description="Free-text semantic search"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if query:
        return _semantic_search(db, query, company, role, round_type, difficulty, limit)

    db_query = db.query(InterviewQuestion)
    if company:
        db_query = db_query.filter(InterviewQuestion.company.ilike(f"%{company}%"))
    if role:
        db_query = db_query.filter(InterviewQuestion.role.ilike(f"%{role}%"))
    if round_type:
        db_query = db_query.filter(InterviewQuestion.round_type == round_type)
    if difficulty:
        db_query = db_query.filter(InterviewQuestion.difficulty == difficulty)

    return db_query.limit(limit).all()


def _semantic_search(
    db: Session,
    query: str,
    company: str | None,
    role: str | None,
    round_type: str | None,
    difficulty: str | None,
    limit: int,
):
    try:
        vector_store = get_vector_store()
        hits = vector_store.search(
            query=query, company=company, role=role, round_type=round_type, limit=limit
        )
    except Exception as exc:  # noqa: BLE001 - Qdrant unreachable, degrade explicitly
        raise HTTPException(status_code=503, detail="Semantic search is unavailable.") from exc

    if not hits:
        return []

    scores = {hit.question_id: hit.score for hit in hits}
    rows = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.id.in_(scores.keys()))
        .all()
    )
    if difficulty:
        rows = [row for row in rows if row.difficulty == difficulty]

    rows.sort(key=lambda row: scores.get(row.id, 0.0), reverse=True)
    return rows


@router.get("/{question_id}")
def get_question(question_id: str, db: Session = Depends(get_db)):
    return db.query(InterviewQuestion).filter(InterviewQuestion.id == question_id).first()
