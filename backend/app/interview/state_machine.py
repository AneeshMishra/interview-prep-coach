"""
Deterministic mock-interview state machine (CLAUDE.md):

    SETUP -> RETRIEVE -> ASK -> WAIT_FOR_ANSWER -> EVALUATE
        -> FOLLOW_UP_OR_NEXT -> ASK -> ... -> SUMMARY -> COMPLETED

The backend — not the LLM — owns state, question count, session
lifecycle, and termination rules. The LLM only produces question text,
evaluation content, and follow-up suggestions (app/interview/evaluation.py);
this module decides whether those suggestions are accepted and when the
session ends.

V1 ships the system_design rubric only (ADR-007), so round_type is fixed
to "system_design" for now — see app/api/routers/interviews.py for where
that's enforced.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import (
    Document,
    Evaluation,
    InterviewMessage,
    InterviewQuestion,
    InterviewSession,
    InterviewSummary,
)
from app.interview.evaluation import evaluate_answer, summarize_interview
from app.interview.rubric import Rubric
from app.llm_providers.base import LLMProvider

MAX_QUESTIONS = 4
MAX_FOLLOWUPS_PER_QUESTION = 1
ROUND_TYPE = "system_design"


class InterviewNotActiveError(Exception):
    """Raised when an answer is submitted to a session that's already completed."""


@dataclass
class AskedQuestion:
    message: InterviewMessage


@dataclass
class InterviewCompleted:
    summary: InterviewSummary


def _pick_next_question(
    db: Session, user_id: str, company: str | None, exclude_ids: list[str]
) -> InterviewQuestion | None:
    """RETRIEVE: prefer a real, previously-uploaded question over generating
    one. Try company + round_type first, then fall back to any system_design
    question, excluding ones already asked this session. Scoped to the
    interviewing user's own uploaded questions — never another user's."""
    base_query = (
        db.query(InterviewQuestion)
        .join(Document)
        .filter(InterviewQuestion.round_type == ROUND_TYPE, Document.user_id == user_id)
    )
    if exclude_ids:
        base_query = base_query.filter(InterviewQuestion.id.notin_(exclude_ids))

    if company:
        match = base_query.filter(InterviewQuestion.company.ilike(f"%{company}%")).first()
        if match is not None:
            return match

    return base_query.first()


def start_interview(
    db: Session,
    llm: LLMProvider,
    llm_provider_name: str,
    llm_model: str,
    rubric: Rubric,
    company: str | None,
    role: str | None,
    user_id: str,
) -> AskedQuestion:
    session = InterviewSession(
        user_id=user_id,
        company=company,
        role=role,
        round_type=ROUND_TYPE,
        status="active",
        rubric_version=rubric.version,
        llm_provider=llm_provider_name,
        llm_model=llm_model,
        current_state="RETRIEVE",
    )
    db.add(session)
    db.commit()

    question = _pick_next_question(db, user_id, company, exclude_ids=[])
    if question is not None:
        content = question.question
        question_id = question.id
    else:
        # No matching question exists anywhere in the knowledge base yet —
        # fall back to an LLM-generated opener. It is never persisted as an
        # InterviewQuestion (that table's rows must trace back to an
        # uploaded document) and never presented with real provenance.
        content = _generate_opening_question(llm, rubric, company, role)
        question_id = None

    message = InterviewMessage(
        session_id=session.id, sequence_no=0, role="interviewer", content=content, question_id=question_id
    )
    db.add(message)
    session.current_state = "WAIT_FOR_ANSWER"
    db.commit()
    db.refresh(message)
    return AskedQuestion(message=message)


def _generate_opening_question(llm: LLMProvider, rubric: Rubric, company: str | None, role: str | None) -> str:
    context = f"company: {company or 'unspecified'}, role: {role or 'unspecified'}"
    prompt = (
        f"No stored interview question is available for this context ({context}). "
        f"Ask one open-ended {rubric.name.replace('_', ' ')} interview question suitable for this "
        "context. Reply with ONLY the question text, no preamble or quotes."
    )
    return llm.complete(
        system_prompt="You are an interviewer opening a mock interview.", user_prompt=prompt
    ).strip()


def submit_answer(
    db: Session,
    session: InterviewSession,
    answer_text: str,
    llm: LLMProvider,
    rubric: Rubric,
) -> AskedQuestion | InterviewCompleted:
    if session.status != "active":
        raise InterviewNotActiveError(f"Interview session {session.id} is not active.")

    messages = list(session.messages)
    interviewer_messages = [m for m in messages if m.role == "interviewer"]
    last_question_message = interviewer_messages[-1]
    next_seq = messages[-1].sequence_no + 1

    candidate_message = InterviewMessage(
        session_id=session.id,
        sequence_no=next_seq,
        role="candidate",
        content=answer_text,
        question_id=last_question_message.question_id,
    )
    db.add(candidate_message)
    session.current_state = "EVALUATE"
    db.commit()

    result = evaluate_answer(
        question_text=last_question_message.content, answer_text=answer_text, rubric=rubric, llm=llm
    )
    weighted_score = rubric.weighted_score(result.criteria_scores)

    evaluation = Evaluation(
        session_id=session.id,
        message_id=candidate_message.id,
        question_id=last_question_message.question_id,
        rubric_version=rubric.version,
        score=weighted_score,
        criteria_json=result.criteria_scores,
        strengths_json=result.strengths,
        weaknesses_json=result.weaknesses,
        feedback=result.feedback,
    )
    db.add(evaluation)
    db.commit()

    session.current_state = "FOLLOW_UP_OR_NEXT"
    db.commit()

    # Deterministic decision, not the LLM's: count root questions asked and
    # follow-ups already used for the current one directly from history,
    # rather than trusting the LLM's suggestion unconditionally.
    root_question_ids: list[str | None] = []
    for m in interviewer_messages:
        if not root_question_ids or root_question_ids[-1] != m.question_id:
            root_question_ids.append(m.question_id)
    questions_asked_count = len(root_question_ids)
    current_question_id = last_question_message.question_id
    followups_used = sum(1 for m in interviewer_messages if m.question_id == current_question_id) - 1

    can_follow_up = (
        result.ask_follow_up
        and result.follow_up_question
        and followups_used < MAX_FOLLOWUPS_PER_QUESTION
    )

    if can_follow_up:
        next_message = InterviewMessage(
            session_id=session.id,
            sequence_no=next_seq + 1,
            role="interviewer",
            content=result.follow_up_question,
            question_id=current_question_id,
        )
        db.add(next_message)
        session.current_state = "WAIT_FOR_ANSWER"
        db.commit()
        db.refresh(next_message)
        return AskedQuestion(message=next_message)

    if questions_asked_count >= MAX_QUESTIONS:
        summary = _generate_summary(db, session, llm, rubric)
        session.status = "completed"
        session.current_state = "COMPLETED"
        session.completed_at = datetime.utcnow()
        db.commit()
        return InterviewCompleted(summary=summary)

    excluded = [qid for qid in root_question_ids if qid is not None]
    next_question = _pick_next_question(db, session.user_id, session.company, exclude_ids=excluded)
    if next_question is not None:
        content, question_id = next_question.question, next_question.id
    else:
        content, question_id = (
            _generate_opening_question(llm, rubric, session.company, session.role),
            None,
        )

    next_message = InterviewMessage(
        session_id=session.id,
        sequence_no=next_seq + 1,
        role="interviewer",
        content=content,
        question_id=question_id,
    )
    db.add(next_message)
    session.current_state = "WAIT_FOR_ANSWER"
    db.commit()
    db.refresh(next_message)
    return AskedQuestion(message=next_message)


def _generate_summary(
    db: Session, session: InterviewSession, llm: LLMProvider, rubric: Rubric
) -> InterviewSummary:
    evaluations = db.query(Evaluation).filter(Evaluation.session_id == session.id).all()
    overall_score = sum(e.score for e in evaluations) / len(evaluations) if evaluations else 0.0
    criteria_breakdown = rubric.average_criteria([e.criteria_json or {} for e in evaluations])

    transcript_lines = [f"{m.role}: {m.content}" for m in session.messages]
    evaluation_lines = [
        f"Q{i + 1} score={e.score:.2f} feedback={e.feedback}" for i, e in enumerate(evaluations)
    ]

    result = summarize_interview(
        transcript_text="\n".join(transcript_lines),
        evaluations_text="\n".join(evaluation_lines),
        llm=llm,
    )

    summary = InterviewSummary(
        session_id=session.id,
        overall_score=overall_score,
        criteria_breakdown_json=criteria_breakdown,
        strengths_json=result.strengths,
        weaknesses_json=result.weaknesses,
        recommendations_json=result.recommendations,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary
