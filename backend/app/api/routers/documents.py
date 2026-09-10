"""
POST /documents/upload — accepts a .docx, kicks off ingestion.
Actual ingestion pipeline wiring (parse -> structure -> validate -> persist
-> embed -> upsert) lands with the Phase 1 ingestion-service task.
"""
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Document
from app.ingestion.docx_parser import content_hash

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported in v1.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    file_bytes = tmp_path.read_bytes()
    doc_hash = content_hash(file_bytes)

    existing = db.query(Document).filter(Document.content_hash == doc_hash).first()
    if existing:
        return {"document_id": existing.id, "status": "duplicate", "detail": "Already ingested."}

    document = Document(filename=file.filename, content_hash=doc_hash, status="pending")
    db.add(document)
    db.commit()
    db.refresh(document)

    # TODO: enqueue background ingestion task (parse -> structure -> persist -> embed)
    # using tmp_path and document.id.

    return {"document_id": document.id, "status": document.status}


@router.get("")
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).all()
