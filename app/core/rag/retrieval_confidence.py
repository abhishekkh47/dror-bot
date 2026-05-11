def compute_retrieval_confidence(
    selected_chunks,
    lifecycle_facts,
):
    """
    Estimate operational confidence
    of retrieved evidence.
    """

    if not selected_chunks:
        return 0.0

    confidence = 0.0

    # Chunk count confidence
    chunk_count = len(selected_chunks)

    if chunk_count >= 5:
        confidence += 0.30
    elif chunk_count >= 3:
        confidence += 0.20
    elif chunk_count >= 2:
        confidence += 0.10

    metadata_list = [
        chunk.get("metadata", {})
        for _, chunk in selected_chunks
    ]

    lifecycle_stages = {
        m.get("lifecycle_stage")
        for m in metadata_list
    }

    knowledge_types = {
        m.get("knowledge_type")
        for m in metadata_list
    }

    # Lifecycle diversity
    if len(lifecycle_stages) >= 2:
        confidence += 0.25

    # Operational reasoning quality
    operational_types = {
        "operational_behavior",
        "troubleshooting",
        "business_rule",
    }

    operational_count = sum(
        1
        for k in knowledge_types
        if k in operational_types
    )

    if operational_count >= 2:
        confidence += 0.25

    # Failure reasoning confidence
    if lifecycle_facts.processing_failed:
        confidence += 0.10

    if lifecycle_facts.transaction_cancelled:
        confidence += 0.10

    return min(confidence, 1.0)