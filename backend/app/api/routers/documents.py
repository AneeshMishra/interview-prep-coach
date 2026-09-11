"""
POST /documents/upload — accepts a .docx, kicks off ingestion.

The full pipeline (parse -> structure -> validate -> persist -> embed ->
upsert) runs as a background task; see app/ingestion/pipeline.py.
"""
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.base import get_db
from app.db.models import Document
from app.ingestion.docx_parser import content_hash
from app.ingestion.pipeline import run_ingestion

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB


async def _save_upload_within_limit(file: UploadFile, max_bytes: int) -> Path:
    """Stream the upload to a temp file, aborting (and cleaning up) if it
    exceeds max_bytes, instead of buffering the whole thing into memory."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp_path = Path(tmp.name)
        total = 0
        while chunk := await file.read(UPLOAD_CHUNK_SIZE):
            total += len(chunk)
            if total > max_bytes:
                tmp.close()
                tmp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds maximum upload size of {max_bytes} bytes.",
                )
            tmp.write(chunk)
    return tmp_path


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    # Sanitize: take only the basename, so a crafted filename (e.g. a path
    # traversal attempt) can never escape the intended upload directory or
    # get stored verbatim.
    safe_filename = Path(file.filename or "").name
    if not safe_filename or not safe_filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported in v1.")

    tmp_path = await _save_upload_within_limit(file, settings.max_upload_size_bytes)

    file_bytes = tmp_path.read_bytes()
    doc_hash = content_hash(file_bytes)

    existing = db.query(Document).filter(Document.content_hash == doc_hash).first()
    if existing:
        tmp_path.unlink(missing_ok=True)
        return {"document_id": existing.id, "status": "duplicate", "detail": "Already ingested."}

    document = Document(filename=safe_filename, content_hash=doc_hash, status="pending")
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(run_ingestion, document.id, str(tmp_path), db)

    return {"document_id": document.id, "status": document.status}


@router.get("")
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).all()
