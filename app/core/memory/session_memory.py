from pydantic import BaseModel
from typing import List, Dict, Optional


class SessionMemory(BaseModel):
    session_id: str
    lifecycle_facts: Dict = {}
    operational_history: List[str] = []
    inferred_conclusions: List[str] = []
    discussed_topics: List[str] = []
    investigation_summary: Dict = {}
    last_response: Optional[str] = None