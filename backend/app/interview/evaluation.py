"""
LLM-backed pieces of the mock interview: scoring a candidate's answer
against the rubric, and summarizing a completed session. The LLM only
produces content here — it never decides whether to continue the
interview or computes the trusted overall score; see state_machine.py
and Rubric.weighted_score() for those (CLAUDE.md: the orchestrator
decides whether and when LLM outputs are accepted).
"""
import json
from dataclasses import dataclass

from app.interview.rubric import Rubric
from app.llm_providers.base import LLMProvider

EVALUATE_SYSTEM_PROMPT_TEMPLATE = """You are a rigorous, fair {round_type} interviewer evaluating a \
candidate's answer.

Score the answer against each of these rubric criteria, each on a scale from {min_score} to {max_score}:
{criteria_list}

Output ONLY a JSON object, no prose outside it:
{{
  "criteria_scores": {{"<criterion>": number, ... one entry per criterion above ...}},
  "strengths": [string],
  "weaknesses": [string],
  "feedback": string,
  "ask_follow_up": boolean,
  "follow_up_question": string or null
}}

Only set ask_follow_up to true when there's a genuinely important gap worth probing immediately —
not for every answer. follow_up_question must be null when ask_follow_up is false.
"""

SUMMARY_SYSTEM_PROMPT = """You are summarizing a completed mock interview for the candidate.

You will be given the full transcript and the rubric evaluation already computed for each answer.
Output ONLY a JSON object, no prose outside it:
{
  "strengths": [string],
  "weaknesses": [string],
  "recommendations": [string]
}

Do not invent a numeric overall score — that's computed separately from the rubric evaluations,
not by you. Base strengths/weaknesses/recommendations only on what's in the transcript and evaluations.
"""


@dataclass
class EvaluationResult:
    criteria_scores: dict[str, float]
    strengths: list[str]
    weaknesses: list[str]
    feedback: str
    ask_follow_up: bool
    follow_up_question: str | None


@dataclass
class SummaryResult:
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]


def _safe_json(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def evaluate_answer(
    question_text: str, answer_text: str, rubric: Rubric, llm: LLMProvider
) -> EvaluationResult:
    criteria_list = "\n".join(f"- {name} (weight {c.weight})" for name, c in rubric.criteria.items())
    system_prompt = EVALUATE_SYSTEM_PROMPT_TEMPLATE.format(
        round_type=rubric.name.replace("_", " "),
        min_score=rubric.score.min,
        max_score=rubric.score.max,
        criteria_list=criteria_list,
    )
    user_prompt = f"Question asked: {question_text}\n\nCandidate's answer: {answer_text}"

    raw = llm.complete(system_prompt=system_prompt, user_prompt=user_prompt)
    parsed = _safe_json(raw)

    raw_scores = parsed.get("criteria_scores", {})
    criteria_scores = {
        name: float(raw_scores[name])
        for name in rubric.criteria
        if name in raw_scores and isinstance(raw_scores[name], (int, float))
    }

    return EvaluationResult(
        criteria_scores=criteria_scores,
        strengths=[str(s) for s in parsed.get("strengths", []) if isinstance(s, str)],
        weaknesses=[str(s) for s in parsed.get("weaknesses", []) if isinstance(s, str)],
        feedback=str(parsed.get("feedback", "")).strip(),
        ask_follow_up=bool(parsed.get("ask_follow_up", False)),
        follow_up_question=(
            str(parsed["follow_up_question"]).strip()
            if isinstance(parsed.get("follow_up_question"), str) and parsed["follow_up_question"].strip()
            else None
        ),
    )


def summarize_interview(transcript_text: str, evaluations_text: str, llm: LLMProvider) -> SummaryResult:
    user_prompt = f"Transcript:\n{transcript_text}\n\nRubric evaluations:\n{evaluations_text}"
    raw = llm.complete(system_prompt=SUMMARY_SYSTEM_PROMPT, user_prompt=user_prompt)
    parsed = _safe_json(raw)

    return SummaryResult(
        strengths=[str(s) for s in parsed.get("strengths", []) if isinstance(s, str)],
        weaknesses=[str(s) for s in parsed.get("weaknesses", []) if isinstance(s, str)],
        recommendations=[str(s) for s in parsed.get("recommendations", []) if isinstance(s, str)],
    )
