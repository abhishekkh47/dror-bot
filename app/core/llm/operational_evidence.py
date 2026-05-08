from app.core.llm.lifecycle_facts import LifecycleFacts


def build_operational_evidence(
    facts: LifecycleFacts
):
    """
    Convert normalized lifecycle facts into
    explicit operational evidence statements.

    These statements become the primary grounding
    layer for generation.

    Responsibility: grounded truth construction / explicit grounding
    """

    evidence = []

    # Creation lifecycle
    if facts.intent_created:
        evidence.append(
            "payment intent creation succeeded"
        )

    # Processing lifecycle
    if facts.processing_started:
        evidence.append(
            "payment processing started"
        )

    # Failure lifecycle
    if facts.processing_failed:
        evidence.append(
            "payment processing failed"
        )

    # Auto-completion failure
    if facts.auto_completion_failed:
        evidence.append(
            "auto-completion failed during processing"
        )

    # Cancellation lifecycle
    if facts.transaction_cancelled:
        evidence.append(
            "transaction was cancelled"
        )

    # Completion lifecycle
    if facts.processing_completed:
        evidence.append(
            "payment processing completed successfully"
        )

    # Failure stage grounding
    if facts.failure_stage:
        evidence.append(
            f"failure occurred during {facts.failure_stage}"
        )

    # Final state grounding
    if facts.final_state:
        evidence.append(
            f"final transaction state is {facts.final_state}"
        )

    return evidence