import uuid
from .types import Session

class SessionStore:
    def __init__(self):
        self.sessions = {}
    
    def create(self, flow_id: str, first_step: str) -> Session:
        session = Session(
            session_id = str(uuid.uuid4()),
            flow_id = flow_id,
            current_step = first_step,
            history = []
        )
        self.sessions[session.session_id] = session
        return session
    
    def create_qa_session(self, session_id: str = None) -> Session:
        session = Session(
            session_id = session_id or str(uuid.uuid4()),
            history = []
        )
        self.sessions[session.session_id] = session
        return session
    
    def get(self, session_id: str) -> Session:
        if session_id not in self.sessions:
            raise Exception("Session not found")
        return self.sessions[session_id]
    
    def update(self, session: Session):
        self.sessions[session.session_id] = session