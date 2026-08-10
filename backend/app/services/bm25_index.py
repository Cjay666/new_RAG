"""BM25 sparse retrieval index — per-knowledge-base indexes."""

from __future__ import annotations

import pickle
from pathlib import Path

from rank_bm25 import BM25Okapi


class BM25IndexManager:
    """Manages BM25 indexes keyed by kb_id."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # In-memory cache: kb_id → (BM25Okapi, list[chunk_meta])
        self._indexes: dict[str, tuple[BM25Okapi, list[dict]]] = {}

    # ── Build ─────────────────────────────────────────────

    def build(self, kb_id: str, chunks: list[dict]) -> None:
        """Build / rebuild BM25 index for a knowledge base.

        IMPORTANT: Merges with existing chunks (by chunk id) so uploading
        a new document doesn't wipe the index of previous documents.
        """
        # Load existing chunks (from memory or disk)
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

        # Merge: new chunks overwrite old ones with same id (upsert)
        for c in chunks:
            existing[c["id"]] = c

        merged = list(existing.values())
        tokenized = [_tokenize(c["chunk_text"]) for c in merged]
        bm25 = BM25Okapi(tokenized)
        self._indexes[kb_id] = (bm25, merged)
        self._save(kb_id)

    # ── Search ────────────────────────────────────────────

    def search(self, kb_id: str, query: str, top_n: int = 100) -> list[dict]:
        """BM25 search. Auto-rebuilds from Milvus if index is missing."""
        if kb_id not in self._indexes:
            self._load(kb_id)
        if kb_id not in self._indexes:
            # Index lost after Docker rebuild → rebuild from Milvus
            self._rebuild_from_milvus(kb_id)
        if kb_id not in self._indexes:
            return []
        bm25, chunks = self._indexes[kb_id]
        tokens = _tokenize(query)
        scores = bm25.get_scores(tokens)
        # Sort by score descending, take top_n
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_n]
        return [
            {**chunks[i], "score": float(score)}
            for i, score in indexed
            if score > 0
        ]

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

    def _delete_file(self, kb_id: str) -> None:
        path = self.data_dir / f"{kb_id}.bm25.pkl"
        if path.exists():
            path.unlink()

    def _rebuild_from_milvus(self, kb_id: str) -> None:
        """Lazy rebuild: read ALL chunks from Milvus and build BM25 from scratch."""
        import sys
        try:
            from ..db.milvus_client import get_all_chunks
            print(f"[BM25] Auto-rebuilding index for kb_id={kb_id} from Milvus...", file=sys.stderr, flush=True)
            all_chunks = get_all_chunks(kb_id)
            print(f"[BM25] Got {len(all_chunks)} chunks from Milvus", file=sys.stderr, flush=True)
            if all_chunks:
                tokenized = [_tokenize(c["chunk_text"]) for c in all_chunks]
                bm25 = BM25Okapi(tokenized)
                self._indexes[kb_id] = (bm25, all_chunks)
                self._save(kb_id)
                print(f"[BM25] Saved index ({len(all_chunks)} chunks) to disk", file=sys.stderr, flush=True)
            else:
                print(f"[BM25] WARNING: No chunks found in Milvus for kb_id={kb_id}", file=sys.stderr, flush=True)
        except Exception as e:
            import traceback
            print(f"[BM25] ERROR rebuilding {kb_id}: {e}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)


# ── Helpers ───────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Simple character-level bigram tokenizer for Chinese text."""
    # For Chinese, character-level unigrams + bigrams work surprisingly well
    chars = list(text.replace(" ", "").replace("\n", ""))
    unigrams = chars
    bigrams = [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
    return unigrams + bigrams
