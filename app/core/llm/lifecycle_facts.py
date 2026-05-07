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