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
import re
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


NO_CANDIDATES_ANSWER = "I couldn't find anything relevant to that in the knowledge base yet."


def parse_chat_answer(raw: str, candidates: list[ChatCandidate]) -> ChatAnswer:
    """Parse+validate a raw LLM response against the CHAT_SYSTEM_PROMPT
    contract. Shared by the non-streaming and streaming code paths so both
    apply identical citation-trust rules to identical LLM output."""
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


_ANSWER_FIELD_PATTERN = re.compile(r'"answer"\s*:\s*"')

_SIMPLE_JSON_ESCAPES = {
    '"': '"', "\\": "\\", "/": "/", "n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f",
}


def _decode_partial_json_string(buffer: str, start: int) -> tuple[str, bool]:
    """Decode a JSON string body starting at buffer[start] (just past the
    opening quote), stopping at the first unescaped closing quote — or, if
    the closing quote hasn't arrived yet, decoding as much as is safely
    decodable (never a half-consumed escape sequence at the buffer's end).
    Returns (decoded_text, closed)."""
    out: list[str] = []
    i = start
    n = len(buffer)
    while i < n:
        ch = buffer[i]
        if ch == "\\":
            if i + 1 >= n:
                break  # escape sequence not fully arrived yet
            esc = buffer[i + 1]
            if esc in _SIMPLE_JSON_ESCAPES:
                out.append(_SIMPLE_JSON_ESCAPES[esc])
                i += 2
                continue
            if esc == "u":
                if i + 6 > n:
                    break  # \uXXXX not fully arrived yet
                out.append(chr(int(buffer[i + 2 : i + 6], 16)))
                i += 6
                continue
            i += 1  # unrecognized escape — skip the backslash defensively
            continue
        if ch == '"':
            return "".join(out), True
        out.append(ch)
        i += 1
    return "".join(out), False


class AnswerStreamExtractor:
    """Incrementally extracts the growing "answer" string value out of a raw
    token stream shaped like the CHAT_SYSTEM_PROMPT contract:
    {"answer": "...", "cited_question_ids": [...]}. Citations are never
    streamed — they're only meaningful (and only trustworthy, see
    parse_chat_answer's validation) once the full object has arrived, so
    only the free-text "answer" field is worth showing incrementally."""

    def __init__(self):
        self.buffer = ""
        self._answer_start: int | None = None
        self._emitted = 0
        self._closed = False

    def feed(self, chunk: str) -> str:
        """Feed a newly-arrived raw chunk; return the newly-decoded slice of
        answer text to display (possibly empty)."""
        self.buffer += chunk
        if self._closed:
            return ""
        if self._answer_start is None:
            match = _ANSWER_FIELD_PATTERN.search(self.buffer)
            if match is None:
                return ""
            self._answer_start = match.end()

        decoded, closed = _decode_partial_json_string(self.buffer, self._answer_start)
        new_text = decoded[self._emitted :]
        self._emitted = len(decoded)
        self._closed = closed
        return new_text


def answer_chat_message(
    user_message: str,
    candidates: list[ChatCandidate],
    history: list[tuple[str, str]],
    llm: LLMProvider,
) -> ChatAnswer:
    if not candidates:
        return ChatAnswer(answer=NO_CANDIDATES_ANSWER, cited_question_ids=[])

    prompt = build_user_prompt(user_message, candidates, history)
    raw = llm.complete(system_prompt=CHAT_SYSTEM_PROMPT, user_prompt=prompt)
    return parse_chat_answer(raw, candidates)
