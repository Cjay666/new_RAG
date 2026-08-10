"""In-memory session store — single user, multi-session per KB."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config import PROJECT_ROOT

_DATA_DIR = Path(PROJECT_ROOT, "data", "sessions")
_DATA_DIR.mkdir(parents=True, exist_ok=True)


class SessionStore:
    """Simple JSON-file-backed session store."""

    def __init__(self):
        self._cache: dict[str, dict] = {}
        self._load_all()

    # ── CRUD ─────────────────────────────────────────────

    def create(self, kb_id: str, title: str = "新会话") -> dict:
        sid = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
        session = {
            "session_id": sid,
            "kb_id": kb_id,
            "title": title,
            "messages": [],
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        self._cache[sid] = session
        self._save(sid)
        return session

    def get(self, session_id: str) -> dict | None:
        if session_id not in self._cache:
            self._load(session_id)
        return self._cache.get(session_id)

    def list_by_kb(self, kb_id: str) -> list[dict]:
        return [
            {"session_id": s["session_id"], "kb_id": s["kb_id"],
             "title": s["title"], "created_at": s["created_at"],
             "updated_at": s["updated_at"]}
            for s in self._cache.values()
            if s["kb_id"] == kb_id
        ]

    def add_message(self, session_id: str, role: str, content: str,
                    sources: list | None = None) -> None:
        session = self.get(session_id)
        if not session:
            return
        session["messages"].append({
            "role": role,
            "content": content,
            "sources": sources,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        session["updated_at"] = datetime.now(timezone.utc).isoformat()
        # Auto-title from first user message
        if role == "user" and session["title"] == "新会话":
            session["title"] = content[:30]
        self._save(session_id)

    def get_history(self, session_id: str) -> list[dict]:
        session = self.get(session_id)
        if not session:
            return []
        return session.get("messages", [])

    def delete(self, session_id: str) -> None:
        self._cache.pop(session_id, None)
        path = _DATA_DIR / f"{session_id}.json"
        if path.exists():
            path.unlink()

    # ── Persistence ───────────────────────────────────────

    def _save(self, session_id: str) -> None:
        if session_id in self._cache:
            path = _DATA_DIR / f"{session_id}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._cache[session_id], f, ensure_ascii=False, indent=2)

    def _load(self, session_id: str) -> None:
        path = _DATA_DIR / f"{session_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                self._cache[session_id] = json.load(f)

    def _load_all(self) -> None:
        for path in _DATA_DIR.glob("*.json"):
            sid = path.stem
            if sid not in self._cache:
                self._load(sid)


# Global singleton
sessions = SessionStore()
