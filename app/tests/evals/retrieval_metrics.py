def evaluate_retrieval_quality(
    selected_chunks,
):
    """
    Evaluate retrieval coverage quality.
    """

    metrics = {
        "chunk_count": len(selected_chunks),
        "lifecycle_coverage": False,
        "operational_coverage": False,
        "troubleshooting_coverage": False,
    }

    lifecycle_stages = set()

    knowledge_types = set()

    for _, chunk in selected_chunks:

        metadata = chunk.get("metadata", {})

        stage = metadata.get(
            "lifecycle_stage"
        )

        knowledge_type = metadata.get(
            "knowledge_type"
        )

        if stage:
            lifecycle_stages.add(stage)

        if knowledge_type:
            knowledge_types.add(
                knowledge_type
            )

    # Lifecycle diversity
    if len(lifecycle_stages) >= 2:
        metrics[
            "lifecycle_coverage"
        ] = True

    # Operational reasoning
    if (
        "operational_behavior"
        in knowledge_types
    ):
        metrics[
            "operational_coverage"
        ] = True

    # Troubleshooting evidence
    if (
        "troubleshooting"
        in knowledge_types
    ):
        metrics[
            "troubleshooting_coverage"
        ] = True

    return metrics