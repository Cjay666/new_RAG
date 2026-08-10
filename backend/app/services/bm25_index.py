"""BM25 sparse retrieval index — per-knowledge-base indexes."""

from __future__ import annotations

import pickle
import sys
from pathlib import Path
from typing import Callable

from rank_bm25 import BM25Okapi


class BM25IndexManager:
    """Manages BM25 indexes keyed by kb_id.

    get_chunks_fn: callable(kb_id) -> list[dict] — reads ALL chunks from Milvus.
    Passed via dependency injection so no lazy relative import is needed.
    """

    def __init__(self, data_dir: Path, get_chunks_fn: Callable[[str], list[dict]] | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._indexes: dict[str, tuple[BM25Okapi, list[dict]]] = {}
        self._get_chunks = get_chunks_fn

    # ── Build ─────────────────────────────────────────────

    def build(self, kb_id: str, chunks: list[dict]) -> None:
        """Build/rebuild BM25 index. Merges with existing chunks (by chunk id)."""
        if not chunks:
            return
        existing: dict[str, dict] = {}
        if kb_id in self._indexes:
            _, old_chunks = self._indexes[kb_id]
            for c in old_chunks:
                existing[c["id"]] = c
        else:
            self._load(kb_id)
            if kb_id in self._indexes:
                _, old_chunks = self._indexes[kb_id]
                for c in old_chunks:
                    existing[c["id"]] = c
        for c in chunks:
            existing[c["id"]] = c
        merged = list(existing.values())
        tokenized = [_tokenize(c["chunk_text"]) for c in merged]
        bm25 = BM25Okapi(tokenized)
        self._indexes[kb_id] = (bm25, merged)
        self._save(kb_id)
        print(f"[BM25] Built index for {kb_id}: {len(merged)} chunks", file=sys.stderr, flush=True)

    # ── Search ────────────────────────────────────────────

    def search(self, kb_id: str, query: str, top_n: int = 100) -> list[dict]:
        """BM25 search. Auto-rebuilds from Milvus if index is missing."""
        if kb_id not in self._indexes:
            self._load(kb_id)
        if kb_id not in self._indexes:
            if self._get_chunks:
                print(f"[BM25] Index missing for {kb_id}, auto-rebuilding from Milvus...", file=sys.stderr, flush=True)
                self._rebuild_from_milvus(kb_id)
            else:
                print(f"[BM25] No get_chunks_fn — cannot auto-rebuild {kb_id}", file=sys.stderr, flush=True)
        if kb_id not in self._indexes:
            print(f"[BM25] Still no index for {kb_id} after rebuild attempt", file=sys.stderr, flush=True)
            return []
        bm25, chunks = self._indexes[kb_id]
        tokens = _tokenize(query)
        scores = bm25.get_scores(tokens)
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_n]
        result = [
            {**chunks[i], "score": float(score)}
            for i, score in indexed
            if score > 0
        ]
        return result

    # ── Rebuild from Milvus ───────────────────────────────

    def rebuild_all_from_milvus(self, kb_id: str = "") -> int:
        """Public method: force-rebuild BM25 from Milvus. Returns chunk count."""
        if not self._get_chunks:
            print("[BM25] No get_chunks_fn available", file=sys.stderr, flush=True)
            return 0
        return self._rebuild_from_milvus(kb_id)

    def _rebuild_from_milvus(self, kb_id: str) -> int:
        """Read all chunks from Milvus and build BM25. Returns chunk count."""
        try:
            all_chunks = self._get_chunks(kb_id)  # type: ignore[misc]
            print(f"[BM25] Got {len(all_chunks)} chunks from Milvus for kb_id={kb_id}", file=sys.stderr, flush=True)
            if all_chunks:
                tokenized = [_tokenize(c["chunk_text"]) for c in all_chunks]
                bm25 = BM25Okapi(tokenized)
                self._indexes[kb_id] = (bm25, all_chunks)
                self._save(kb_id)
                print(f"[BM25] Saved index ({len(all_chunks)} chunks) for {kb_id}", file=sys.stderr, flush=True)
                return len(all_chunks)
            else:
                print(f"[BM25] WARNING: No chunks in Milvus for kb_id={kb_id}", file=sys.stderr, flush=True)
                return 0
        except Exception as e:
            import traceback
            print(f"[BM25] ERROR rebuilding {kb_id}: {e}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            return 0

    # ── Remove ────────────────────────────────────────────

    def remove_doc(self, kb_id: str, doc_id: str) -> None:
        """Remove all chunks of a document from the index and rebuild."""
        if kb_id not in self._indexes:
            self._load(kb_id)
        if kb_id not in self._indexes:
            return
        _, chunks = self._indexes[kb_id]
        filtered = [c for c in chunks if c.get("doc_id") != doc_id]
        if filtered:
            self.build(kb_id, filtered)
        else:
            self._indexes.pop(kb_id, None)
            self._delete_file(kb_id)

    # ── Persistence ───────────────────────────────────────

    def _save(self, kb_id: str) -> None:
        path = self.data_dir / f"{kb_id}.bm25.pkl"
        with open(path, "wb") as f:
            pickle.dump(self._indexes[kb_id], f)

    def _load(self, kb_id: str) -> None:
        path = self.data_dir / f"{kb_id}.bm25.pkl"
        if path.exists():
            with open(path, "rb") as f:
                self._indexes[kb_id] = pickle.load(f)
                print(f"[BM25] Loaded {kb_id} from disk ({len(self._indexes[kb_id][1])} chunks)", file=sys.stderr, flush=True)

    def _delete_file(self, kb_id: str) -> None:
        path = self.data_dir / f"{kb_id}.bm25.pkl"
        if path.exists():
            path.unlink()


# ── Tokenization ───────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Character-level unigrams + bigrams for Chinese text."""
    chars = list(text.replace(" ", "").replace("\n", ""))
    unigrams = chars
    bigrams = [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
    return unigrams + bigrams
