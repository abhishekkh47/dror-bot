def compare_retrieval_quality(
    initial_context,
    retry_context,
):
    """
    Compare retrieval quality between
    initial retrieval and retry retrieval.
    """

    initial_score = 0
    retry_score = 0

    # Confidence comparison
    initial_confidence = (
        initial_context.get(
            "retrieval_confidence",
            0.0
        )
    )

    retry_confidence = (
        retry_context.get(
            "retrieval_confidence",
            0.0
        )
    )

    initial_score += (
        initial_confidence * 100
    )

    retry_score += (
        retry_confidence * 100
    )

    # Chunk coverage
    initial_chunks = len(
        initial_context.get(
            "selected_chunks",
            []
        )
    )

    retry_chunks = len(
        retry_context.get(
            "selected_chunks",
            []
        )
    )

    initial_score += min(
        initial_chunks,
        5
    ) * 5

    retry_score += min(
        retry_chunks,
        5
    ) * 5

    # Lifecycle timeline quality
    initial_timeline = len(
        initial_context.get(
            "lifecycle_timeline",
            []
        )
    )

    retry_timeline = len(
        retry_context.get(
            "lifecycle_timeline",
            []
        )
    )

    initial_score += (
        initial_timeline * 5
    )

    retry_score += (
        retry_timeline * 5
    )

    return retry_score > initial_score