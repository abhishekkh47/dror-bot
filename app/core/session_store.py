import sqlite3
import uuid
import os
from .types import Session

class SessionStore:
    def __init__(self, db_path="app/data/sessions.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    data TEXT
                )
            ''')
            
    def create_qa_session(self, session_id: str = None) -> Session:
        session = Session(
            session_id = session_id or str(uuid.uuid4()),
            history = []
        )
        self.update(session)
        return session
        
    def get(self, session_id: str) -> Session:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT data FROM sessions WHERE session_id = ?', (session_id,))
            row = cursor.fetchone()
            if not row:
                raise Exception("Session not found")
            return Session.model_validate_json(row[0])
            
    def update(self, session: Session):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO sessions (session_id, data) VALUES (?, ?)',
                (session.session_id, session.model_dump_json())
            )