"""FastAPI main application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import chat, documents, evaluation, knowledge_base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Initialize Milvus connection
    from .db.milvus_client import connect
    connect()
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
