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
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

import os
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "supersecret-dev-key")
api_key_header = APIKeyHeader(name="X-Admin-Api-Key", auto_error=False)

async def get_api_key(api_key: str = Depends(api_key_header)):
    if not api_key or api_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
    return api_key

class SyncDocsRequest(BaseModel):
    files: list[dict]

class FeedbackRequest(BaseModel):
    session_id: str
    rating: str
    comments: str | None = None

@router.post("/feedback")
@limiter.limit("20/minute")
async def submit_feedback(request: Request, feedback_request: FeedbackRequest):
    try:
        session = session_store.get(feedback_request.session_id)
        session.feedback_rating = feedback_request.rating
        session.feedback_comments = feedback_request.comments
        session_store.update(session)
        # Log to separate evaluation table
        session_store.log_evaluation_feedback(
            feedback_request.session_id, 
            feedback_request.rating, 
            feedback_request.comments
        )
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}

@router.post("/admin/sync-docs", dependencies=[Depends(get_api_key)])
async def sync_docs(request: Request, sync_request: SyncDocsRequest):
    try:
        processed_chunks = process_markdown_files(sync_request.files)
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
@limiter.limit("20/minute")
async def start_session(request: Request):
    """Generates a new session and returns the session_id to be used in /query."""
    session = session_store.create_qa_session()
    return {"session_id": session.session_id}


@router.post("/query", response_model=QueryResponse)
@limiter.limit("20/minute")
async def query(request: Request, query_request: QueryRequest):
    """Standard (non-streaming) QA endpoint. Returns complete answer as JSON."""
    safe_query = redact_pii(query_request.query)
    session_id = query_request.session_id
    if not session_id:
        session = session_store.create_qa_session()
        session_id = session.session_id
        
    response = await answer_query(query=safe_query, session_id=session_id, session_store=session_store)
    response.session_id = session_id
    return response


@router.post("/query/stream")
@limiter.limit("20/minute")
async def query_stream(request: Request, query_request: QueryRequest):
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
    safe_query = redact_pii(query_request.query)
    session_id = query_request.session_id
    if not session_id:
        session = session_store.create_qa_session()
        session_id = session.session_id
        
    async def event_generator():
        # Pass the guaranteed session_id down to the stream
        async for token in stream_query(safe_query, session_id=session_id, session_store=session_store):
            # SSE format: each event is "data: <payload>\n\n"
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disables nginx buffering in production
            "X-Session-ID": session_id,  # Expose generated session ID in headers
        },
    )