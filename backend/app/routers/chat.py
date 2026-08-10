"""Chat router — conversation and query endpoints."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..db.session_store import sessions
from ..models.schemas import ChatRequest, ChatResponse, MessageResponse, SessionCreate, SessionResponse
from ..services.pipeline import query_pipeline, query_pipeline_stream

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/session", response_model=SessionResponse)
async def create_session(body: SessionCreate):
    """Create a new chat session."""
    s = sessions.create(body.kb_id, body.title)
    return SessionResponse(
        session_id=s["session_id"],
        kb_id=s["kb_id"],
        title=s["title"],
        created_at=s["created_at"],
        updated_at=s["updated_at"],
    )


@router.get("/sessions/{kb_id}", response_model=list[SessionResponse])
async def list_sessions(kb_id: str):
    """List all sessions for a knowledge base."""
    result = sessions.list_by_kb(kb_id)
    return [
        SessionResponse(
            session_id=s["session_id"],
            kb_id=s["kb_id"],
            title=s["title"],
            created_at=s["created_at"],
            updated_at=s["updated_at"],
        )
        for s in result
    ]


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    sessions.delete(session_id)
    return {"ok": True}


@router.get("/history/{session_id}", response_model=list[MessageResponse])
async def get_history(session_id: str):
    """Get message history of a session."""
    msgs = sessions.get_history(session_id)
    return [
        MessageResponse(
            role=m["role"],
            content=m["content"],
            sources=m.get("sources"),
            timestamp=m["timestamp"],
        )
        for m in msgs
    ]


@router.post("/query", response_model=ChatResponse)
async def query(body: ChatRequest):
    """Send a question and get a full RAG answer (non-streaming)."""
    # Get history
    history_msgs = sessions.get_history(body.session_id)
    history_texts = [
        f"{m['role']}: {m['content']}" for m in history_msgs[-10:]
    ]

    # Save user message
    sessions.add_message(body.session_id, "user", body.question)

    try:
        result = await query_pipeline(
            question=body.question,
            kb_id=body.kb_id,
            session_id=body.session_id,
            history=history_texts,
            top_k=body.top_k,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Save assistant message
    sessions.add_message(
        body.session_id, "assistant", result["answer"],
        sources=[s.model_dump() for s in result["sources"]],
    )

    return ChatResponse(
        session_id=body.session_id,
        answer=result["answer"],
        sources=result["sources"],
        query_strategies_used=result["query_strategies_used"],
    )


@router.post("/query/stream")
async def query_stream(body: ChatRequest):
    """Send a question and get a streaming SSE response."""
    # Save user message
    sessions.add_message(body.session_id, "user", body.question)

    history_msgs = sessions.get_history(body.session_id)
    history_texts = [
        f"{m['role']}: {m['content']}" for m in history_msgs[-10:]
    ]

    async def event_generator():
        full_answer = ""
        try:
            async for token in query_pipeline_stream(
                question=body.question,
                kb_id=body.kb_id,
                session_id=body.session_id,
                history=history_texts,
                top_k=body.top_k,
            ):
                full_answer += token
                yield {"event": "token", "data": token}
        except Exception as e:
            yield {"event": "error", "data": str(e)}

        # Save full answer
        sessions.add_message(body.session_id, "assistant", full_answer)
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())
