"""Hybrid retrieval with RRF fusion — the core retrieval pipeline."""

from __future__ import annotations

from ..config import COARSE_RECALL_TOP_N, COARSE_RERANK_TOP_N, RETRIEVAL_TOP_K
from .embedding import embed_single
from .vector_store import bm25_search, vector_search


async def hybrid_retrieve(
    queries: list[str],
    kb_id: str,
    top_k: int = RETRIEVAL_TOP_K,
) -> list[dict]:
    """Core retrieval: multi-query × hybrid search → RRF fusion → top results.

    Args:
        queries: Query strings (original + rewritten variants)
        kb_id: Knowledge base ID
        top_k: Final candidate count after RRF

    Returns:
        List of chunk dicts with id, chunk_text, doc_name, header_path, page, score (rrf)
    """
    # ── Step 1: Coarse recall ───────────────────────────
    all_candidates: dict[str, dict] = {}

    for query in queries:
        qv = await embed_single(query)
        dense = vector_search(qv, kb_id, top_k=COARSE_RECALL_TOP_N)
        sparse = bm25_search(kb_id, query, top_n=COARSE_RECALL_TOP_N)
        for r in dense + sparse:
            cid = r.get("id", "")
            if cid and cid not in all_candidates:
                all_candidates[cid] = r

    candidates = list(all_candidates.values())
    if not candidates:
        return []

    # ── Step 2: RRF coarse ranking ──────────────────────
    rrf_scores = await _compute_rrf(queries, candidates, kb_id)
    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    top_n = min(COARSE_RERANK_TOP_N, len(ranked))
    candidate_lookup = {c["id"]: c for c in candidates}

    return [
        {**candidate_lookup[cid], "rrf_score": score}
        for cid, score in ranked[:top_n]
        if cid in candidate_lookup
    ]


async def _compute_rrf(
    queries: list[str],
    candidates: list[dict],
    kb_id: str,
    k: int = 60,
) -> dict[str, float]:
    """Compute RRF fusion scores: Σ 1/(k + rank) across all retrieval lists."""
    rrf: dict[str, float] = {c["id"]: 0.0 for c in candidates}
    candidate_ids = set(rrf.keys())

    for query in queries:
        qv = await embed_single(query)
        dense = vector_search(qv, kb_id, top_k=COARSE_RECALL_TOP_N)
        sparse = bm25_search(kb_id, query, top_n=COARSE_RECALL_TOP_N)

        for rank_list in [dense, sparse]:
            for rank, r in enumerate(rank_list, start=1):
                cid = r.get("id", "")
                if cid in candidate_ids:
                    rrf[cid] += 1.0 / (k + rank)

    return rrf
