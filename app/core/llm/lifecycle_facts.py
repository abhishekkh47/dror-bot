from dataclasses import dataclass
from typing import Optional

@dataclass
class LifecycleFacts:
    """
    Canonical Lifecycle grounding model

    Represents operational payment state inferred from retrieved chunks

    IMPORTANT: 
    This model represents BUSINESS/OPERATIONAL state,
    not implementation internals.
    """

    # Intent/Transaction creation phase
    intent_created: bool = False

    # Processing lifecycle
    processing_started: bool = False
    processing_failed: bool = False
    processing_completed: bool = False

    # Completion / cancellation outcomes
    transaction_cancelled: bool = False

    # Specialized lifecycle outcomes
    auto_completion_failed: bool = False
    user_cancelled: bool = False

    # Optional metadata
    failure_stage: Optional[str] = None
    final_state: Optional[str] = None

    # deterministic normalization layer
    def infer_derived_state(self):
        """
        Apply deterministic lifecycle interfence rules

        Those rules normalize operational truth before prompt generation
        """

        # Processing implies creation already succeeded 
        if self.processing_started:
            self.intent_created = True
        
        # Auto completion failure implies processing failure
        if self.auto_completion_failed:
            self.processing_started = True
            self.processing_failed = True
            self.failure_stage = "auto-completion"

        # Processing failure that later cancels transaction
        if self.processing_failed and self.transaction_cancelled:
            self.final_state = "cancelled"
        
        # completed processing determines final state
        if self.processing_completed:
            self.final_state = "completed"

        # Generic processing failure
        if self.processing_failed and not self.final_state:
            self.final_state = "failed"