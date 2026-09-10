"""
Turns raw extracted sections into validated ExtractedQuestion records
using an LLM structuring prompt. The LLM call is delegated to whichever
provider is configured (see app/llm_providers).
"""
import json

from app.ingestion.docx_parser import RawSection
from app.llm_providers.base import LLMProvider
from app.schemas.question import ExtractedQuestion

STRUCTURING_SYSTEM_PROMPT = """You convert raw interview-experience text into
structured JSON records. Output ONLY a JSON array, no prose.

Each element must match this shape:
{
  "company": str,
  "role": str,
  "round_type": "system_design"|"dsa"|"behavioral"|"technical"|"hr"|"other",
  "question": str,
  "answer_notes": str | null,
  "difficulty": "easy"|"medium"|"hard"|null,
  "tags": [str],
  "source_type": "user_reported",
  "source_section": str | null,
  "extraction_confidence": float between 0 and 1
}

Rules:
- source_type must always be "user_reported" for content extracted from the
  user's document — never invent questions.
- If company/role can't be determined from context, use "unknown".
- extraction_confidence reflects how clearly the text maps to this schema.
"""


def build_prompt(section: RawSection) -> str:
    body = "\n".join(section.paragraphs)
    for table in section.tables:
        body += "\n" + "\n".join(" | ".join(row) for row in table)
    heading = section.heading or "(no heading)"
    return f"Section: {heading}\n\n{body}"


def structure_section(
    section: RawSection, llm: LLMProvider, document_context: str = ""
) -> list[ExtractedQuestion]:
    prompt = build_prompt(section)
    if document_context:
        prompt = f"Document context: {document_context}\n\n{prompt}"

    raw_response = llm.complete(
        system_prompt=STRUCTURING_SYSTEM_PROMPT,
        user_prompt=prompt,
    )

    try:
        records = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM structuring output was not valid JSON: {exc}") from exc

    validated: list[ExtractedQuestion] = []
    for record in records:
        # Pydantic validation is the confidence gate mentioned in the
        # architecture doc — invalid records are skipped, not persisted.
        try:
            validated.append(ExtractedQuestion(**record))
        except Exception:
            continue

    return validated
