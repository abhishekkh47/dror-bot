def build_response_constraints(retrieval_confidence, lifecycle_facts):
    """
    Build operational response constraints for controlled generation
    """

    constraints = []

    # Base constraints
    constraints.extend([
        "Do not invent operational causes.",
        "Operational conclusions must align with provided evidence.",
        "Do not infer unsupported webhook failures.",
        "Do not assume transport-layer failures.",
        "Do not mix lifecycle stages.",
        "Do not describe intent creation failure after processing started.",
    ])

    # Confidence-aware constraints
    if retrieval_confidence < 0.40:
        constraints.extend([
            "Use cautious phrasing.",
            "Avoid definitive root-cause claims.",
            "State when evidence is incomplete.",
        ])

    # Lifecycle-aware constraints
    if lifecycle_facts.processing_started:
        constraints.append(
            "Intent creation already succeeded."
        )

    if lifecycle_facts.transaction_cancelled:
        constraints.append(
            "Cancellation must be treated as a downstream result."
        )

    return constraints