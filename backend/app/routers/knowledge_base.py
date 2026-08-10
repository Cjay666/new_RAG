"""Knowledge Base management router."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..models.schemas import KBCreate, KBResponse

router = APIRouter(prefix="/api/kb", tags=["knowledge_base"])

# Simple in-memory KB registry
_kbs: dict[str, dict] = {}


@router.post("/", response_model=KBResponse)
async def create_kb(body: KBCreate):
    """Create a new knowledge base."""
    kb_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    _kbs[kb_id] = {
        "kb_id": kb_id,
        "name": body.name,
        "description": body.description,
        "doc_count": 0,
        "created_at": now,
    }
    return KBResponse(**{**_kbs[kb_id], "created_at": now})


@router.get("/", response_model=list[KBResponse])
async def list_kbs():
    """List all knowledge bases."""
    return [
        KBResponse(
            kb_id=v["kb_id"],
            name=v["name"],
            description=v["description"],
            doc_count=v["doc_count"],
            created_at=v["created_at"],
        )
        for v in _kbs.values()
    ]


@router.delete("/{kb_id}")
async def delete_kb(kb_id: str):
    """Delete a knowledge base."""
    if kb_id not in _kbs:
        raise HTTPException(404, "Knowledge base not found")
    del _kbs[kb_id]
    return {"ok": True}
