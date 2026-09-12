"""
POST /chat/sessions — start a new Q&A chat session.
GET  /chat/sessions — history: past sessions, most recently active first.
POST /chat/sessions/{session_id}/messages — ask a question, get a grounded answer.
POST /chat/sessions/{session_id}/messages/stream — same, streamed via SSE
    (CLAUDE.md: "Use SSE for LLM streaming").
GET  /chat/sessions/{session_id}/messages — full conversation history.

Retrieval-grounded search chat over the existing question knowledge base
(see app/chat/rag.py). Not the mock-interview state machine reserved for
InterviewSession/InterviewMessage.
"""
import json
from datetime import datetime
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.chat.rag import (
    AnswerStreamExtractor,
    ChatCandidate,
    NO_CANDIDATES_ANSWER,
    RETRIEVAL_LIMIT,
    answer_chat_message,
    build_user_prompt,
    CHAT_SYSTEM_PROMPT,
    parse_chat_answer,
)
from app.config import Settings, get_settings
from app.db.base import get_db
from app.db.models import ChatMessage, ChatSession, Document, InterviewQuestion, User
from app.llm_providers.base import LLMProvider
from app.llm_providers.factory import get_llm_provider
from app.rate_limit import get_llm_rate_limiter, rate_limit_by_user
from app.retrieval.vector_store import get_vector_store

router = APIRouter(prefix="/chat", tags=["chat"])

_llm_rate_limit = rate_limit_by_user(get_llm_rate_limiter)

# Most-recent user/assistant turns included as conversational context for
# the LLM. Retrieval itself uses only the latest message (see rag.py) —
# keeping that simple for v1 rather than trying to fold history into the
# search query too.
HISTORY_TURNS = 6


class SendMessageRequest(BaseModel):
    message: str


def _serialize_message(message: ChatMessage) -> dict:
    return {
        "id": message.id,
        "session_id": message.session_id,
        "role": message.role,
        "content": message.content,
        "cited_question_ids": message.cited_question_ids or [],
        "created_at": message.created_at,
    }


def _get_session_or_404(session_id: str, user_id: str, db: Session) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return session


PREVIEW_MAX_CHARS = 140


def _serialize_session_for_history(session: ChatSession, messages: list[ChatMessage]) -> dict:
    last_message = messages[-1] if messages else None
    preview = None
    if last_message is not None:
        preview = last_message.content[:PREVIEW_MAX_CHARS]
        if len(last_message.content) > PREVIEW_MAX_CHARS:
            preview += "…"
    return {
        "id": session.id,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "message_count": len(messages),
        "preview": preview,
    }


@router.get("/sessions")
def list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
        .all()
    )
    if not sessions:
        return []

    session_ids = [s.id for s in sessions]
    messages_by_session: dict[str, list[ChatMessage]] = {sid: [] for sid in session_ids}
    for message in (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id.in_(session_ids))
        .order_by(ChatMessage.session_id, ChatMessage.sequence_no)
        .all()
    ):
        messages_by_session[message.session_id].append(message)

    return [_serialize_session_for_history(s, messages_by_session[s.id]) for s in sessions]


@router.post("/sessions")
def create_session(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = ChatSession(user_id=current_user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "created_at": session.created_at}


@router.get("/sessions/{session_id}/messages")
def list_messages(
    session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    session = _get_session_or_404(session_id, current_user.id, db)
    return [_serialize_message(m) for m in session.messages]


def _prepare_message(
    session_id: str,
    raw_message: str,
    db: Session,
    settings: Settings,
    current_user: User,
) -> tuple[ChatSession, str, int, list[tuple[str, str]], list[ChatCandidate]]:
    """Shared prep for both the streaming and non-streaming send-message
    endpoints: validate, persist the user's message, retrieve candidates.
    Raises the same HTTPExceptions either endpoint would raise on its own —
    call this before opening an SSE stream, since a normal HTTP error
    response is no longer possible once streaming has started."""
    session = _get_session_or_404(session_id, current_user.id, db)

    text = raw_message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message must not be empty.")

    existing_messages = list(session.messages)
    next_seq = (existing_messages[-1].sequence_no + 1) if existing_messages else 0

    user_message = ChatMessage(
        session_id=session.id, sequence_no=next_seq, role="user", content=text
    )
    db.add(user_message)
    # ChatSession itself has no other column a new message would touch, so
    # without this the ORM never issues an UPDATE and updated_at (what
    # list_sessions orders by) would never move past creation time.
    session.updated_at = datetime.utcnow()
    db.commit()

    history = [(m.role, m.content) for m in existing_messages[-HISTORY_TURNS:]]

    try:
        vector_store = get_vector_store()
        hits = vector_store.search(text, limit=RETRIEVAL_LIMIT)
    except Exception as exc:  # noqa: BLE001 - Qdrant unreachable, degrade explicitly
        raise HTTPException(status_code=503, detail="Semantic search is unavailable.") from exc

    question_ids = [hit.question_id for hit in hits]
    questions_by_id = (
        {
            q.id: q
            for q in db.query(InterviewQuestion)
            .join(Document)
            .filter(InterviewQuestion.id.in_(question_ids), Document.user_id == current_user.id)
            .all()
        }
        if question_ids
        else {}
    )
    threshold = settings.low_confidence_threshold
    candidates = []
    for hit in hits:
        question = questions_by_id.get(hit.question_id)
        if question is None:
            continue
        candidates.append(
            ChatCandidate(
                id=question.id,
                company=question.company,
                role=question.role,
                round_type=question.round_type,
                question=question.question,
                answer_notes=question.answer_notes,
                difficulty=question.difficulty,
                needs_review=(
                    question.extraction_confidence is None
                    or question.extraction_confidence < threshold
                ),
            )
        )
    return session, text, next_seq, history, candidates


@router.post("/sessions/{session_id}/messages", dependencies=[Depends(_llm_rate_limit)])
def send_message(
    session_id: str,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    session, text, next_seq, history, candidates = _prepare_message(
        session_id, payload.message, db, settings, current_user
    )

    try:
        llm = get_llm_provider(settings)
        result = answer_chat_message(text, candidates, history, llm)
    except Exception as exc:  # noqa: BLE001 - LLM unreachable/misconfigured
        raise HTTPException(status_code=503, detail="Could not generate an answer right now.") from exc

    assistant_message = ChatMessage(
        session_id=session.id,
        sequence_no=next_seq + 1,
        role="assistant",
        content=result.answer,
        cited_question_ids=result.cited_question_ids,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    return _serialize_message(assistant_message)


def _sse(event: str, data: dict) -> str:
    # jsonable_encoder, not raw json.dumps — data can carry a serialized
    # ChatMessage whose created_at is a datetime, which json.dumps alone
    # doesn't know how to encode.
    return f"event: {event}\ndata: {json.dumps(jsonable_encoder(data))}\n\n"


def _generate_answer_events(
    llm: LLMProvider, text: str, candidates: list[ChatCandidate], history: list[tuple[str, str]]
) -> Iterator[tuple[str, dict]]:
    """Yields ("chunk", {...}) events as the LLM's answer text is generated,
    then a final ("done", {...}) or ("error", {...}). Runs entirely inside
    the SSE response body, so — unlike _prepare_message — nothing here can
    raise an HTTPException; an LLM failure becomes an "error" event instead,
    since HTTP headers (and the 200 status) are already committed by the
    time this generator starts running."""
    if not candidates:
        yield "done", {"answer": NO_CANDIDATES_ANSWER, "cited_question_ids": []}
        return

    prompt = build_user_prompt(text, candidates, history)
    extractor = AnswerStreamExtractor()
    try:
        for raw_chunk in llm.stream(CHAT_SYSTEM_PROMPT, prompt):
            delta = extractor.feed(raw_chunk)
            if delta:
                yield "chunk", {"text": delta}
    except Exception:  # noqa: BLE001 - LLM unreachable/misconfigured mid-stream
        yield "error", {"detail": "Could not generate an answer right now."}
        return

    result = parse_chat_answer(extractor.buffer, candidates)
    yield "done", {"answer": result.answer, "cited_question_ids": result.cited_question_ids}


@router.post("/sessions/{session_id}/messages/stream", dependencies=[Depends(_llm_rate_limit)])
def send_message_stream(
    session_id: str,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    session, text, next_seq, history, candidates = _prepare_message(
        session_id, payload.message, db, settings, current_user
    )

    try:
        llm = get_llm_provider(settings)
    except Exception as exc:  # noqa: BLE001 - misconfigured provider (e.g. missing API key)
        raise HTTPException(status_code=503, detail="Could not generate an answer right now.") from exc

    def event_stream() -> Iterator[str]:
        for event_name, data in _generate_answer_events(llm, text, candidates, history):
            yield _sse(event_name, data)
            if event_name == "error":
                return  # nothing to persist — the stream ends here
            if event_name == "done":
                assistant_message = ChatMessage(
                    session_id=session.id,
                    sequence_no=next_seq + 1,
                    role="assistant",
                    content=data["answer"],
                    cited_question_ids=data["cited_question_ids"],
                )
                db.add(assistant_message)
                db.commit()
                db.refresh(assistant_message)
                yield _sse("message", _serialize_message(assistant_message))

    return StreamingResponse(event_stream(), media_type="text/event-stream")
