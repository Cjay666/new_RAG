"""Document management router — upload, delete, list, with progress tracking."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import aiofiles
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile

from ..config import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE_MB, UPLOAD_DIR
from ..models.schemas import DocStatus, DocumentResponse, DocumentUploadResponse
from ..services.pipeline import ingest_document, remove_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

# In-memory document registry with progress tracking
_docs: dict[str, dict] = {}


def _progress_callback_factory(doc_id: str):
    """Create a progress callback that updates _docs[doc_id]."""
    async def _cb(status: str, pct: int):
        status_map = {
            "parsing": DocStatus.PARSING,
            "chunking": DocStatus.CHUNKING,
            "embedding": DocStatus.EMBEDDING,
            "indexing": DocStatus.EMBEDDING,  # same stage
            "indexed": DocStatus.INDEXED,
        }
        if doc_id in _docs:
            _docs[doc_id]["status"] = status_map.get(status, DocStatus.UPLOADED)
            _docs[doc_id]["progress"] = pct
            _docs[doc_id]["stage"] = status
    return _cb


async def _process_document(doc_id: str, file_path, filename: str, kb_id: str):
    """Background task: full ingestion pipeline with progress updates."""
    try:
        cb = _progress_callback_factory(doc_id)
        result = await ingest_document(file_path, filename, kb_id, progress_callback=cb)
        if doc_id in _docs:
            _docs[doc_id]["status"] = DocStatus(result["status"])
            _docs[doc_id]["chunk_count"] = result["chunk_count"]
            _docs[doc_id]["progress"] = 100
            _docs[doc_id]["stage"] = "done"
    except Exception as e:
        if doc_id in _docs:
            _docs[doc_id]["status"] = DocStatus.FAILED
            _docs[doc_id]["error"] = str(e)
            _docs[doc_id]["stage"] = "error"


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(kb_id: str, file: UploadFile, bg: BackgroundTasks):
    """Upload a document — returns immediately, processes in background."""
    if not file.filename:
        raise HTTPException(400, "No filename")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件类型: {ext}")

    doc_id = str(uuid.uuid4())[:12]
    safe_name = f"{doc_id}_{file.filename}"
    file_path = UPLOAD_DIR / safe_name

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"文件超过 {MAX_UPLOAD_SIZE_MB}MB 限制")

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    _docs[doc_id] = {
        "doc_id": doc_id,
        "kb_id": kb_id,
        "filename": file.filename,
        "file_size": len(content),
        "status": DocStatus.UPLOADED,
        "chunk_count": 0,
        "progress": 0,
        "stage": "uploaded",
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Schedule background ingestion
    bg.add_task(_process_document, doc_id, file_path, file.filename, kb_id)

    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        status=DocStatus.UPLOADED,
        message="文档已上传，后台处理中...",
    )


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, kb_id: str):
    """Delete a document and all its chunks."""
    if doc_id not in _docs:
        raise HTTPException(404, "文档不存在")

    count = await remove_document(doc_id, kb_id)
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
        if d.get("kb_id") == kb_id
    ]


@router.get("/status/{doc_id}")
async def document_status(doc_id: str):
    """Get processing status + progress of a document."""
    if doc_id not in _docs:
        raise HTTPException(404, "文档不存在")
    d = _docs[doc_id]
    return {
        "doc_id": d["doc_id"],
        "filename": d["filename"],
        "status": d["status"].value if isinstance(d["status"], DocStatus) else d["status"],
        "chunk_count": d["chunk_count"],
        "progress": d.get("progress", 0),
        "stage": d.get("stage", ""),
        "error": d.get("error"),
        "created_at": d["created_at"],
    }
