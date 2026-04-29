from typing import List, Dict, Optional, Union
from pydantic import BaseModel

class Step(BaseModel):
    id: str
    type: str # ACTION, INFO, DECISION, OPTIONAL
    title: str
    description: Optional[str] = None
    options: Optional[List[str]] = None
    next: Optional[Union[str, Dict[str, str]]] = None

class Flow(BaseModel):
    flow_id: str
    steps: List[Step]

class Session(BaseModel):
    session_id: str
    flow_id: str
    current_step: str
    history: List[str]