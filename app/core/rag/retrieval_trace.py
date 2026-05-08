from pydantic import BaseModel
from typing import List, Optional

class RetrievalDecision(BaseModel):
    chunk_id: str
    capability: Optional[str] = None
    lifestyle_stage: Optional[str] = None
    knowledge_type: Optional[str] = None
    importance: Optional[str] = None
    base_score: float
    adjusted_score: float
    included: bool
    exclusion_reason: Optional[str] = None
    score_breakdown: dict = {}

class RetrievalTrace(BaseModel):
    query: str
    step_domain: List[str]
    step_topic: Optional[str] = None
    decisions: List[RetrievalDecision] = []