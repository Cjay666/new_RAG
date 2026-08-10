"""Main RAG pipeline — orchestrates the full query → retrieval → generation flow."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator, Optional

from ..models.schemas import QueryStrategy, SourceChunk
from .chunker import chunk_document
from .document_loader import load_document
from .embedding import embed_single
from .generator import generate_answer
from .query_rewriter import dehydrate, hyde_generate, step_back_decompose
from .reranker import rerank
from .retriever import hybrid_retrieve
from .router import route_query
from .vector_store import delete_document as delete_doc_from_store
from .vector_store import index_chunks


# ══════════════════════════════════════════════════════════
# Document Ingestion
# ══════════════════════════════════════════════════════════

async def ingest_document(
    file_path,
    original_filename: str,
    kb_id: str,
    chunk_size: int = 600,
    chunk_overlap: int = 120,
    progress_callback=None,
) -> dict:
    """Full document ingestion pipeline with progress reporting.

    progress_callback(status, progress_pct) called at each stage.
    """

    async def _report(status: str, pct: int):
        if progress_callback:
            await progress_callback(status, pct)

    doc_id = str(uuid.uuid4())[:12]
    await _report("parsing", 10)

    # Step 1: Load document → Markdown
    markdown_text = await load_document(file_path, original_filename)
    await _report("chunking", 30)

    # Step 2: Chunk
    chunks = chunk_document(
        markdown_text=markdown_text,
        doc_name=original_filename,
        kb_id=kb_id,
        doc_id=doc_id,
    )

    if not chunks:
        return {"doc_id": doc_id, "chunk_count": 0, "status": "failed"}

    # Step 3: Convert to dicts for indexing
    chunk_dicts = [
        {
            "id": c.id,
            "doc_id": c.doc_id,
            "kb_id": c.kb_id,
            "doc_name": c.doc_name,
            "header_path": c.header_path,
            "page": c.page,
            "chunk_index": c.chunk_index,
            "total_chunks": c.total_chunks,
            "parent_id": c.parent_id,
            "chunk_text": c.text,
        }
        for c in chunks
    ]

    total = len(chunk_dicts)
    await _report("embedding", 40)

    # Step 4: Embed in batches, report progress
    from .embedding import embed_texts
    texts = [c["chunk_text"] for c in chunk_dicts]
    vectors = await embed_texts(texts)

    for c, v in zip(chunk_dicts, vectors):
        c["vector"] = v

    await _report("indexing", 85)

    # Step 5: Index into Milvus & BM25
    count = await index_chunks(chunk_dicts)
    await _report("indexed", 100)

    return {
        "doc_id": doc_id,
        "chunk_count": count,
        "status": "indexed" if count > 0 else "failed",
    }


async def remove_document(doc_id: str, kb_id: str) -> int:
    """Delete a document and all its chunks."""
    return delete_doc_from_store(doc_id, kb_id)


# ══════════════════════════════════════════════════════════
# Query Pipeline (P1)
# ══════════════════════════════════════════════════════════

async def query_pipeline(
    question: str,
    kb_id: str,
    session_id: str,
    history: list[str] | None = None,
    top_k: int = 5,
) -> dict:
    """Full RAG query pipeline: route → rewrite → retrieve → rerank → generate.

    Returns:
        dict: {answer, sources, strategies_used}
    """
    strategies_used: list[QueryStrategy] = []

    # ── Step 1: Route ────────────────────────────────────
    strategies = await route_query(question, history)

    # ── Step 2: Rewrite (if needed) ──────────────────────
    queries = [question]  # Always keep original

    if "direct" not in strategies or len(strategies) > 1:
        for strat in strategies:
            try:
                if strat == "hyde":
                    hyp = await hyde_generate(question)
                    queries.append(hyp)
                    strategies_used.append(QueryStrategy.HYDE)
                elif strat == "step_back":
                    subs = await step_back_decompose(question)
                    queries.extend(subs)
                    strategies_used.append(QueryStrategy.STEP_BACK)
                elif strat == "dehydrate":
                    clean = await dehydrate(question, history)
                    if clean != question:
                        queries.append(clean)
                        strategies_used.append(QueryStrategy.DEHYDRATE)
            except Exception:
                pass  # If a strategy fails, continue with others

    # Deduplicate queries
    queries = list(dict.fromkeys(queries))

    # ── Step 3: Hybrid retrieve + RRF ────────────────────
    candidates = await hybrid_retrieve(queries, kb_id)

    # ── Step 4: Rerank (fine ranking) ────────────────────
    if len(candidates) > top_k:
        candidates = await rerank(question, candidates, top_k)
    else:
        candidates = candidates[:top_k]

    # ── Step 5: Small-to-Big — fetch parent chunks ────────
    contexts = await _resolve_parents(candidates, kb_id)

    # ── Step 6: Generate answer ──────────────────────────
    answer = await generate_answer(question, contexts, history=None)

    # Build source list
    sources = [
        SourceChunk(
            chunk_id=c["id"],
            doc_name=c.get("doc_name", ""),
            header_path=c.get("header_path", ""),
            page=c.get("page"),
            content=c.get("chunk_text", "")[:300],
            relevance_score=c.get("rerank_score", c.get("rrf_score", 0)),
        )
        for c in contexts
    ]

    return {
        "session_id": session_id,
        "answer": answer,
        "sources": sources,
        "query_strategies_used": strategies_used,
    }


async def query_pipeline_stream(
    question: str,
    kb_id: str,
    session_id: str,
    history: list[str] | None = None,
    top_k: int = 5,
) -> AsyncGenerator[str, None]:
    """Streaming version — yields SSE tokens one at a time."""
    # Same pipeline but stream the generation
    strategies = await route_query(question, history)

    queries = [question]
    for strat in strategies:
        try:
            if strat == "hyde":
                queries.append(await hyde_generate(question))
            elif strat == "step_back":
                queries.extend(await step_back_decompose(question))
            elif strat == "dehydrate":
                clean = await dehydrate(question, history)
                if clean != question:
                    queries.append(clean)
        except Exception:
            pass

    queries = list(dict.fromkeys(queries))
    candidates = await hybrid_retrieve(queries, kb_id)

    if len(candidates) > top_k:
        candidates = await rerank(question, candidates, top_k)
    else:
        candidates = candidates[:top_k]

    contexts = await _resolve_parents(candidates, kb_id)

    # Stream the generation
    stream = await generate_answer(question, contexts, history=None, stream=True)
    yield "[SOURCES]"
    yield "\n".join([
        f"{c.get('doc_name','')} > {c.get('header_path','')}"
        for c in contexts
    ])
    yield "[/SOURCES]\n"

    async for token in stream:
        yield token


# ══════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════

async def _resolve_parents(candidates: list[dict], kb_id: str) -> list[dict]:
    """Small-to-Big: replace child chunks with their parent contexts."""
    # Track unique parent IDs to avoid duplicates
    seen_parents: set[str] = set()
    resolved: list[dict] = []

    for c in candidates:
        parent_id = c.get("parent_id", "")
        if parent_id and parent_id not in seen_parents:
            seen_parents.add(parent_id)
            # The parent contains the full section text
            # For now, use the child chunk itself as the parent context
            # In full implementation: fetch parent from Milvus by parent_id
            resolved.append(c)
        elif not parent_id and c["id"] not in seen_parents:
            seen_parents.add(c["id"])
            resolved.append(c)

    return resolved
