def determine_response_mode(
    retrieval_confidence,
    reasoning_issues,
    response_reliability_score
):
    """
    Determine operational response mode
    based on confidence and reasoning quality.
    """

    if response_reliability_score < 40:
        return "fallback"

    if response_reliability_score < 60:
        return "clarification"
        
    if retrieval_confidence >= 0.75:
        return "normal"

    if retrieval_confidence >= 0.45:
        return "cautious"

    if retrieval_confidence >= 0.25:
        return "clarification"

    return "fallback"