from app.core.llm.chunk_selector import select_relevant_chunks
from app.core.llm.operational_distiller import distill_chunks
from app.core.llm.operational_evidence import build_operational_evidence
from app.core.rag.lifecycle_chunk_selector import select_lifecycle_chunks
from app.core.rag.retrieval_rules import is_noise_chunk
from app.core.llm.lifecycle_extractor import extract_lifecycle_facts
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
    candidate_chunks, retrieval_trace = (
        apply_structured_filters(
            retrieved_chunks=scored_chunks,
            step=step
        )
    )

    # Noise suppression
    candidate_chunks = [
        (score, chunk)
        for score, chunk in candidate_chunks
        if not is_noise_chunk(chunk)
    ]

    # Fallback
    if not candidate_chunks:
        return None

    # Lifecycle extraction
    lifecycle_facts = extract_lifecycle_facts(
        candidate_chunks
    )

    # Lifecycle chunk selector
    selected_chunks = select_lifecycle_chunks(
        filtered_chunks=candidate_chunks,
        lifecycle_facts=lifecycle_facts,
    )

    # LLM chunk selector
    selected_chunks = select_relevant_chunks(
        query,
        selected_chunks
    )

    if not selected_chunks:
        return None
    
    # Final lifecycle grounding
    lifecycle_facts = extract_lifecycle_facts(
        selected_chunks
    )

    # Distillation
    distilled_chunks = distill_chunks(
        selected_chunks
    )

    # Operational evidence
    operational_evidence = (
        build_operational_evidence(
            lifecycle_facts
        )
    )

    return {
        "filtered_chunks": candidate_chunks,
        "distilled_chunks": distilled_chunks,
        "lifecycle_facts": lifecycle_facts,
        "operational_evidence": operational_evidence,
        "retrieval_trace": retrieval_trace,
    }