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


class RubricNotFoundError(Exception):
    pass


@lru_cache
def load_rubric(name: str) -> Rubric:
    path = RUBRICS_DIR / f"{name}.yaml"
    if not path.exists():
        raise RubricNotFoundError(f"No rubric named {name!r} in {RUBRICS_DIR}")
    data = yaml.safe_load(path.read_text())
    return Rubric(**data)
