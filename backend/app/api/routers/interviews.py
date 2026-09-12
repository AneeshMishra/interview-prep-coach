"""
POST /interviews — start a mock interview session.
POST /interviews/{session_id}/answers — submit an answer, get the next
    question/follow-up, or (once the session ends) the final summary.
GET  /interviews/{session_id} — session status.
GET  /interviews/{session_id}/transcript — full message history.
GET  /interviews/{session_id}/summary — final summary (404 until COMPLETED).

The mock interview is a deterministic state machine (app/interview/
state_machine.py), not the RAG search chat in app/api/routers/chat.py.
V1 supports the system_design round only (ADR-007) — the only rubric
shipped (app/rubrics/system_design.yaml).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.base import get_db
from app.db.models import InterviewSession, InterviewSummary
from app.interview.rubric import load_rubric
from app.interview.state_machine import (
    ROUND_TYPE,
    AskedQuestion,
    InterviewCompleted,
    InterviewNotActiveError,
    start_interview,
    submit_answer,
)
from app.llm_providers.factory import get_llm_provider

router = APIRouter(prefix="/interviews", tags=["interviews"])


class StartInterviewRequest(BaseModel):
    company: str | None = None
    role: str | None = None
    round_type: str = ROUND_TYPE


class SubmitAnswerRequest(BaseModel):
    answer: str


def _serialize_message(message) -> dict:
    return {
        "id": message.id,
        "session_id": message.session_id,
        "sequence_no": message.sequence_no,
        "role": message.role,
        "content": message.content,
        "question_id": message.question_id,
        "created_at": message.created_at,
    }


def _serialize_summary(summary: InterviewSummary) -> dict:
    return {
        "session_id": summary.session_id,
        "overall_score": summary.overall_score,
        "strengths": summary.strengths_json or [],
        "weaknesses": summary.weaknesses_json or [],
        "recommendations": summary.recommendations_json or [],
        "created_at": summary.created_at,
    }


def _serialize_session(session: InterviewSession) -> dict:
    return {
        "id": session.id,
        "company": session.company,
        "role": session.role,
        "round_type": session.round_type,
        "status": session.status,
        "current_state": session.current_state,
        "rubric_version": session.rubric_version,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
    }


def _get_session_or_404(session_id: str, db: Session) -> InterviewSession:
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    return session


def _result_response(result: AskedQuestion | InterviewCompleted) -> dict:
    if isinstance(result, InterviewCompleted):
        return {"type": "summary", "summary": _serialize_summary(result.summary)}
    return {"type": "message", "message": _serialize_message(result.message)}


@router.post("")
def create_interview(
    payload: StartInterviewRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if payload.round_type != ROUND_TYPE:
        raise HTTPException(
            status_code=400,
            detail=f"Only the {ROUND_TYPE!r} round is supported in this version.",
        )

    rubric = load_rubric(ROUND_TYPE)
    try:
        llm = get_llm_provider(settings)
    except Exception as exc:  # noqa: BLE001 - LLM unreachable/misconfigured
        raise HTTPException(status_code=503, detail="Could not start the interview right now.") from exc

    result = start_interview(
        db=db,
        llm=llm,
        llm_provider_name=settings.llm_provider,
        llm_model=settings.llm_model,
        rubric=rubric,
        company=payload.company,
        role=payload.role,
    )
    session = db.query(InterviewSession).filter(
        InterviewSession.id == result.message.session_id
    ).first()
    return {"session": _serialize_session(session), **_result_response(result)}


@router.get("/{session_id}")
def get_interview(session_id: str, db: Session = Depends(get_db)):
    return _serialize_session(_get_session_or_404(session_id, db))


@router.get("/{session_id}/transcript")
def get_transcript(session_id: str, db: Session = Depends(get_db)):
    session = _get_session_or_404(session_id, db)
    return [_serialize_message(m) for m in session.messages]


@router.get("/{session_id}/summary")
def get_summary(session_id: str, db: Session = Depends(get_db)):
    session = _get_session_or_404(session_id, db)
    summary = (
        db.query(InterviewSummary).filter(InterviewSummary.session_id == session.id).first()
    )
    if summary is None:
        raise HTTPException(status_code=404, detail="This interview hasn't finished yet.")
    return _serialize_summary(summary)


@router.post("/{session_id}/answers")
def answer_interview(
    session_id: str,
    payload: SubmitAnswerRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    session = _get_session_or_404(session_id, db)

    text = payload.answer.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Answer must not be empty.")

    rubric = load_rubric(session.round_type)
    try:
        llm = get_llm_provider(settings)
    except Exception as exc:  # noqa: BLE001 - LLM unreachable/misconfigured
        raise HTTPException(status_code=503, detail="Could not evaluate the answer right now.") from exc

    try:
        result = submit_answer(db=db, session=session, answer_text=text, llm=llm, rubric=rubric)
    except InterviewNotActiveError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _result_response(result)
