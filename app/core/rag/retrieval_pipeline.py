from app.core.llm.chunk_selector import select_relevant_chunks
from app.core.llm.operational_distiller import distill_chunks
from app.core.llm.operational_evidence import build_operational_evidence
from app.core.rag.lifecycle_chunk_selector import select_lifecycle_chunks
from app.core.rag.retrieval_confidence import compute_retrieval_confidence
from app.core.rag.retrieval_diagnostics import RetrievalDiagnostic, RetrievalStage
from app.core.rag.retrieval_rules import is_noise_chunk
from app.core.llm.lifecycle_extractor import extract_lifecycle_facts
from app.core.rag.retrieval_filtering import apply_structured_filters
from app.core.llm.retriever import store
from app.core.rag.retrieval_validator import validate_retrieval_quality


def build_retrieval_context(
    query,
    step,
):
    """
    Centralized retrieval orchestration layer.
    Responsibility: high-level retrieval orchestration
    """

    diagnostic = RetrievalDiagnostic(
        chunk_counts={}
    )
    # Vector retrieval
    scored_chunks = store.search(
        query,
        step,
        top_k=8
    )
    diagnostic.chunk_counts["vector_search"] = len(scored_chunks)

    if not scored_chunks:
        diagnostic.failed_stage = RetrievalStage.VECTOR_SEARCH
        diagnostic.reason = "Vector search returned no chunks"
        return {
            "diagnostic": diagnostic
        }

    # Structured filtering
    candidate_chunks, retrieval_trace = (
        apply_structured_filters(
            retrieved_chunks=scored_chunks,
            step=step
        )
    )
    diagnostic.chunk_counts["structured_filtering"] = len(candidate_chunks)
    if not candidate_chunks:
        diagnostic.failed_stage = RetrievalStage.STRUCTURED_FILTERING
        diagnostic.reason = "All chunks removed during structured filtering"
        return {
            "diagnostic": diagnostic
        }

    # Noise suppression
    candidate_chunks = [
        (score, chunk)
        for score, chunk in candidate_chunks
        if not is_noise_chunk(chunk)
    ]
    diagnostic.chunk_counts["noise_suppression"] = len(candidate_chunks)

    # Fallback
    if not candidate_chunks:
        diagnostic.failed_stage = RetrievalStage.NOISE_SUPPRESSION
        diagnostic.reason = "All chunks removed after noise suppression"
        return {
            "diagnostic": diagnostic
        }

    # initial Lifecycle extraction
    lifecycle_facts = extract_lifecycle_facts(
        candidate_chunks
    )

    # Lifecycle chunk selector
    selected_chunks = select_lifecycle_chunks(
        filtered_chunks=candidate_chunks,
        lifecycle_facts=lifecycle_facts,
    )
    diagnostic.chunk_counts["lifecycle_selection"] = len(selected_chunks)

    # LLM chunk selector
    selected_chunks = select_relevant_chunks(
        query,
        selected_chunks
    )
    diagnostic.chunk_counts["llm_selection"] = len(selected_chunks)

    if not selected_chunks:
        diagnostic.failed_stage = RetrievalStage.LLM_SELECTION
        diagnostic.reason = "All chunks removed by select_relevant_chunks"
        return {
            "diagnostic": diagnostic
        }
    
    # Final lifecycle grounding
    lifecycle_facts = extract_lifecycle_facts(
        selected_chunks
    )
    
    is_valid, validation_reason = (
        validate_retrieval_quality(
            selected_chunks=selected_chunks,
            lifecycle_facts=lifecycle_facts,
        )
    )

    if not is_valid:
        diagnostic.failed_stage = (
            "retrieval_validation"
        )

        diagnostic.reason = validation_reason

        return {
            "diagnostic": diagnostic
        }
    
    retrieval_confidence = (
        compute_retrieval_confidence(
            selected_chunks=selected_chunks,
            lifecycle_facts=lifecycle_facts,
        )
    )

    # Distillation
    distilled_chunks = distill_chunks(
        selected_chunks
    )
    diagnostic.chunk_counts["distillation"] = len(distilled_chunks)

    # Operational evidence
    operational_evidence = (
        build_operational_evidence(
            lifecycle_facts
        )
    )

    return {
        "candidate_chunks": candidate_chunks,
        "selected_chunks": selected_chunks,
        "distilled_chunks": distilled_chunks,
        "lifecycle_facts": lifecycle_facts,
        "operational_evidence": operational_evidence,
        "retrieval_trace": retrieval_trace,
        "diagnostic": diagnostic,
        "retrieval_confidence": retrieval_confidence,
    }