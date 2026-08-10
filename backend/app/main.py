"""FastAPI main application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import chat, documents, evaluation, knowledge_base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    import sys
    from .db.milvus_client import connect
    connect()

    # Rebuild BM25 indexes from Milvus (they may have been lost during container rebuild)
    try:
        from .services.vector_store import _bm25
        from .db.milvus_client import get_all_chunks
        all_chunks = get_all_chunks("")
        kb_ids = list(dict.fromkeys(c["kb_id"] for c in all_chunks if c.get("kb_id")))
        for kb_id in kb_ids:
            n = _bm25.rebuild_all_from_milvus(kb_id)
            print(f"[Startup] BM25 rebuilt for {kb_id}: {n} chunks", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[Startup] BM25 pre-rebuild skipped: {e}", file=sys.stderr, flush=True)

    yield


app = FastAPI(
    title="RAG 智能问答系统",
    description="基于 RAG 的智能知识库问答系统 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(knowledge_base.router)
app.include_router(evaluation.router)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/kb/{kb_id}/bm25-rebuild")
async def bm25_rebuild(kb_id: str):
    """Manually rebuild BM25 index from Milvus. Returns chunk count."""
    from .services.vector_store import rebuild_bm25
    n = rebuild_bm25(kb_id)
    return {"kb_id": kb_id, "bm25_chunks": n, "ok": n > 0}
