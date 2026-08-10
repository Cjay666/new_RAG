"""Reranker — BGE-Reranker v2-m3 via Ollama for fine-grained relevance scoring."""

from __future__ import annotations

import httpx

from ..config import OLLAMA_BASE_URL, RERANKER_MODEL, RETRIEVAL_TOP_K

_RERANK_PROMPT = """判断以下文档片段是否与用户问题相关。

用户问题：{question}

文档片段：
{context}

请给出1-10的相关性评分(10=完全相关)，只返回数字。"""


async def rerank(
    question: str,
    chunks: list[dict],
    top_k: int = RETRIEVAL_TOP_K,
) -> list[dict]:
    """Re-rank chunks using BGE-Reranker cross-encoder.

    Args:
        question: User's original question
        chunks: Candidate chunks from RRF coarse ranking (~30 items)
        top_k: How many to keep after fine ranking

    Returns:
        Re-ranked chunks with updated score field
    """
    if not chunks:
        return []
    if len(chunks) <= top_k:
        return chunks

    # Score each chunk
    async with httpx.AsyncClient(timeout=120) as client:
        for chunk in chunks:
            score = await _score_single(client, question, chunk["chunk_text"])
            chunk["rerank_score"] = score

    # Sort by rerank score descending
    chunks.sort(key=lambda c: c.get("rerank_score", 0), reverse=True)
    return chunks[:top_k]


async def _score_single(
    client: httpx.AsyncClient,
    question: str,
    context: str,
) -> float:
    """Get relevance score from reranker for a single chunk."""
    # Truncate context to avoid overwhelming the model
    ctx_snippet = context[:1500]
    prompt = _RERANK_PROMPT.format(question=question, context=ctx_snippet)

    try:
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": RERANKER_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 10},
            },
        )
        resp.raise_for_status()
        raw = resp.json()["response"].strip()
        # Parse score
        score = float(raw)
        return max(1.0, min(10.0, score)) / 10.0  # Normalize to 0-1
    except (ValueError, KeyError, httpx.HTTPError):
        return 0.5  # Default neutral score on error
