"""Milvus vector database client — uses MilvusClient (new API)."""

from __future__ import annotations

from pymilvus import MilvusClient

from ..config import MILVUS_COLLECTION, MILVUS_DIM, MILVUS_HOST, MILVUS_PORT

_client = MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")

_SCHEMA = {
    "id": {"dtype": "VARCHAR", "is_primary": True, "max_length": 64},
    "doc_id": {"dtype": "VARCHAR", "max_length": 64},
    "kb_id": {"dtype": "VARCHAR", "max_length": 64},
    "doc_name": {"dtype": "VARCHAR", "max_length": 512},
    "header_path": {"dtype": "VARCHAR", "max_length": 1024},
    "page": {"dtype": "INT64"},
    "chunk_index": {"dtype": "INT64"},
    "total_chunks": {"dtype": "INT64"},
    "parent_id": {"dtype": "VARCHAR", "max_length": 64},
    "chunk_text": {"dtype": "VARCHAR", "max_length": 8192},
    "vector": {"dtype": "FLOAT_VECTOR", "dim": MILVUS_DIM},
}

_INDEX_PARAMS = {
    "metric_type": "COSINE",
    "index_type": "IVF_FLAT",
    "params": {"nlist": 128},
}


def _ensure_collection() -> None:
    """Create collection if it doesn't exist."""
    if not _client.has_collection(MILVUS_COLLECTION):
        _client.create_collection(
            collection_name=MILVUS_COLLECTION,
            schema=_SCHEMA,
            index_params={"field_name": "vector", "index_type": "IVF_FLAT",
                          "metric_type": "COSINE", "params": {"nlist": 128}},
        )
        _client.load_collection(MILVUS_COLLECTION)


def connect() -> None:
    """Ensure collection is ready."""
    _ensure_collection()


def insert_chunks(chunks: list[dict]) -> list[str]:
    """Insert chunks. Each dict = one row. Returns list of primary keys."""
    _ensure_collection()
    rows = [
        {
            "id": c["id"],
            "doc_id": c["doc_id"],
            "kb_id": c["kb_id"],
            "doc_name": c["doc_name"],
            "header_path": c.get("header_path", ""),
            "page": c.get("page", 0),
            "chunk_index": c.get("chunk_index", 0),
            "total_chunks": c.get("total_chunks", 0),
            "parent_id": c.get("parent_id", ""),
            "chunk_text": c["chunk_text"],
            "vector": c["vector"],
        }
        for c in chunks
    ]
    result = _client.insert(collection_name=MILVUS_COLLECTION, data=rows)
    return result.get("ids", [])


def get_all_chunks(kb_id: str = "") -> list[dict]:
    """Get ALL chunks, optionally filtered by kb_id. Used to rebuild BM25."""
    _ensure_collection()
    filter_expr = f'kb_id == "{kb_id}"' if kb_id else 'id != ""'
    results = _client.query(
        collection_name=MILVUS_COLLECTION,
        filter=filter_expr,
        output_fields=[
            "id", "doc_id", "kb_id", "doc_name", "header_path",
            "page", "chunk_index", "total_chunks", "parent_id", "chunk_text",
        ],
        limit=100000,
    )
    return [
        {
            "id": r.get("id"),
            "doc_id": r.get("doc_id", ""),
            "kb_id": r.get("kb_id", ""),
            "doc_name": r.get("doc_name", ""),
            "header_path": r.get("header_path", ""),
            "page": r.get("page", 0),
            "chunk_index": r.get("chunk_index", 0),
            "total_chunks": r.get("total_chunks", 0),
            "parent_id": r.get("parent_id", ""),
            "chunk_text": r.get("chunk_text", ""),
        }
        for r in results
    ]


def delete_by_doc_id(doc_id: str) -> int:
    """Delete all chunks of a document."""
    _ensure_collection()
    result = _client.delete(
        collection_name=MILVUS_COLLECTION,
        filter=f'doc_id == "{doc_id}"',
    )
    return len(result) if isinstance(result, list) else result.get("delete_count", 0)


def search(
    query_vector: list[float],
    kb_id: str,
    top_k: int = 100,
) -> list[dict]:
    """Vector similarity search."""
    _ensure_collection()
    results = _client.search(
        collection_name=MILVUS_COLLECTION,
        data=[query_vector],
        limit=top_k,
        filter=f'kb_id == "{kb_id}"',
        output_fields=[
            "id", "doc_id", "doc_name", "header_path",
            "page", "chunk_index", "total_chunks",
            "parent_id", "chunk_text",
        ],
    )
    # results is list[list[dict]], first dim = per query
    hits = results[0] if results else []
    return [
        {
            "id": h.get("id"),
            "doc_id": h.get("entity", {}).get("doc_id", ""),
            "doc_name": h.get("entity", {}).get("doc_name", ""),
            "header_path": h.get("entity", {}).get("header_path", ""),
            "page": h.get("entity", {}).get("page", 0),
            "chunk_index": h.get("entity", {}).get("chunk_index", 0),
            "total_chunks": h.get("entity", {}).get("total_chunks", 0),
            "parent_id": h.get("entity", {}).get("parent_id", ""),
            "chunk_text": h.get("entity", {}).get("chunk_text", ""),
            "score": h.get("distance", 0),
        }
        for h in hits
    ]
