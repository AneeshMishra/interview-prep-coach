"""
GET /questions — company/role/round filtered + optional semantic search.

Also surfaces the extraction-confidence review flag (docs/architecture.md
P1-007): records the LLM structuring pass wasn't confident about are
flagged via needs_review so they're not silently trusted as fact.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.base import get_db
from app.db.models import InterviewQuestion
from app.retrieval.vector_store import get_vector_store

router = APIRouter(prefix="/questions", tags=["questions"])


def _needs_review(question: InterviewQuestion, threshold: float) -> bool:
    # Unknown confidence is treated as low confidence — it can't be
    # verified, so it shouldn't be trusted outright either.
    return question.extraction_confidence is None or question.extraction_confidence < threshold


def _serialize(question: InterviewQuestion, threshold: float) -> dict:
    return {
        "id": question.id,
        "document_id": question.document_id,
        "company": question.company,
        "role": question.role,
        "round_type": question.round_type,
        "question": question.question,
        "answer_notes": question.answer_notes,
        "difficulty": question.difficulty,
        "source_type": question.source_type,
        "source_section": question.source_section,
        "extraction_confidence": question.extraction_confidence,
        "needs_review": _needs_review(question, threshold),
        "tags": [t.tag for t in question.tags],
        "created_at": question.created_at,
    }


@router.get("")
def search_questions(
    company: str | None = Query(default=None),
    role: str | None = Query(default=None),
    round_type: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    needs_review: bool | None = Query(
        default=None, description="Filter to low-confidence extractions flagged for review"
    ),
    query: str | None = Query(default=None, description="Free-text semantic search"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if query:
        rows = _semantic_search(db, query, company, role, round_type, difficulty, limit)
    else:
        db_query = db.query(InterviewQuestion)
        if company:
            db_query = db_query.filter(InterviewQuestion.company.ilike(f"%{company}%"))
        if role:
            db_query = db_query.filter(InterviewQuestion.role.ilike(f"%{role}%"))
        if round_type:
            db_query = db_query.filter(InterviewQuestion.round_type == round_type)
        if difficulty:
            db_query = db_query.filter(InterviewQuestion.difficulty == difficulty)
        if needs_review is True:
            db_query = db_query.filter(
                or_(
                    InterviewQuestion.extraction_confidence.is_(None),
                    InterviewQuestion.extraction_confidence < settings.low_confidence_threshold,
                )
            )
        elif needs_review is False:
            db_query = db_query.filter(
                InterviewQuestion.extraction_confidence.is_not(None),
                InterviewQuestion.extraction_confidence >= settings.low_confidence_threshold,
            )
        rows = db_query.limit(limit).all()

    if query and needs_review is not None:
        rows = [row for row in rows if _needs_review(row, settings.low_confidence_threshold) == needs_review]

    return [_serialize(row, settings.low_confidence_threshold) for row in rows]


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
def get_question(
    question_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    question = db.query(InterviewQuestion).filter(InterviewQuestion.id == question_id).first()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    return _serialize(question, settings.low_confidence_threshold)
