import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.core.llm.qa_pipeline import answer_query, stream_query
from app.core.session_store import SessionStore
from app.core.types import QueryRequest, QueryResponse

from pydantic import BaseModel
from app.core.rag.ingestion_service import process_markdown_files
from app.core.security.pii_redactor import redact_pii
import traceback

router = APIRouter()

class SyncDocsRequest(BaseModel):
    files: list[dict]

class FeedbackRequest(BaseModel):
    session_id: str
    rating: str
    comments: str | None = None

@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    try:
        session = session_store.get(request.session_id)
        session.feedback_rating = request.rating
        session.feedback_comments = request.comments
        session_store.update(session)
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}

@router.post("/admin/sync-docs")
async def sync_docs(request: SyncDocsRequest):
    try:
        processed_chunks = process_markdown_files(request.files)
        from app.core.llm.retriever import store, KNOWLEDGE_FILES
        import os
        if "app/data/knowledge_base/dynamic_ingestion.json" not in KNOWLEDGE_FILES:
            KNOWLEDGE_FILES.append("app/data/knowledge_base/dynamic_ingestion.json")
        existing_files = [f for f in KNOWLEDGE_FILES if os.path.exists(f)]
        store.reload(existing_files)
        return {"status": "success", "chunks_processed": len(processed_chunks)}
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

session_store = SessionStore()
class SessionStartResponse(BaseModel):
    session_id: str

@router.post("/session/start", response_model=SessionStartResponse)
async def start_session():
    """Generates a new session and returns the session_id to be used in /query."""
    session = session_store.create_qa_session()
    return {"session_id": session.session_id}


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Standard (non-streaming) QA endpoint. Returns complete answer as JSON."""
    safe_query = redact_pii(request.query)
    return await answer_query(query=safe_query, session_id=request.session_id, session_store=session_store)


@router.post("/query/stream")
async def query_stream(request: QueryRequest):
    """
    Streaming QA endpoint using Server-Sent Events (SSE).

    Each SSE event carries one token. The stream ends with a [DONE] event.

    Client usage (JavaScript):
        const es = new EventSource('/query/stream');  // or use fetch with ReadableStream
        // POST body: {"query": "...", "session_id": "default"}

    curl usage:
        curl -s -X POST http://localhost:8000/query/stream \\
          -H "Content-Type: application/json" \\
          -d '{"query": "how do I verify webhook signatures?"}'
    """
    safe_query = redact_pii(request.query)
    
    async def event_generator():
        async for token in stream_query(safe_query, session_id=request.session_id, session_store=session_store):
            # SSE format: each event is "data: <payload>\n\n"
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disables nginx buffering in production
        },
    )