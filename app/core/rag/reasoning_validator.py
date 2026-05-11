def validate_reasoning_consistency(response: str, lifecycle_facts):
    """
    Validate operational reasoning consistency
    against lifecycle facts
    """

    issues = []

    response_lower = response.lower()

    # Invalid chronology:
    # processing started implies
    # intent creation succeeded
    if lifecycle_facts.processing_started:

        invalid_patterns = [
            "intent creation failed",
            "payment intent failed",
            "transaction creation failed",
        ]

        for pattern in invalid_patterns:
            if pattern in response_lower:
                issues.append(
                    f"Invalid chronology: "
                    f"{pattern}"
                )

    # Cancellation must be downstream
    if lifecycle_facts.transaction_cancelled:

        if (
            "cancelled before processing"
            in response_lower
        ):
            issues.append(
                "Cancellation chronology conflict"
            )

    return issues