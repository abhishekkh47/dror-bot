CONFLICT_RULES = [
    (
        "completed",
        "transaction_cancelled",
    ),
    (
        "processing_started",
        "processing_never_started",
    ),
    (
        "authentication_required",
        "completed",
    ),
]


def detect_operational_conflicts(
    lifecycle_facts,
    operational_evidence,
):
    """
    Detect conflicting operational evidence.
    """

    evidence_text = " ".join(
        operational_evidence
    ).lower()

    detected_states = set()

    # Lifecycle states
    if lifecycle_facts.processing_started:
        detected_states.add(
            "processing_started"
        )

    if lifecycle_facts.transaction_cancelled:
        detected_states.add(
            "transaction_cancelled"
        )

    if lifecycle_facts.final_state:
        detected_states.add(
            lifecycle_facts.final_state.lower()
        )

    # Operational evidence
    if (
        "authentication"
        in evidence_text
    ):
        detected_states.add(
            "authentication_required"
        )

    conflicts = []

    for a, b in CONFLICT_RULES:
        if (
            a in detected_states
            and b in detected_states
        ):
            conflicts.append(
                f"Conflicting operational states: "
                f"{a} vs {b}"
            )

    return conflicts