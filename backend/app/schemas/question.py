"""
Pydantic schemas for the canonical interview-question model.
This is the contract between: LLM structuring output -> validation -> persistence.
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RoundType(str, Enum):
    system_design = "system_design"
    dsa = "dsa"
    behavioral = "behavioral"
    technical = "technical"
    hr = "hr"
    other = "other"


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class SourceType(str, Enum):
    user_reported = "user_reported"
    ai_generated = "ai_generated"
    ai_followup = "ai_followup"


class ExtractedQuestion(BaseModel):
    """Shape the LLM structuring pass must produce for one Q&A record."""

    company: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    round_type: RoundType = RoundType.other
    question: str = Field(..., min_length=3)
    answer_notes: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    tags: list[str] = Field(default_factory=list)
    source_type: SourceType = SourceType.user_reported
    source_section: Optional[str] = None
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str]) -> list[str]:
        return [t.strip().lower() for t in v if t.strip()]


class QuestionOut(ExtractedQuestion):
    """What the API returns — adds identifiers."""

    id: str
    document_id: str


class QuestionFilter(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    round_type: Optional[RoundType] = None
    difficulty: Optional[Difficulty] = None
    query: Optional[str] = None  # free-text semantic search
    limit: int = Field(default=20, ge=1, le=100)
