def separate_grounded_and_inferred_reasoning(
    lifecycle_facts,
    operational_evidence,
):
    """
    Separate grounded operational facts
    from inferred conclusions.
    """

    grounded_facts = []

    inferred_conclusions = []

    # Grounded lifecycle facts
    if lifecycle_facts.intent_created:
        grounded_facts.append(
            "Intent creation succeeded"
        )

    if lifecycle_facts.processing_started:
        grounded_facts.append(
            "Processing started"
        )

    if lifecycle_facts.processing_failed:
        grounded_facts.append(
            "Processing failure detected"
        )

    if lifecycle_facts.transaction_cancelled:
        grounded_facts.append(
            "Transaction cancellation detected"
        )

    # Inferred reasoning
    if (
        lifecycle_facts.processing_failed
        and lifecycle_facts.transaction_cancelled
    ):
        inferred_conclusions.append(
            "Cancellation likely occurred "
            "after processing failure"
        )

    if (
        lifecycle_facts.processing_started
        and not lifecycle_facts.processing_failed
        and not lifecycle_facts.final_state
    ):
        inferred_conclusions.append(
            "Transaction may still be "
            "in progress"
        )

    return {
        "grounded_facts":
            grounded_facts,

        "inferred_conclusions":
            inferred_conclusions,
    }