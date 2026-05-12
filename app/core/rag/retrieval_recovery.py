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

def apply_recovery_strategy(
    retrieval_options,
    recovery_strategy,
):
    """
    Apply bounded retrieval recovery strategy.
    """

    updated = retrieval_options.copy()

    if recovery_strategy.get(
        "increase_top_k"
    ):
        updated["top_k"] += 3

    if recovery_strategy.get(
        "relax_similarity_threshold"
    ):
        updated[
            "similarity_threshold"
        ] -= 0.05

    return updated