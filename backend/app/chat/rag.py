"""
RAG-based Q&A over the question knowledge base — Phase 2's "chat where a
user can ask a query." Not the mock-interview state machine: see the
ChatSession/ChatMessage docstring in app/db/models.py for why those are
separate from InterviewSession/InterviewMessage.

Retrieval-grounded by design: the LLM is instructed to answer only from the
candidate questions it's given and to say so plainly when nothing relevant
is found, rather than inventing an answer untethered from the stored data —
consistent with the app's provenance principle (CLAUDE.md: never present
something not actually in the knowledge base as if it were).
"""
import json
from dataclasses import asdict, dataclass

from app.llm_providers.base import LLMProvider

RETRIEVAL_LIMIT = 8

CHAT_SYSTEM_PROMPT = """You are a search assistant over a personal interview-question knowledge base.
Answer the user's question using ONLY the candidate questions provided below — never invent
a question, company, or fact that isn't in them.

Output ONLY a JSON object, no prose outside it, matching this shape:
{
  "answer": str,
  "cited_question_ids": [str]
}

"answer" is a natural-language answer for the user. "cited_question_ids" lists the ids of
the candidates you actually used to build the answer; use [] if you used none.

If none of the candidates are relevant to the question, say so plainly in "answer" and
return an empty cited_question_ids list — do not guess or fabricate an answer.
"""


@dataclass
class ChatCandidate:
    id: str
    company: str | None
    role: str | None
    round_type: str | None
    question: str
    answer_notes: str | None
    difficulty: str | None
    needs_review: bool


@dataclass
class ChatAnswer:
    answer: str
    cited_question_ids: list[str]


def build_user_prompt(
    user_message: str, candidates: list[ChatCandidate], history: list[tuple[str, str]]
) -> str:
    candidates_json = json.dumps([asdict(c) for c in candidates], indent=2)
    history_text = "\n".join(f"{role}: {content}" for role, content in history) if history else "(none)"
    return (
        f"Conversation so far:\n{history_text}\n\n"
        f"Candidate questions (JSON):\n{candidates_json}\n\n"
        f"User's new question: {user_message}"
    )


def answer_chat_message(
    user_message: str,
    candidates: list[ChatCandidate],
    history: list[tuple[str, str]],
    llm: LLMProvider,
) -> ChatAnswer:
    if not candidates:
        return ChatAnswer(
            answer="I couldn't find anything relevant to that in the knowledge base yet.",
            cited_question_ids=[],
        )

    prompt = build_user_prompt(user_message, candidates, history)
    raw = llm.complete(system_prompt=CHAT_SYSTEM_PROMPT, user_prompt=prompt)

    try:
        parsed = json.loads(raw)
        answer = str(parsed.get("answer", "")).strip()
        cited = [str(i) for i in parsed.get("cited_question_ids", [])]
    except (json.JSONDecodeError, AttributeError, TypeError):
        # A chat reply that's just the raw unstructured text is still
        # useful to the user — unlike ingestion, where malformed LLM
        # output must be safely dropped rather than persisted as fact.
        answer = raw.strip()
        cited = []

    # Never let the LLM claim a citation to a question it wasn't shown, or
    # one that doesn't exist — citations are a trust mechanism, not decoration.
    valid_ids = {c.id for c in candidates}
    cited = [qid for qid in cited if qid in valid_ids]

    if not answer:
        answer = "I couldn't find anything relevant to that in the knowledge base."

    return ChatAnswer(answer=answer, cited_question_ids=cited)
