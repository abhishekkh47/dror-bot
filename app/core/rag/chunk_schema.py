from pydantic import BaseModel
from typing import List, Optional

class ChunkMetadata(BaseModel):
    """
    Canonical retrieval metadata schema
    """

    # high-level business area
    business_domain: str

    # workflow/api capability
    capability: str

    # operational lifecycle phase
    lifecycle_stage: str

    # State represented by chunk
    operational_state: Optional[str] = None

    # Semantic role of chunk
    knowledge_type: str

    # Transport/integration mechanism
    mechanism: Optional[str] = None

    # Visibility classification
    visibility: str = "public_integrator"

    # Retrieval weighting
    importance: str = "medium"

class RAGChunk(BaseModel):
    """
    Canonical chunk structure
    """
    id: str
    metadata: ChunkMetadata
    tags: List[str] = []
    content: str