def score_response_quality(
    response,
    retrieval_confidence,
    reasoning_issues,
    response_mode,
):
    """
    Score operational response quality.
    """

    score = 100

    # Penalize reasoning contradictions
    score -= len(reasoning_issues) * 20

    # Penalize fallback responses slightly
    if response_mode == "fallback":
        score -= 25

    elif response_mode == "clarification":
        score -= 10

    # Penalize weak confidence
    if retrieval_confidence < 0.40:
        score -= 15

    # Detect obvious hallucination phrases
    hallucination_patterns = [
        "webhook failure",
        "socket disconnected",
        "database rollback failure",
    ]

    response_lower = response.lower()

    hallucination_hits = sum(
        1
        for pattern in hallucination_patterns
        if pattern in response_lower
    )

    score -= hallucination_hits * 15

    return max(score, 0)