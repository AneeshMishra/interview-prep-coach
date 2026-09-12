import json

from app.chat.rag import ChatCandidate, answer_chat_message


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.last_system_prompt = None
        self.last_user_prompt = None

    def complete(self, system_prompt, user_prompt):
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return self.response


def make_candidate(id_="q1", **overrides):
    defaults = dict(
        id=id_,
        company="Nagarro",
        role="Backend Engineer",
        round_type="technical",
        question="What is a virtual thread in Java?",
        answer_notes=None,
        difficulty="medium",
        needs_review=False,
    )
    defaults.update(overrides)
    return ChatCandidate(**defaults)


def test_returns_answer_and_valid_citations():
    llm = FakeLLM(json.dumps({"answer": "Virtual threads are lightweight JVM-managed threads.", "cited_question_ids": ["q1"]}))
    candidates = [make_candidate("q1")]

    result = answer_chat_message("what is a virtual thread?", candidates, history=[], llm=llm)

    assert result.answer == "Virtual threads are lightweight JVM-managed threads."
    assert result.cited_question_ids == ["q1"]


def test_drops_citations_not_among_the_offered_candidates():
    # The LLM must never be trusted to cite something it wasn't shown.
    llm = FakeLLM(json.dumps({"answer": "Some answer.", "cited_question_ids": ["q1", "made-up-id"]}))
    candidates = [make_candidate("q1")]

    result = answer_chat_message("question", candidates, history=[], llm=llm)

    assert result.cited_question_ids == ["q1"]


def test_falls_back_to_raw_text_on_malformed_json():
    llm = FakeLLM("not json at all")
    candidates = [make_candidate()]

    result = answer_chat_message("question", candidates, history=[], llm=llm)

    assert result.answer == "not json at all"
    assert result.cited_question_ids == []


def test_returns_no_results_message_without_calling_llm_when_no_candidates():
    llm = FakeLLM("should not be called")
    result = answer_chat_message("anything", candidates=[], history=[], llm=llm)

    assert result.cited_question_ids == []
    assert "couldn't find anything relevant" in result.answer.lower()
    assert llm.last_user_prompt is None


def test_prompt_includes_candidates_and_history():
    llm = FakeLLM(json.dumps({"answer": "answer", "cited_question_ids": []}))
    candidates = [make_candidate("q1", question="Design a rate limiter")]
    history = [("user", "hi"), ("assistant", "hello")]

    answer_chat_message("rate limiter design?", candidates, history, llm)

    assert "Design a rate limiter" in llm.last_user_prompt
    assert "user: hi" in llm.last_user_prompt
    assert "assistant: hello" in llm.last_user_prompt
    assert "rate limiter design?" in llm.last_user_prompt
    assert llm.last_system_prompt is not None


def test_empty_answer_gets_a_default_message():
    llm = FakeLLM(json.dumps({"answer": "", "cited_question_ids": []}))
    result = answer_chat_message("question", [make_candidate()], history=[], llm=llm)

    assert result.answer  # non-empty fallback, not a blank string
