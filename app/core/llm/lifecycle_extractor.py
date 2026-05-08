from app.core.llm.lifecycle_facts import LifecycleFacts


def extract_lifecycle_facts(filtered_chunks):
    """
    Extract deterministic operational lifecycle facts from retrieved chunks.

    This layer exists to:
    - separate lifecycle reasoning from generation
    - reduce prompt hallucinations/ambiguity
    - normalize operational state
    """

    facts = LifecycleFacts()
    combined_text = " ".join([
        chunk["content"].lower()
        for _, chunk in filtered_chunks
    ])

    if any(phrase in combined_text for phrase in [
        "intent created successfully",
        "payment intent created",
        "platform transaction created",
    ]):
        facts.intent_created = True

    if any(phrase in combined_text for phrase in [
        "auto-completion",
        "processing",
        "settlement",
        "completion stage",
    ]):
        facts.processing_started = True

    if any(phrase in combined_text for phrase in [
        "failed",
        "error",
        "http 400",
        "rollback",
    ]):
        facts.processing_failed = True

    if any(phrase in combined_text for phrase in [
        "auto-completion failed",
        "auto-completion error",
        "auto-completion rollback",
    ]):
        facts.auto_completion_failed = True

    if any(phrase in combined_text for phrase in [
        "cancelled",
        "cancellation",
        "status to cancelled",
    ]):
        facts.transaction_cancelled = True

    if any(phrase in combined_text for phrase in [
        "marked platform transaction as completed",
        "payment completed successfully",
        "transaction_completed",
    ]):
        facts.processing_completed = True

    facts.infer_derived_state()
    facts.resolve_contradictions()

    return facts
