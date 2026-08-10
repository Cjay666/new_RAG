"""Knowledge Base management router — with JSON file persistence."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config import PROJECT_ROOT
from ..models.schemas import KBCreate, KBResponse

router = APIRouter(prefix="/api/kb", tags=["knowledge_base"])

_DATA_FILE = Path(PROJECT_ROOT, "data", "knowledge_bases.json")
_kbs: dict[str, dict] = {}


def _load() -> None:
    """Load KBs from JSON file."""
    if _DATA_FILE.exists():
        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                _kbs.update(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass


def _save() -> None:
    """Save KBs to JSON file."""
    _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(_kbs, f, ensure_ascii=False, indent=2)


# Load on startup
_load()


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
    _save()
    return KBResponse(**{**_kbs[kb_id], "created_at": now})


@router.get("/", response_model=list[KBResponse])
async def list_kbs():
    """List all knowledge bases."""
    _load()  # refresh from disk
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
    _save()
    return {"ok": True}
