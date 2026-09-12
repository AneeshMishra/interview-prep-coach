"""
End-to-end document ingestion: parse -> structure -> validate -> persist ->
embed -> upsert. Runs as a FastAPI background task so the upload endpoint
can return immediately (see app/api/routers/documents.py).

LLM/vector-store dependencies are injectable so this can be unit-tested
without a running Ollama or Qdrant instance.
"""
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Document, InterviewQuestion, QuestionTag
from app.ingestion.docx_parser import parse_docx
from app.ingestion.structurer import structure_section
from app.llm_providers.base import LLMProvider
from app.llm_providers.factory import get_llm_provider
from app.retrieval.vector_store import VectorStore, get_vector_store


def question_qdrant_metadata(question: InterviewQuestion) -> dict:
    """Qdrant payload for one question — shared with app/ingestion/reindex.py
    so a from-scratch reindex produces exactly the same payload shape as
    ingestion-time indexing does."""
    return {
        "company": question.company,
        "role": question.role,
        "round_type": question.round_type,
        "difficulty": question.difficulty,
        "source_type": question.source_type,
        "source_document_id": question.document_id,
    }


def run_ingestion(
    document_id: str,
    file_path: str,
    db: Session,
    llm: LLMProvider | None = None,
    vector_store: VectorStore | None = None,
) -> None:
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        return

    document.status = "processing"
    document.error_message = None
    db.commit()

    try:
        llm = llm or get_llm_provider(get_settings())
        vector_store = vector_store or get_vector_store()
        sections = parse_docx(file_path)

        for section in sections:
            try:
                extracted = structure_section(section, llm, document_context=document.filename)
            except ValueError:
                # LLM returned non-JSON for this section — skip it, keep going.
                continue

            for record in extracted:
                question = InterviewQuestion(
                    document_id=document.id,
                    company=record.company,
                    role=record.role,
                    round_type=record.round_type.value,
                    question=record.question,
                    answer_notes=record.answer_notes,
                    difficulty=record.difficulty.value if record.difficulty else None,
                    source_type=record.source_type.value,
                    source_section=record.source_section,
                    extraction_confidence=record.extraction_confidence,
                )
                db.add(question)
                db.flush()  # assign question.id before tagging/embedding

                for tag in record.tags:
                    db.add(QuestionTag(question_id=question.id, tag=tag))

                vector_store.upsert_question(
                    question_id=question.id,
                    text=question.question,
                    metadata=question_qdrant_metadata(question),
                )

        document.status = "done"
        db.commit()
    except Exception as exc:  # noqa: BLE001 - recorded on the document, not re-raised
        db.rollback()
        document.status = "failed"
        document.error_message = str(exc)
        db.commit()
    finally:
        Path(file_path).unlink(missing_ok=True)
