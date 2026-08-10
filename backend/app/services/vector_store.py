"""Vector store manager — orchestrates Milvus + BM25 for document indexing/deletion."""

from __future__ import annotations

from ..config import COARSE_RECALL_TOP_N, UPLOAD_DIR
from ..db import milvus_client as milvus
from .bm25_index import BM25IndexManager
from .embedding import embed_texts

# BM25 stored inside Docker volume (UPLOAD_DIR.parent = /app/data) — survives rebuilds
# get_chunks_fn injected directly (no lazy relative import) for reliable auto-rebuild
_bm25 = BM25IndexManager(
    UPLOAD_DIR.parent / "bm25_indexes",
    get_chunks_fn=milvus.get_all_chunks,
)


async def index_chunks(chunks: list[dict]) -> int:
    """Index a batch of chunks: embed → Milvus + BM25. Returns chunk count."""
    if not chunks:
        return 0
    kb_id = chunks[0]["kb_id"]
    texts = [c["chunk_text"] for c in chunks]
    vectors = await embed_texts(texts)
    for c, v in zip(chunks, vectors):
        c["vector"] = v
    milvus.insert_chunks(chunks)
    _bm25.build(kb_id, chunks)
    return len(chunks)


def delete_document(doc_id: str, kb_id: str) -> int:
    """Delete a document from both Milvus and BM25."""
    count = milvus.delete_by_doc_id(doc_id)
    _bm25.remove_doc(kb_id, doc_id)
    return count


def vector_search(query_vector: list[float], kb_id: str, top_k: int = COARSE_RECALL_TOP_N) -> list[dict]:
    """Dense vector search."""
    return milvus.search(query_vector, kb_id, top_k)


def bm25_search(kb_id: str, query: str, top_n: int = COARSE_RECALL_TOP_N) -> list[dict]:
    """Sparse BM25 search."""
    return _bm25.search(kb_id, query, top_n)


def rebuild_bm25(kb_id: str) -> int:
    """Force-rebuild BM25 index from Milvus. Returns chunk count."""
    return _bm25.rebuild_all_from_milvus(kb_id)
