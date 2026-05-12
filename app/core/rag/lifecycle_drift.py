def detect_lifecycle_drift(
    lifecycle_facts,
    selected_chunks,
):
    """
    Detect contradictory lifecycle evidence
    across retrieved chunks.
    """

    issues = []

    # Invalid chronology:
    # processing started implies
    # intent creation succeeded
    if (
        lifecycle_facts.processing_started
        and not lifecycle_facts.intent_created
    ):
        issues.append(
            "Processing started without "
            "intent creation."
        )

    # Cancellation before processing
    if (
        lifecycle_facts.transaction_cancelled
        and not lifecycle_facts.processing_started
    ):
        issues.append(
            "Cancellation occurred without "
            "processing evidence."
        )

    # Detect conflicting lifecycle stages
    lifecycle_stages = set()

    for _, chunk in selected_chunks:

        metadata = chunk.get("metadata", {})

        stage = metadata.get(
            "lifecycle_stage"
        )

        if stage:
            lifecycle_stages.add(stage)

    contradictory_pairs = [
        (
            "intent_creation_failed",
            "processing"
        ),
    ]

    for a, b in contradictory_pairs:

        if (
            a in lifecycle_stages
            and b in lifecycle_stages
        ):
            issues.append(
                f"Conflicting lifecycle stages: "
                f"{a} vs {b}"
            )

    return issues