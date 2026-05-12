VALID_LIFECYCLE_FLOWS = [
    [
        "intent_created",
        "processing_started",
        "processing_failed",
        "transaction_cancelled",
    ],
    [
        "intent_created",
        "processing_started",
        "completed",
    ],
]


def score_lifecycle_coherence(
    lifecycle_timeline,
):
    """
    Score lifecycle chronology coherence.
    """

    if not lifecycle_timeline:
        return 0

    normalized = [
        item.lower().replace(".", "")
        for item in lifecycle_timeline
    ]
    best_score = 0

    for flow in VALID_LIFECYCLE_FLOWS:
        matches = 0
        for stage in flow:
            if any(
                stage in timeline_item
                for timeline_item in normalized
            ):
                matches += 1

        score = int((matches / len(flow)) * 100)
        best_score = max(best_score, score)

    return best_score