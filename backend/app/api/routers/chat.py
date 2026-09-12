"""
POST /chat/sessions — start a new Q&A chat session.
POST /chat/sessions/{session_id}/messages — ask a question, get a grounded answer.
GET  /chat/sessions/{session_id}/messages — full conversation history.

Retrieval-grounded search chat over the existing question knowledge base
(see app/chat/rag.py). Not the mock-interview state machine reserved for
InterviewSession/InterviewMessage.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.chat.rag import ChatCandidate, RETRIEVAL_LIMIT, answer_chat_message
from app.config import Settings, get_settings
from app.db.base import get_db
from app.db.models import ChatMessage, ChatSession, Document, InterviewQuestion, User
from app.llm_providers.factory import get_llm_provider
from app.retrieval.vector_store import get_vector_store

router = APIRouter(prefix="/chat", tags=["chat"])

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


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: str,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    session = _get_session_or_404(session_id, current_user.id, db)

    text = payload.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message must not be empty.")

    existing_messages = list(session.messages)
    next_seq = (existing_messages[-1].sequence_no + 1) if existing_messages else 0

    user_message = ChatMessage(
        session_id=session.id, sequence_no=next_seq, role="user", content=text
    )
    db.add(user_message)
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
