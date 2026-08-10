"""Milvus vector database client — connection and collection management."""

from __future__ import annotations

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
    connections,
    utility,
)

from ..config import MILVUS_COLLECTION, MILVUS_DIM, MILVUS_HOST, MILVUS_PORT

_FIELDS = [
    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
    FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="kb_id", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="doc_name", dtype=DataType.VARCHAR, max_length=512),
    FieldSchema(name="header_path", dtype=DataType.VARCHAR, max_length=1024),
    FieldSchema(name="page", dtype=DataType.INT64),
    FieldSchema(name="chunk_index", dtype=DataType.INT64),
    FieldSchema(name="total_chunks", dtype=DataType.INT64),
    FieldSchema(name="parent_id", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=8192),
    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=MILVUS_DIM),
]

_INDEX_PARAMS = {
    "metric_type": "COSINE",
    "index_type": "IVF_FLAT",
    "params": {"nlist": 128},
}


def connect() -> None:
    """Establish connection to Milvus."""
    connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)
    _ensure_collection()


def _ensure_collection() -> None:
    """Create collection if it doesn't exist."""
    if not utility.has_collection(MILVUS_COLLECTION):
        schema = CollectionSchema(_FIELDS, description="RAG knowledge chunks")
        col = Collection(MILVUS_COLLECTION, schema)
        col.create_index("vector", _INDEX_PARAMS)
        col.load()


def get_collection() -> Collection:
    """Return the loaded Milvus collection."""
    connect()
    col = Collection(MILVUS_COLLECTION)
    col.load()
    return col


def insert_chunks(chunks: list[dict]) -> list[str]:
    """Insert chunk records into Milvus. Each dict must include all field values."""
    col = get_collection()
    data = [_build_row(c) for c in chunks]
    # Transpose from list-of-dicts to dict-of-lists
    keys = [f.name for f in _FIELDS]
    rows = {k: [d[k] for d in data] for k in keys}
    result = col.insert(rows)
    col.flush()
    return result.primary_keys


def delete_by_doc_id(doc_id: str) -> int:
    """Delete all chunks belonging to a document. Returns delete count."""
    col = get_collection()
    expr = f'doc_id == "{doc_id}"'
    result = col.delete(expr)
    col.flush()
    return result.delete_count if hasattr(result, "delete_count") else 0


def search(
    query_vector: list[float],
    kb_id: str,
    top_k: int = 100,
) -> list[dict]:
    """Vector similarity search within a knowledge base."""
    col = get_collection()
    results = col.search(
        data=[query_vector],
        anns_field="vector",
        param={"metric_type": "COSINE", "params": {"nprobe": 16}},
        limit=top_k,
        expr=f'kb_id == "{kb_id}"',
        output_fields=[
            "id", "doc_id", "doc_name", "header_path",
            "page", "chunk_index", "total_chunks",
            "parent_id", "chunk_text",
        ],
    )
    # results[0] is the list of hits for the first query
    return [
        {
            "id": hit.id,
            "doc_id": hit.entity.get("doc_id"),
            "doc_name": hit.entity.get("doc_name"),
            "header_path": hit.entity.get("header_path"),
            "page": hit.entity.get("page"),
            "chunk_index": hit.entity.get("chunk_index"),
            "total_chunks": hit.entity.get("total_chunks"),
            "parent_id": hit.entity.get("parent_id"),
            "chunk_text": hit.entity.get("chunk_text"),
            "score": hit.score,
        }
        for hit in results[0]
    ]


def _build_row(c: dict) -> dict:
    """Build a single row dict matching the collection schema."""
    return {
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
