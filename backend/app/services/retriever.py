"""Hybrid retrieval with RRF fusion — the core retrieval pipeline."""

from __future__ import annotations

from ..config import COARSE_RECALL_TOP_N, COARSE_RERANK_TOP_N, RETRIEVAL_TOP_K
from .embedding import embed_single
from .vector_store import bm25_search, vector_search


async def hybrid_retrieve(
    queries: list[str],
    kb_id: str,
    top_k: int = RETRIEVAL_TOP_K,
) -> tuple[list[dict], dict]:
    """Core retrieval: multi-query × hybrid search → RRF fusion → top results.

    Returns:
        (candidates, trace) — trace has query_count, dense_total, sparse_total,
        unique_after_merge for frontend display.
    """
    rrf: dict[str, float] = {}
    chunk_map: dict[str, dict] = {}
    dense_total = 0
    sparse_total = 0

    for query in queries:
        qv = await embed_single(query)
        dense = vector_search(qv, kb_id, top_k=COARSE_RECALL_TOP_N)
        sparse = bm25_search(kb_id, query, top_n=COARSE_RECALL_TOP_N)
        dense_total += len(dense)
        sparse_total += len(sparse)

        for rank_list, weight in [(dense, 60), (sparse, 60)]:
            for rank, r in enumerate(rank_list, start=1):
                cid = r.get("id", "")
                if not cid:
                    continue
                if cid not in chunk_map:
                    chunk_map[cid] = r
                rrf[cid] = rrf.get(cid, 0) + 1.0 / (weight + rank)

    trace = {
        "query_count": len(queries),
        "dense_total": dense_total,
        "sparse_total": sparse_total,
        "unique_after_merge": len(chunk_map),
        "note": f"每路 Top-{COARSE_RECALL_TOP_N}, RRF(k=60) 融合",
    }

    if not rrf:
        return [], trace

    ranked = sorted(rrf.items(), key=lambda x: x[1], reverse=True)
    top_n = min(COARSE_RERANK_TOP_N, len(ranked))

    candidates = [
        {**chunk_map[cid], "rrf_score": round(score, 4)}
        for cid, score in ranked[:top_n]
        if cid in chunk_map
    ]

    return candidates, trace
