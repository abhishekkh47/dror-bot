def compute_chunk_selection_score(chunk, lifecycle_facts):
    """
    Score chunk usefulness for operational lifecycle reasoning
    """

    metadata = chunk.get("metadata", {})
    score = 0

    lifecycle_stage = metadata.get("lifecycle_stage")

    knowledge_type = metadata.get("knowledge_type")

    operational_state = metadata.get("operational_state")

    # Strongly prefer operational behavior
    if knowledge_type == "operational_behavior":
        score += 3

    # Prefer troubleshooting guidance
    if knowledge_type == "troubleshooting":
        score += 2

    # Suppress transport details
    if knowledge_type == "transport_behavior":
        score -= 3

    # Lifecycle alignment
    if (
        lifecycle_facts.final_state == "cancelled"
        and lifecycle_stage == "cancellation"
    ):
        score += 4

    if (
        lifecycle_facts.processing_failed
        and operational_state == "failed"
    ):
        score += 3

    if (
        lifecycle_facts.processing_completed
        and operational_state == "completed"
    ):
        score += 2

    return score