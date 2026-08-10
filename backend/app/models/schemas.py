"""Pydantic models for API request/response."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════

class DocStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXED = "indexed"
    FAILED = "failed"


class QueryStrategy(str, Enum):
    HYDE = "hyde"
    STEP_BACK = "step_back"
    DEHYDRATE = "dehydrate"


# ═══════════════════════════════════════════════════════════
# Knowledge Base
# ═══════════════════════════════════════════════════════════

class KBCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    description: str = Field("", max_length=500)


class KBResponse(BaseModel):
    kb_id: str
    name: str
    description: str
    doc_count: int
    created_at: datetime


# ═══════════════════════════════════════════════════════════
# Document
# ═══════════════════════════════════════════════════════════

class DocumentResponse(BaseModel):
    doc_id: str
    kb_id: str
    filename: str
    file_size: int
    status: DocStatus
    chunk_count: int = 0
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    status: DocStatus
    message: str


# ═══════════════════════════════════════════════════════════
# Chat
# ═══════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    kb_id: str = Field(..., description="知识库ID")
    question: str = Field(..., min_length=1, max_length=5000)
    top_k: int = Field(5, ge=1, le=20)


class SourceChunk(BaseModel):
    chunk_id: str
    doc_name: str
    header_path: str
    page: Optional[int] = None
    content: str
    relevance_score: float


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[SourceChunk]
    query_strategies_used: list[QueryStrategy] = []
    trace: Optional[dict] = None


# ═══════════════════════════════════════════════════════════
# Session
# ═══════════════════════════════════════════════════════════

class SessionCreate(BaseModel):
    kb_id: str
    title: str = "新会话"


class SessionResponse(BaseModel):
    session_id: str
    kb_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    sources: Optional[list[SourceChunk]] = None
    trace: Optional[dict] = None
    timestamp: datetime


# ═══════════════════════════════════════════════════════════
# Evaluation
# ═══════════════════════════════════════════════════════════

class EvalRequest(BaseModel):
    kb_id: str
    test_queries: list[str] = Field(..., min_length=1, max_length=50)


class EvalMetrics(BaseModel):
    context_precision: float
    context_recall: float
    faithfulness: float
    answer_relevancy: float


class EvalResponse(BaseModel):
    eval_id: str
    kb_id: str
    metrics: EvalMetrics
    query_count: int
    detail: Optional[dict] = None
    created_at: datetime


# ═══════════════════════════════════════════════════════════
# Experiment
# ═══════════════════════════════════════════════════════════

class ExperimentConfig(BaseModel):
    chunk_size: int = 600
    chunk_overlap: int = 120
    top_k: int = 5
    use_hyde: bool = True
    use_step_back: bool = True
    use_dehydrate: bool = True
    use_reranker: bool = True


class ExperimentCreate(BaseModel):
    kb_id: str
    name: str
    configs: list[ExperimentConfig] = Field(..., min_length=1, max_length=5)


class ExperimentResult(BaseModel):
    config: ExperimentConfig
    metrics: EvalMetrics


class ExperimentResponse(BaseModel):
    experiment_id: str
    name: str
    kb_id: str
    results: list[ExperimentResult]
    created_at: datetime
