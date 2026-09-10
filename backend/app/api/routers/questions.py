"""
GET /questions — company/role/round filtered + optional semantic search.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import InterviewQuestion

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("")
def search_questions(
    company: str | None = Query(default=None),
    role: str | None = Query(default=None),
    round_type: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(InterviewQuestion)
    if company:
        query = query.filter(InterviewQuestion.company.ilike(f"%{company}%"))
    if role:
        query = query.filter(InterviewQuestion.role.ilike(f"%{role}%"))
    if round_type:
        query = query.filter(InterviewQuestion.round_type == round_type)
    if difficulty:
        query = query.filter(InterviewQuestion.difficulty == difficulty)

    return query.limit(limit).all()

    # NOTE: semantic (free-text) search via VectorStore.search() combines with
    # these same filters — wired in once the ingestion pipeline populates Qdrant.


@router.get("/{question_id}")
def get_question(question_id: str, db: Session = Depends(get_db)):
    return db.query(InterviewQuestion).filter(InterviewQuestion.id == question_id).first()
