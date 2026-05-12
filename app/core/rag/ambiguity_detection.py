AMBIGUOUS_PATTERNS = [
    (
        "authentication",
        "processing",
    ),
    (
        "timeout",
        "cancellation",
    ),
    (
        "network",
        "processing",
    ),
]


def detect_operational_ambiguity(
    operational_evidence,
    operational_conflicts,
):
    """
    Detect unresolved operational ambiguity.
    """

    if operational_conflicts:
        return []

    evidence_text = " ".join(
        operational_evidence
    ).lower()

    ambiguities = []

    for a, b in AMBIGUOUS_PATTERNS:

        if (
            a in evidence_text
            and b in evidence_text
        ):
            ambiguities.append(
                f"Ambiguous operational cause: "
                f"{a} vs {b}"
            )

    return ambiguities