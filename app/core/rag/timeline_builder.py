def build_lifecycle_timeline(
    lifecycle_facts,
):
    """
    Build explicit operational chronology
    from lifecycle facts.
    """

    timeline = []

    if lifecycle_facts.intent_created:
        timeline.append(
            "Payment intent was created."
        )

    if lifecycle_facts.processing_started:
        timeline.append(
            "Payment processing started."
        )

    if lifecycle_facts.processing_failed:
        timeline.append(
            "Payment processing failed."
        )

    if lifecycle_facts.transaction_cancelled:
        timeline.append(
            "Transaction was cancelled."
        )

    final_state = lifecycle_facts.final_state

    if final_state:
        timeline.append(
            f"Final transaction state: "
            f"{final_state}."
        )

    return timeline