from fastapi import APIRouter
from app.core.flow_engine import FlowEngine
from app.core.flow_loader import FlowLoader
from app.core.session_store import SessionStore
from app.core.llm.rag_pipeline import ask_with_context

router = APIRouter()

flow_loader = FlowLoader()
flow_loader.load_flows()

session_store = SessionStore()
engine = FlowEngine(flow_loader, session_store)

@router.post("/flow/start")
def start_flow(flow_id: str):
    session = engine.start_flow(flow_id)
    step = engine.get_current_step(session.session_id)
    return { "session": session, "step": step }

@router.post("/flow/input")
def process_input(session_id: str, user_input: str):
    try:
        step = engine.process_input(session_id, user_input)

        result = ask_with_context(
            query=user_input,
            step=step
        )

        return { "step": step, "response": result.response }
    except Exception as e:
        return { "error": str(e) }