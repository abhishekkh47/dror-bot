def should_cache_response(
    execution_result,
):
    """
    Determine whether response
    is safe to cache.
    """

    if (
        execution_result.response_mode
        != "normal"
    ):
        return False

    if (
        execution_result.response_reliability_score
        < 75
    ):
        return False

    if (
        execution_result.operational_conflicts
    ):
        return False

    if (
        execution_result.operational_ambiguities
    ):
        return False

    return True