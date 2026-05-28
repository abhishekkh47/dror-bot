ESCALATION_PATTERNS = [
    "missing funds",
    "money not received",
    "account restricted",
    "compliance review",
    "kyc rejected",
    "fraud",
    "chargeback",
    "legal issue",
    "unauthorized transaction",
]


def should_escalate_to_human(
    query,
    execution_result,
):
    """
    Determine whether issue should
    escalate to human support.
    """

    query_lower = query.lower()

    # Sensitive operational flows
    for pattern in ESCALATION_PATTERNS:
        if pattern in query_lower:
            return True

    # Excessive ambiguity
    if execution_result.response_reliability_score < 40:
        return True

    # Heavy operational conflicts
    if len(execution_result.operational_conflicts) >= 2:
        return True

    return False