import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Document, InterviewQuestion, InterviewSession
from app.interview.rubric import load_rubric
from app.interview.state_machine import (
    MAX_FOLLOWUPS_PER_QUESTION,
    MAX_QUESTIONS,
    InterviewCompleted,
    AskedQuestion,
    InterviewNotActiveError,
    start_interview,
    submit_answer,
)


class ScriptedLLM:
    """Returns queued responses in order; asserts nothing is requested beyond what's queued."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        if not self.responses:
            raise AssertionError("LLM called more times than expected")
        return self.responses.pop(0)


def no_followup_response(score=4):
    return json.dumps(
        {
            "criteria_scores": {c: score for c in load_rubric("system_design").criteria},
            "strengths": ["Clear requirements gathering."],
            "weaknesses": ["Could discuss failure modes more."],
            "feedback": "Solid answer overall.",
            "ask_follow_up": False,
            "follow_up_question": None,
        }
    )


def followup_response():
    return json.dumps(
        {
            "criteria_scores": {c: 3 for c in load_rubric("system_design").criteria},
            "strengths": [],
            "weaknesses": ["Didn't address consistency."],
            "feedback": "Needs more depth.",
            "ask_follow_up": True,
            "follow_up_question": "How would you handle consistency across replicas?",
        }
    )


def summary_response():
    return json.dumps(
        {
            "strengths": ["Good communication."],
            "weaknesses": ["Scalability depth could improve."],
            "recommendations": ["Practice capacity estimation."],
        }
    )


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def rubric():
    return load_rubric("system_design")


def seed_question(db, company="Amazon", question="Design a URL shortener."):
    document = Document(filename="sample.docx", content_hash=f"hash-{question}", status="done")
    db.add(document)
    db.commit()
    q = InterviewQuestion(
        document_id=document.id, company=company, role="Backend Engineer",
        round_type="system_design", question=question, difficulty="medium",
        source_type="user_reported", extraction_confidence=0.9,
    )
    db.add(q)
    db.commit()
    return q


def test_start_interview_asks_a_real_stored_question_when_available(db_session, rubric):
    question = seed_question(db_session, company="Amazon", question="Design a URL shortener.")
    llm = ScriptedLLM([])  # should not be called — a real question exists

    result = start_interview(
        db=db_session, llm=llm, llm_provider_name="ollama", llm_model="llama3",
        rubric=rubric, company="Amazon", role="Backend Engineer",
    )

    assert isinstance(result, AskedQuestion)
    assert result.message.content == "Design a URL shortener."
    assert result.message.question_id == question.id
    assert result.message.role == "interviewer"
    assert llm.calls == []

    session = db_session.query(InterviewSession).first()
    assert session.status == "active"
    assert session.round_type == "system_design"
    assert session.rubric_version == rubric.version


def test_start_interview_falls_back_to_llm_when_no_question_exists(db_session, rubric):
    llm = ScriptedLLM(["Design a rate limiter for a public API."])

    result = start_interview(
        db=db_session, llm=llm, llm_provider_name="ollama", llm_model="llama3",
        rubric=rubric, company="SomeCompany", role="SRE",
    )

    assert result.message.content == "Design a rate limiter for a public API."
    assert result.message.question_id is None  # never fabricated as a real stored question
    assert len(llm.calls) == 1


def test_submit_answer_asks_follow_up_when_llm_flags_a_gap(db_session, rubric):
    seed_question(db_session)
    llm = ScriptedLLM([followup_response()])
    started = start_interview(
        db=db_session, llm=ScriptedLLM([]), llm_provider_name="ollama", llm_model="llama3",
        rubric=rubric, company="Amazon", role="Backend Engineer",
    )
    session = db_session.query(InterviewSession).first()

    result = submit_answer(db=db_session, session=session, answer_text="My answer.", llm=llm, rubric=rubric)

    assert isinstance(result, AskedQuestion)
    assert result.message.content == "How would you handle consistency across replicas?"
    assert result.message.question_id == started.message.question_id  # tied to the same root question


def test_submit_answer_caps_followups_per_question(db_session, rubric):
    seed_question(db_session, question="Design a URL shortener.")
    seed_question(db_session, question="Design a rate limiter.")

    llm_start = ScriptedLLM([])
    start_interview(
        db=db_session, llm=llm_start, llm_provider_name="ollama", llm_model="llama3",
        rubric=rubric, company="Amazon", role="Backend Engineer",
    )
    session = db_session.query(InterviewSession).first()

    assert MAX_FOLLOWUPS_PER_QUESTION == 1  # this test assumes the current cap

    llm = ScriptedLLM([followup_response(), no_followup_response()])
    first = submit_answer(db=db_session, session=session, answer_text="answer 1", llm=llm, rubric=rubric)
    assert first.message.content == "How would you handle consistency across replicas?"

    # A second follow-up suggestion for the SAME question must be refused —
    # the cap is enforced by the app, regardless of what the LLM asks for.
    second = submit_answer(db=db_session, session=session, answer_text="answer 2", llm=llm, rubric=rubric)
    assert second.message.content != "How would you handle consistency across replicas?"
    assert second.message.question_id != first.message.question_id


def test_interview_completes_after_max_questions(db_session, rubric):
    for i in range(MAX_QUESTIONS):
        seed_question(db_session, question=f"Question {i}")

    llm_start = ScriptedLLM([])
    start_interview(
        db=db_session, llm=llm_start, llm_provider_name="ollama", llm_model="llama3",
        rubric=rubric, company="Amazon", role="Backend Engineer",
    )
    session = db_session.query(InterviewSession).first()

    llm = ScriptedLLM(
        [no_followup_response() for _ in range(MAX_QUESTIONS - 1)] + [no_followup_response(), summary_response()]
    )

    result = None
    for i in range(MAX_QUESTIONS):
        result = submit_answer(db=db_session, session=session, answer_text=f"answer {i}", llm=llm, rubric=rubric)

    assert isinstance(result, InterviewCompleted)
    assert result.summary.overall_score == pytest.approx(4.0)
    assert result.summary.strengths_json == ["Good communication."]

    db_session.refresh(session)
    assert session.status == "completed"
    assert session.current_state == "COMPLETED"
    assert session.completed_at is not None


def test_submit_answer_rejects_completed_session(db_session, rubric):
    seed_question(db_session)
    start_interview(
        db=db_session, llm=ScriptedLLM([]), llm_provider_name="ollama", llm_model="llama3",
        rubric=rubric, company="Amazon", role="Backend Engineer",
    )
    session = db_session.query(InterviewSession).first()
    session.status = "completed"
    db_session.commit()

    with pytest.raises(InterviewNotActiveError):
        submit_answer(db=db_session, session=session, answer_text="too late", llm=ScriptedLLM([]), rubric=rubric)


def test_overall_score_is_computed_by_app_not_trusted_from_llm(db_session, rubric):
    """The summarizer LLM is never asked for (and its output never supplies)
    the numeric overall_score — it's always the average of persisted,
    rubric-weighted Evaluation.score values."""
    seed_question(db_session, question="Q1")
    seed_question(db_session, question="Q2")
    seed_question(db_session, question="Q3")
    seed_question(db_session, question="Q4")

    start_interview(
        db=db_session, llm=ScriptedLLM([]), llm_provider_name="ollama", llm_model="llama3",
        rubric=rubric, company="Amazon", role="Backend Engineer",
    )
    session = db_session.query(InterviewSession).first()

    # First 3 answers score 4/5 on every criterion, last scores 2/5.
    responses = [no_followup_response(score=4) for _ in range(3)]
    responses.append(no_followup_response(score=2))
    responses.append(summary_response())
    llm = ScriptedLLM(responses)

    result = None
    for i in range(MAX_QUESTIONS):
        result = submit_answer(db=db_session, session=session, answer_text=f"a{i}", llm=llm, rubric=rubric)

    assert isinstance(result, InterviewCompleted)
    # (4+4+4+2)/4 = 3.5 — a plain average of the app-computed weighted scores.
    assert result.summary.overall_score == pytest.approx(3.5)
