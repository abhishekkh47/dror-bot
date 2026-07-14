from typing import List, Dict, Optional, Union, ClassVar, Set
from pydantic import BaseModel, PrivateAttr



class Session(BaseModel):
    session_id: str
    history: List[str]
    feedback_rating: Optional[str] = None
    feedback_comments: Optional[str] = None

class ExecutionResult(BaseModel):
    response: str
    retrieval_confidence: float
    response_mode: str
    reasoning_issues: List[str]
    quality_score: int
    selected_chunks: list
    lifecycle_drift_issues: list[str]
    retrieval_recovery_eligible: bool
    retry_attempted: bool = False
    initial_retrieval_confidence: float = 0.0
    final_retrieval_confidence: float = 0.0
    retry_confidence_delta: float = 0.0
    retrieval_stability_score: int = 100
    lifecycle_coherence_score: int = 0
    operational_conflicts: list[str] = []
    response_reliability_score: int = 100
    evidence_attribution: dict = {}
    reasoning_breakdown: dict = {}
    operational_ambiguities: list[str] = []
    human_escalation_required: bool = False

class SourceCitation(BaseModel):
    file_name: str
    snippet: str
    relevance_score: float

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    domain: str
    mode: str
    session_id: str
    confidence: float = 0.0
    citations: List[SourceCitation] = []