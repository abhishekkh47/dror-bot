def compute_response_reliability(
    retrieval_confidence,
    lifecycle_coherence_score,
    retrieval_stability_score,
    operational_conflicts,
):
    """
    Compute overall response reliability.
    """

    score = 100

    # Retrieval confidence
    score -= int(
        (1 - retrieval_confidence) * 40
    )

    # Lifecycle coherence
    score -= int(
        (100 - lifecycle_coherence_score)
        * 0.25
    )

    # Retrieval stability
    score -= int(
        (100 - retrieval_stability_score)
        * 0.20
    )

    # Operational conflicts
    score -= (
        len(operational_conflicts) * 15
    )

    return max(score, 0)