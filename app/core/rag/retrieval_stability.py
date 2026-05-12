def analyze_retrieval_stability(
    initial_context,
    retry_context,
):
    """
    Analyze retrieval stability between
    retrieval attempts.
    """

    stability_score = 100

    # Chunk overlap
    initial_chunks = {
        chunk["id"]
        for _, chunk in initial_context.get(
            "selected_chunks",
            []
        )
    }

    retry_chunks = {
        chunk["id"]
        for _, chunk in retry_context.get(
            "selected_chunks",
            []
        )
    }

    overlap = len(
        initial_chunks.intersection(
            retry_chunks
        )
    )

    total = max(
        len(initial_chunks),
        1
    )

    overlap_ratio = overlap / total

    stability_score -= int(
        (1 - overlap_ratio) * 40
    )

    # Confidence fluctuation
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

    confidence_delta = abs(
        retry_confidence -
        initial_confidence
    )

    stability_score -= int(
        confidence_delta * 30
    )

    # Lifecycle timeline fluctuation
    initial_timeline = set(
        initial_context.get(
            "lifecycle_timeline",
            []
        )
    )

    retry_timeline = set(
        retry_context.get(
            "lifecycle_timeline",
            []
        )
    )

    timeline_overlap = len(
        initial_timeline.intersection(
            retry_timeline
        )
    )

    timeline_total = max(
        len(initial_timeline),
        1
    )

    timeline_ratio = (
        timeline_overlap /
        timeline_total
    )

    stability_score -= int(
        (1 - timeline_ratio) * 30
    )

    return max(stability_score, 0)