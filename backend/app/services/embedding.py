"""Embedding service via Ollama BGE-M3."""

from __future__ import annotations

import httpx

from ..config import EMBEDDING_MODEL, OLLAMA_BASE_URL


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embed a list of texts. Returns list of vectors."""
    vectors = []
    async with httpx.AsyncClient(timeout=60) as client:
        for text in texts:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": text},
            )
            resp.raise_for_status()
            vectors.append(resp.json()["embedding"])
    return vectors


async def embed_single(text: str) -> list[float]:
    """Embed a single text."""
    results = await embed_texts([text])
    return results[0]


def embed_texts_sync(texts: list[str]) -> list[list[float]]:
    """Synchronous version for use in non-async contexts."""
    import httpx as sync_httpx

    vectors = []
    with sync_httpx.Client(timeout=60) as client:
        for text in texts:
            resp = client.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": text},
            )
            resp.raise_for_status()
            vectors.append(resp.json()["embedding"])
    return vectors
