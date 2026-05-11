from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class RetrievalDiagnostic(BaseModel):
    failed_stage: Optional[str] = None
    reason: Optional[str] = None
    # chunk_counts: dict = {} => This is mutable
    chunk_counts: dict = Field(default_factory=dict) # This is immutable



class RetrievalStage(str, Enum):
    VECTOR_SEARCH = "vector_search"
    STRUCTURED_FILTERING = "structured_filtering"
    NOISE_SUPPRESSION = "noise_suppression"
    LIFECYCLE_SELECTION = "lifecycle_selection"
    LLM_SELECTION = "llm_selection"
    DISTILLATION = "distillation"