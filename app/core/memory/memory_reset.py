from app.core.memory.session_memory import SessionMemory


RESET_TOPICS = [
    "authentication",
    "headers",
    "intent_creation",
]


def should_reset_investigation(
    session_memory,
    current_query,
):
    """
    Detect whether current query
    represents a new investigation.
    """

    query_lower = current_query.lower()

    previous_topics = set(
        session_memory.discussed_topics
    )

    # Explicit reset-topic shift
    for topic in RESET_TOPICS:

        if (
            topic in query_lower
            and topic not in previous_topics
        ):
            return True

    # Empty memory
    if not previous_topics:
        return False

    # string overlap becomes unreliable. So commenting below code
    # No topical overlap
    # overlap = any(
    #     topic in query_lower
    #     for topic in previous_topics
    # )
    # if not overlap:
    #     return True

    return False

def reset_session_memory(
    session_id,
):
    """
    Reset investigation state.
    """

    return SessionMemory(
        session_id=session_id
    )