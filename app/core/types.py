from typing import List, Dict, Optional, Union, ClassVar, Set
from pydantic import BaseModel, PrivateAttr

class Step(BaseModel):
    id: str
    type: str # ACTION, INFO, DECISION, OPTIONAL
    title: str
    description: Optional[str] = None
    options: Optional[List[str]] = None
    rag_topic: Optional[str] = None
    next: Optional[Union[str, Dict[str, str]]] = None
    domain: Optional[List[str]] = None

class Flow(BaseModel):
    flow_id: str
    steps: List[Step]

    """
    PrivateAttr tells Pydantic:
    “this field is NOT part of the data model — don't validate or serialize it”
    """
    _step_map: Dict[str, Step] = PrivateAttr(default_factory=dict) # Internal cache for fast lookup and performace optimization

    """
    model_post_init is a special method that is called after the model is initialized automatically
    
    It's inherited from BaseModel — the base class already defines model_post_init as a no-op. 
    When you override it, your version gets called instead.
    
    The __context parameter is None in normal usage (like Flow(**data)). 
    It only carries a value in specific cases like nested validator contexts.
    
    Every instantiation triggers it — whether you do Flow(**data), Flow.model_validate(data),
    or Flow.model_validate_json(json_string), model_post_init always runs after validation.
    """
    # def model_post_init(self, __context) -> None:
    #     self._step_map = {step.id: step for step in self.steps}
    #     self._validate_next_references()

    # def _validate_next_references(self) -> None:
    #     for step in self.steps:
    #         if step.next is None:
    #             continue
    #         if isinstance(step.next, str):
    #             targets = [step.next]
    #         else:
    #             targets = step.next.values()
    #         for target in targets:
    #             if target not in self._step_map:
    #                 raise ValueError(
    #                     f"Step '{step.id}' references non-existent next step '{target}' "
    #                     f"in flow '{self.flow_id}'"
    #                 )

    """
    Problems with above code:
    We're assuming model_post_init always runs
    
    That only works if:
    - we're using Pydantic v2
    - the object is instantiated via model parsing
    If you ever:
    - manually construct objects
    - or mutate steps later
    
    👉 _step_map may become stale if Flow is mutable after load (but in our case, it's not, so we're good)

    Solution:
    - use a property instead of a class variable
    - use a post_init method to validate the next references
    """
    def model_post_init(self, __context) -> None:
        # check duplicate IDs
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate step IDs found in flow")
        
        self._step_map = {step.id: step for step in self.steps}
        self._validate_next_references()
    
    VALID_TYPES: ClassVar[Set[str]] = {"INFO", "DECISION", "ACTION"}
    TERMINAL_STEPS: ClassVar[Set[str]] = {"end_success", "end_failure"}

    def _validate_next_references(self) -> None:
        for step in self.steps:
            step_type = step.type.upper()
            if step_type not in self.VALID_TYPES:
                raise ValueError(f"Invalid step type: {step_type}")

            # Terminal Handling
            if step.next is None:
                if step.id not in self.TERMINAL_STEPS:
                    raise ValueError(f"Step '{step.id}' is not a terminal step and has no next step. It must have a next step")
                continue

            #Validate decision steps
            if step_type == 'DECISION':
                if not step.options:
                    raise ValueError(f"Step '{step.id}' is a decision step but has no options")
                
                if not isinstance(step.next, dict):
                    raise ValueError(f"Step '{step.id}' is a decision step but has no next step. It must have dict 'next'")
                
                if set(step.options) != set(step.next.keys()):
                    raise ValueError(f"Step '{step.id}' has options that do not match the next step IDs")
                
                targets = step.next.values()
            else:
                # Non-decision steps must not have a 'next' field (they should not branch)
                if isinstance(step.next, dict):
                    raise ValueError(f"Step '{step.id}' is a non-decision step but has a 'next' field. It must not have a 'next' field")
                
                targets = [step.next]
            
                # if step.next is None and step_type != 'INFO':
                #     raise ValueError(f"Only INFO steps should terminate the flow")
            
                # targets = [step.next] if step.next else []
            
            # validate references
            for target in targets:
                if target not in self._step_map:
                    raise ValueError(f"Step '{step.id}' references non-existent next step '{target}' in flow '{self.flow_id}'")

    def get_step(self, step_id: str) -> Step:
        step = self._step_map.get(step_id)
        if not step:
            raise Exception(f"Step '{step_id}' not found in flow '{self.flow_id}'")
        return step

class Session(BaseModel):
    session_id: str
    flow_id: str
    current_step: str
    history: List[str]

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