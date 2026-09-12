"""
POST /documents/upload — accepts a .docx, kicks off ingestion.
POST /documents/import/google-doc — same, but fetches a publicly-shared
Google Doc's .docx export instead of taking a file upload.

Both converge on _register_document_and_start_ingestion, and from there
run the exact same pipeline (parse -> structure -> validate -> persist ->
embed -> upsert) as a background task; see app/ingestion/pipeline.py.
"""
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings
from app.db.base import get_db
from app.db.models import Document, User
from app.ingestion.docx_parser import content_hash
from app.ingestion.google_docs_import import (
    GoogleDocNotAccessible,
    GoogleDocTooLarge,
    download_google_doc_as_docx,
    extract_google_doc_id,
    sanitize_docx_filename,
)
from app.ingestion.pipeline import run_ingestion
from app.rate_limit import get_upload_rate_limiter, rate_limit_by_user

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB

_upload_rate_limit = rate_limit_by_user(get_upload_rate_limiter)


class ImportGoogleDocRequest(BaseModel):
    url: str


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


def _register_document_and_start_ingestion(
    tmp_path: Path,
    filename: str,
    user_id: str,
    db: Session,
    background_tasks: BackgroundTasks,
) -> dict:
    file_bytes = tmp_path.read_bytes()
    doc_hash = content_hash(file_bytes)

    existing = (
        db.query(Document)
        .filter(Document.user_id == user_id, Document.content_hash == doc_hash)
        .first()
    )
    if existing:
        tmp_path.unlink(missing_ok=True)
        return {"document_id": existing.id, "status": "duplicate", "detail": "Already ingested."}

    document = Document(user_id=user_id, filename=filename, content_hash=doc_hash, status="pending")
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(run_ingestion, document.id, str(tmp_path), db)

    return {"document_id": document.id, "status": document.status}


@router.post("/upload", dependencies=[Depends(_upload_rate_limit)])
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    # Sanitize: take only the basename, so a crafted filename (e.g. a path
    # traversal attempt) can never escape the intended upload directory or
    # get stored verbatim.
    safe_filename = Path(file.filename or "").name
    if not safe_filename or not safe_filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported in v1.")

    tmp_path = await _save_upload_within_limit(file, settings.max_upload_size_bytes)
    return _register_document_and_start_ingestion(
        tmp_path, safe_filename, current_user.id, db, background_tasks
    )


@router.post("/import/google-doc", dependencies=[Depends(_upload_rate_limit)])
async def import_google_doc(
    payload: ImportGoogleDocRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    doc_id = extract_google_doc_id(payload.url)
    if not doc_id:
        raise HTTPException(status_code=400, detail="That doesn't look like a Google Docs document URL.")

    try:
        tmp_path, exported_filename = await download_google_doc_as_docx(
            doc_id, settings.max_upload_size_bytes
        )
    except GoogleDocTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except GoogleDocNotAccessible as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{exc} Make sure the document's sharing is set to "
                '"Anyone with the link can view", or download it manually '
                "(File > Download > Microsoft Word (.docx)) and upload that "
                "file instead."
            ),
        ) from exc

    # doc_id may contain "/" for a "Publish to the web" link (e.g. "e/<token>"),
    # which is a valid URL path segment but not a valid filename character.
    fallback_name = f"google-doc-{doc_id.replace('/', '-')}.docx"
    safe_filename = sanitize_docx_filename(exported_filename) or fallback_name
    return _register_document_and_start_ingestion(
        tmp_path, safe_filename, current_user.id, db, background_tasks
    )


@router.get("")
def list_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Document).filter(Document.user_id == current_user.id).all()
