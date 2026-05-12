def should_retry_retrieval(
    retrieval_confidence,
    lifecycle_drift_issues,
):
    """
    Determine whether retrieval should
    attempt recovery.
    """

    if retrieval_confidence < 0.35:
        return True

    if lifecycle_drift_issues:
        return True

    return False

def build_recovery_strategy():
    """
    Build retrieval recovery strategy.
    """

    return {
        "increase_top_k": True,
        "relax_similarity_threshold": True,
        "allow_adjacent_lifecycle_stages": True,
    }