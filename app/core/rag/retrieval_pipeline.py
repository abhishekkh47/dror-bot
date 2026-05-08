from app.core.llm.chunk_selector import select_relevant_chunks
from app.core.llm.operational_distiller import distill_chunks
from app.core.llm.operational_evidence import build_operational_evidence
from app.core.llm.rag_pipeline import is_noise_chunk, extract_lifecycle_facts
from app.core.rag.retrieval_filtering import apply_structured_filters
from app.core.llm.retriever import store


def build_retrieval_context(
    query,
    step,
):
    """
    Centralized retrieval orchestration layer.
    Responsibility: high-level retrieval orchestration
    """

    # Vector retrieval
    scored_chunks = store.search(
        query,
        step,
        top_k=8
    )

    if not scored_chunks:
        return None

    # Structured filtering
    filtered = apply_structured_filters(
        retrieved_chunks=scored_chunks,
        step=step,
    )

    # Noise suppression
    filtered = [
        (score, chunk)
        for score, chunk in filtered
        if not is_noise_chunk(chunk)
    ]

    # Fallback
    if not filtered:
        filtered = scored_chunks[:2]

    # LLM chunk selector
    filtered = select_relevant_chunks(
        query,
        filtered
    )

    if not filtered:
        filtered = scored_chunks[:2]

    # Lifecycle extraction
    lifecycle_facts = extract_lifecycle_facts(
        filtered
    )

    # Distillation
    distilled_chunks = distill_chunks(
        filtered
    )

    # Operational evidence
    operational_evidence = (
        build_operational_evidence(
            lifecycle_facts
        )
    )

    return {
        "filtered_chunks": filtered,
        "distilled_chunks": distilled_chunks,
        "lifecycle_facts": lifecycle_facts,
        "operational_evidence": operational_evidence,
    }