"""
Configuration-driven rubrics (ADR-003): YAML + Pydantic, never hardcoded
Python business logic. See app/rubrics/*.yaml.
"""
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

RUBRICS_DIR = Path(__file__).resolve().parent.parent / "rubrics"


class RubricCriterion(BaseModel):
    weight: float


class RubricScoreRange(BaseModel):
    min: float
    max: float


class Rubric(BaseModel):
    name: str
    version: str
    criteria: dict[str, RubricCriterion]
    score: RubricScoreRange

    def clamp(self, value: float) -> float:
        return max(self.score.min, min(self.score.max, value))

    def weighted_score(self, criteria_scores: dict[str, float]) -> float:
        """Deterministic, app-computed overall score — never trust the LLM's
        own arithmetic. Unknown/missing criteria score as the rubric's
        minimum; out-of-range scores are clamped rather than allowed to
        skew the result."""
        total_weight = sum(c.weight for c in self.criteria.values())
        if total_weight == 0:
            return self.score.min
        weighted_sum = sum(
            self.clamp(criteria_scores.get(name, self.score.min)) * criterion.weight
            for name, criterion in self.criteria.items()
        )
        return weighted_sum / total_weight

    def average_criteria(self, criteria_scores_list: list[dict[str, float]]) -> dict[str, float]:
        """Per-criterion breakdown for a completed interview: average this
        criterion's score across every answer it was actually scored on
        (clamped into the rubric's range first — same "never trust the
        LLM's own arithmetic" rule as weighted_score). Unlike
        weighted_score, a criterion never once scored across any answer is
        omitted rather than defaulted to the minimum — there's nothing to
        average, and defaulting it would fabricate a rating no answer
        actually received. Preserves the rubric's criteria order."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for name in self.criteria:
            for scores in criteria_scores_list:
                if name in scores:
                    totals[name] = totals.get(name, 0.0) + self.clamp(scores[name])
                    counts[name] = counts.get(name, 0) + 1
        return {name: totals[name] / counts[name] for name in self.criteria if name in counts}


class RubricNotFoundError(Exception):
    pass


@lru_cache
def load_rubric(name: str) -> Rubric:
    path = RUBRICS_DIR / f"{name}.yaml"
    if not path.exists():
        raise RubricNotFoundError(f"No rubric named {name!r} in {RUBRICS_DIR}")
    data = yaml.safe_load(path.read_text())
    return Rubric(**data)
