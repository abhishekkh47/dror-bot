import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.core.flow_engine import FlowEngine
from app.core.flow_loader import FlowLoader
from app.core.llm.qa_pipeline import answer_query, stream_query
from app.core.session_store import SessionStore
from app.core.llm.rag_pipeline import ask_with_context
from app.core.types import QueryRequest, QueryResponse

router = APIRouter()

flow_loader = FlowLoader()
flow_loader.load_flows()

session_store = SessionStore()
engine = FlowEngine(flow_loader, session_store)


@router.post("/flow/start")
def start_flow(flow_id: str):
    session = engine.start_flow(flow_id)
    step = engine.get_current_step(session.session_id)
    return {"session": session, "step": step}


@router.post("/flow/input")
async def process_input(session_id: str, user_input: str):
    try:
        step = engine.process_input(session_id, user_input)
        result = await ask_with_context(query=user_input, step=step)
        return {"step": step, "response": result.response}
    except Exception as e:
        return {"error": str(e)}


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Standard (non-streaming) QA endpoint. Returns complete answer as JSON."""
    return await answer_query(query=request.query, session_id=request.session_id)


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
    async def event_generator():
        async for token in stream_query(request.query):
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