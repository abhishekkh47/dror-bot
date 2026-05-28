from app.core.memory.session_memory import SessionMemory

MEMORY_STORE = {}

def get_session_memory(session_id: str):
    return MEMORY_STORE.get(session_id)


def save_session_memory(
    session_memory: SessionMemory,
):
    MEMORY_STORE[
        session_memory.session_id
    ] = session_memory