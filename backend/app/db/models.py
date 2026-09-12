"""
SQLAlchemy models — the system of record.
Mirrors the schema in docs/architecture.md section 7.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, Integer, ForeignKey, DateTime, JSON, Text
)
from sqlalchemy.orm import relationship

from app.db.base import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=gen_uuid)
    filename = Column(String, nullable=False)
    content_hash = Column(String, unique=True, nullable=False, index=True)
    status = Column(String, default="pending")  # pending|processing|done|failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    questions = relationship("InterviewQuestion", back_populates="document")


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(String, primary_key=True, default=gen_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    company = Column(String, index=True)
    role = Column(String, index=True)
    round_type = Column(String, index=True)  # e.g. system_design, dsa, behavioral
    question = Column(Text, nullable=False)
    answer_notes = Column(Text, nullable=True)
    difficulty = Column(String, nullable=True)  # easy|medium|hard
    source_type = Column(String, default="user_reported")  # user_reported|ai_generated|ai_followup
    source_section = Column(String, nullable=True)
    extraction_confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="questions")
    tags = relationship("QuestionTag", back_populates="question")


class QuestionTag(Base):
    __tablename__ = "question_tags"

    question_id = Column(String, ForeignKey("interview_questions.id"), primary_key=True)
    tag = Column(String, primary_key=True)

    question = relationship("InterviewQuestion", back_populates="tags")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(String, primary_key=True, default=gen_uuid)
    company = Column(String)
    role = Column(String)
    round_type = Column(String)
    status = Column(String, default="active")  # active|completed|abandoned
    rubric_version = Column(String, nullable=True)
    llm_provider = Column(String, nullable=True)
    llm_model = Column(String, nullable=True)
    current_state = Column(String, default="SETUP")
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    messages = relationship(
        "InterviewMessage", back_populates="session", order_by="InterviewMessage.sequence_no"
    )


class InterviewMessage(Base):
    __tablename__ = "interview_messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False)
    sequence_no = Column(Integer, nullable=False)
    role = Column(String, nullable=False)  # interviewer|candidate
    content = Column(Text, nullable=False)
    question_id = Column(String, ForeignKey("interview_questions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("InterviewSession", back_populates="messages")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False)
    message_id = Column(String, ForeignKey("interview_messages.id"), nullable=False)
    question_id = Column(String, ForeignKey("interview_questions.id"), nullable=True)
    rubric_version = Column(String, nullable=True)
    score = Column(Float, nullable=True)
    criteria_json = Column(JSON, nullable=True)
    strengths_json = Column(JSON, nullable=True)
    weaknesses_json = Column(JSON, nullable=True)
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class InterviewSummary(Base):
    __tablename__ = "interview_summaries"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False)
    overall_score = Column(Float, nullable=True)
    strengths_json = Column(JSON, nullable=True)
    weaknesses_json = Column(JSON, nullable=True)
    recommendations_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatSession(Base):
    """A Q&A search-chat conversation over the question knowledge base.

    Deliberately separate from InterviewSession: that table (above) is
    reserved for the future mock-interview state machine (SETUP -> ASK ->
    WAIT_FOR_ANSWER -> EVALUATE -> SUMMARY per CLAUDE.md) — a stateful,
    rubric-scored workflow. This is a plain RAG chat: no state machine, no
    evaluation, just retrieval-grounded question answering.
    """

    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=gen_uuid)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "ChatMessage", back_populates="session", order_by="ChatMessage.sequence_no"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)
    sequence_no = Column(Integer, nullable=False)
    role = Column(String, nullable=False)  # user|assistant
    content = Column(Text, nullable=False)
    # Question ids the assistant grounded its answer in — null/empty for a
    # user message, or for an assistant message that found nothing relevant.
    cited_question_ids = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")
