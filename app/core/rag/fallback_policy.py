def determine_response_mode(
    retrieval_confidence,
    reasoning_issues,
):
    """
    Determine operational response mode
    based on confidence and reasoning quality.
    """

    if retrieval_confidence >= 0.75:
        return "normal"

    if retrieval_confidence >= 0.45:
        return "cautious"

    if retrieval_confidence >= 0.25:
        return "clarification"

    return "fallback"