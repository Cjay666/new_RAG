"""Document management router — upload, delete, list, status."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile

from ..config import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE_MB, UPLOAD_DIR
from ..models.schemas import DocStatus, DocumentResponse, DocumentUploadResponse
from ..services.pipeline import ingest_document, remove_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Simple in-memory document registry
_docs: dict[str, dict] = {}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(kb_id: str, file: UploadFile):
    """Upload a document to a knowledge base."""
    # Validate
    if not file.filename:
        raise HTTPException(400, "No filename provided")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    doc_id = str(uuid.uuid4())[:12]
    safe_name = f"{doc_id}_{file.filename}"
    file_path = UPLOAD_DIR / safe_name

    # Check size
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {MAX_UPLOAD_SIZE_MB}MB limit")

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Register
    _docs[doc_id] = {
        "doc_id": doc_id,
        "filename": file.filename,
        "file_size": len(content),
        "status": DocStatus.UPLOADED,
        "chunk_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Start ingestion (async background — in production use a task queue)
    try:
        _docs[doc_id]["status"] = DocStatus.PARSING
        result = await ingest_document(file_path, file.filename, kb_id)
        _docs[doc_id]["status"] = DocStatus.INDEXED
        _docs[doc_id]["chunk_count"] = result["chunk_count"]
    except Exception as e:
        _docs[doc_id]["status"] = DocStatus.FAILED
        raise HTTPException(500, f"Ingestion failed: {e}")

    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        status=_docs[doc_id]["status"],
        message=f"Indexed {result['chunk_count']} chunks",
    )


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, kb_id: str):
    """Delete a document and all its chunks."""
    if doc_id not in _docs:
        raise HTTPException(404, "Document not found")

    count = await remove_document(doc_id, kb_id)

    # Remove uploaded file
    for f in UPLOAD_DIR.glob(f"{doc_id}_*"):
        f.unlink()

    del _docs[doc_id]
    return {"ok": True, "deleted_chunks": count}


@router.get("/list/{kb_id}", response_model=list[DocumentResponse])
async def list_documents(kb_id: str):
    """List all documents in a knowledge base."""
    return [
        DocumentResponse(
            doc_id=d["doc_id"],
            kb_id=kb_id,
            filename=d["filename"],
            file_size=d["file_size"],
            status=d["status"],
            chunk_count=d["chunk_count"],
            created_at=d["created_at"],
        )
        for d in _docs.values()
    ]


@router.get("/status/{doc_id}", response_model=DocumentResponse)
async def document_status(doc_id: str, kb_id: str):
    """Get processing status of a document."""
    if doc_id not in _docs:
        raise HTTPException(404, "Document not found")
    d = _docs[doc_id]
    return DocumentResponse(
        doc_id=d["doc_id"],
        kb_id=kb_id,
        filename=d["filename"],
        file_size=d["file_size"],
        status=d["status"],
        chunk_count=d["chunk_count"],
        created_at=d["created_at"],
    )
