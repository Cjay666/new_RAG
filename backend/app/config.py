"""Application configuration — all values from environment variables."""

import os
from pathlib import Path

# ── Project root ──────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ── LLM: DeepSeek ─────────────────────────────────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ── MinerU API ────────────────────────────────────────────
MINERU_API_KEY = os.getenv("MINERU_API_KEY", "")
MINERU_BASE_URL = os.getenv("MINERU_BASE_URL", "https://mineru.net/api/v4")

# ── Ollama ────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "bge-reranker-v2-m3")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:3b")

# ── Milvus ────────────────────────────────────────────────
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "rag_knowledge")
MILVUS_DIM = 1024  # BGE-M3 向量维度

# ── Chunking ──────────────────────────────────────────────
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "600"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))

# ── Retrieval ─────────────────────────────────────────────
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))
RRF_K = 60
COARSE_RECALL_TOP_N = 100
COARSE_RERANK_TOP_N = 30

# ── Upload ────────────────────────────────────────────────
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ── Allowed upload extensions ─────────────────────────────
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt",
    ".xlsx", ".xls", ".txt", ".md", ".csv",
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff",
}
