from app.core.memory.memory_summarizer import summarize_investigation_state
from app.core.memory.session_memory import (
    SessionMemory
)


def update_session_memory(
    session_memory,
    lifecycle_facts,
    reasoning_breakdown,
    evidence_attribution,
    response,
):
    """
    Update operational memory state.
    """

    # Lifecycle facts
    session_memory.lifecycle_facts.update(
        lifecycle_facts.model_dump()
    )

    # Grounded operational history
    grounded = reasoning_breakdown.get(
        "grounded_facts",
        []
    )

    session_memory.operational_history.extend(
        grounded
    )

    # Inferred reasoning
    inferred = reasoning_breakdown.get(
        "inferred_conclusions",
        []
    )

    session_memory.inferred_conclusions.extend(
        inferred
    )

    # Discussed topics
    topics = evidence_attribution.get(
        "supporting_topics",
        []
    )

    session_memory.discussed_topics.extend(
        topics
    )

    session_memory.last_response = response

    session_memory.investigation_summary = summarize_investigation_state(session_memory)

    return session_memory