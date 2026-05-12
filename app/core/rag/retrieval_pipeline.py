from app.core.llm.chunk_selector import select_relevant_chunks
from app.core.llm.operational_distiller import distill_chunks
from app.core.llm.operational_evidence import build_operational_evidence
from app.core.rag.evidence_conflicts import detect_operational_conflicts
from app.core.rag.lifecycle_chunk_selector import select_lifecycle_chunks
from app.core.rag.lifecycle_coherence import score_lifecycle_coherence
from app.core.rag.retrieval_comparator import compare_retrieval_quality
from app.core.rag.retrieval_confidence import compute_retrieval_confidence
from app.core.rag.retrieval_diagnostics import RetrievalDiagnostic, RetrievalStage
from app.core.rag.retrieval_recovery import apply_recovery_strategy, build_recovery_strategy, should_retry_retrieval
from app.core.rag.retrieval_rules import is_noise_chunk
from app.core.llm.lifecycle_extractor import extract_lifecycle_facts
from app.core.rag.retrieval_filtering import apply_structured_filters
from app.core.llm.retriever import store
from app.core.rag.retrieval_stability import analyze_retrieval_stability
from app.core.rag.retrieval_validator import validate_retrieval_quality
from app.core.rag.timeline_builder import build_lifecycle_timeline


def build_retrieval_context(
    query,
    step,
):
    """
    Centralized retrieval orchestration layer.
    Responsibility:
    - vector retrieval
    - adaptive retrieval retry
    - retrieval orchestration
    """

    retrieval_options = {
        "top_k": 8,
        "similarity_threshold": 0.70,
    }

    # Initial retrieval
    scored_chunks = store.search(
        query,
        step,
        top_k=retrieval_options["top_k"]
    )

    diagnostic = RetrievalDiagnostic(
        chunk_counts={
            "vector_search": len(scored_chunks)
        }
    )

    if not scored_chunks:
        diagnostic.failed_stage = RetrievalStage.VECTOR_SEARCH
        diagnostic.reason = "Vector search returned no chunks"
        return { "diagnostic": diagnostic }

    # Initial retrieval processing
    retrieval_context = (
        process_retrieved_chunks(
            retrieved_chunks=scored_chunks,
            query=query,
            step=step,
        )
    )

    retrieval_confidence = (
        retrieval_context.get(
            "retrieval_confidence",
            0.0
        )
    )
    initial_retrieval_confidence = retrieval_confidence
    retry_attempted = False
    retry_confidence_delta = 0.0
    retrieval_stability_score = 100

    # Adaptive retrieval recovery
    retrieval_recovery_eligible = (
        should_retry_retrieval(
            retrieval_confidence=
                retrieval_confidence,

            lifecycle_drift_issues=[],
        )
    )

    # Controlled single retry
    if retrieval_recovery_eligible:
        retry_attempted = True
        recovery_strategy = (
            build_recovery_strategy()
        )
        retrieval_options = (
            apply_recovery_strategy(
                retrieval_options,
                recovery_strategy,
            )
        )
        retry_chunks = store.search(
            query,
            step,
            top_k=retrieval_options["top_k"]
        )
        retry_context = process_retrieved_chunks(
            retrieved_chunks=retry_chunks,
            query=query,
            step=step,
        )
        retrieval_stability_score = analyze_retrieval_stability(
            initial_context=retrieval_context,
            retry_context=retry_context,
        )
        retry_confidence = retry_context.get(
            "retrieval_confidence",
            0.0
        )
        retry_confidence_delta = (
            retry_confidence - initial_retrieval_confidence
        )
        # Keep better retrieval result
        retry_is_better = (
            compare_retrieval_quality(
                initial_context=retrieval_context,
                retry_context=retry_context,
            )
        )

        if retry_is_better:
            retrieval_context = retry_context

    retrieval_context["retry_attempted"] = retry_attempted
    retrieval_context["initial_retrieval_confidence"] = initial_retrieval_confidence
    retrieval_context["final_retrieval_confidence"] = retrieval_context.get("retrieval_confidence",0.0)
    retrieval_context["retry_confidence_delta"] = retry_confidence_delta
    retrieval_context["retrieval_stability_score"] = retrieval_stability_score
    return retrieval_context

def process_retrieved_chunks(
    retrieved_chunks,
    query,
    step,
):
    """
    Process retrieved chunks through
    filtering, selection, validation,
    distillation, and lifecycle extraction.
    """

    diagnostic = RetrievalDiagnostic(
        chunk_counts={}
    )

    # Structured filtering
    candidate_chunks, retrieval_trace = (
        apply_structured_filters(
            retrieved_chunks=retrieved_chunks,
            step=step
        )
    )

    diagnostic.chunk_counts[
        "structured_filtering"
    ] = len(candidate_chunks)

    if not candidate_chunks:
        diagnostic.failed_stage = (
            RetrievalStage.STRUCTURED_FILTERING
        )
        diagnostic.reason = (
            "All chunks removed during filtering"
        )
        return {
            "diagnostic": diagnostic
        }

    # Noise suppression
    candidate_chunks = [
        (score, chunk)
        for score, chunk in candidate_chunks
        if not is_noise_chunk(chunk)
    ]

    diagnostic.chunk_counts[
        "noise_suppression"
    ] = len(candidate_chunks)

    if not candidate_chunks:
        diagnostic.failed_stage = (
            RetrievalStage.NOISE_SUPPRESSION
        )
        diagnostic.reason = (
            "All chunks removed during noise suppression"
        )
        return {
            "diagnostic": diagnostic
        }

    # Initial lifecycle extraction
    lifecycle_facts = extract_lifecycle_facts(
        candidate_chunks
    )

    # Lifecycle selection
    selected_chunks = select_lifecycle_chunks(
        filtered_chunks=candidate_chunks,
        lifecycle_facts=lifecycle_facts,
    )
    if not selected_chunks:
        diagnostic.failed_stage = (
            RetrievalStage.LIFECYCLE_SELECTION
        )
        diagnostic.reason = (
            "All chunks removed during lifecycle selection"
        )
        return {
            "diagnostic": diagnostic
        }

    diagnostic.chunk_counts[
        "lifecycle_selection"
    ] = len(selected_chunks)

    # LLM chunk selection
    selected_chunks = select_relevant_chunks(
        query,
        selected_chunks
    )

    diagnostic.chunk_counts[
        "llm_selection"
    ] = len(selected_chunks)

    if not selected_chunks:
        diagnostic.failed_stage = (
            RetrievalStage.LLM_SELECTION
        )
        diagnostic.reason = (
            "All chunks removed during LLM selection"
        )
        return {
            "diagnostic": diagnostic
        }

    # Final lifecycle extraction
    lifecycle_facts = extract_lifecycle_facts(
        selected_chunks
    )

    # Validation
    is_valid, validation_reason = (
        validate_retrieval_quality(
            selected_chunks=selected_chunks,
            lifecycle_facts=lifecycle_facts,
        )
    )

    if not is_valid:
        diagnostic.failed_stage = (
            RetrievalStage.RETRIEVAL_VALIDATION
        )

        diagnostic.reason = validation_reason

        return {
            "diagnostic": diagnostic
        }

    # Confidence
    retrieval_confidence = compute_retrieval_confidence(
        selected_chunks=selected_chunks,
        lifecycle_facts=lifecycle_facts,
    )

    # Distillation
    distilled_chunks = distill_chunks(selected_chunks)

    # Operational evidence
    operational_evidence = build_operational_evidence(lifecycle_facts)

    operational_conflicts = detect_operational_conflicts(
        lifecycle_facts=lifecycle_facts,
        operational_evidence=operational_evidence,
    )

    # Timeline
    lifecycle_timeline = build_lifecycle_timeline(lifecycle_facts)

    lifecycle_coherence_score = score_lifecycle_coherence(lifecycle_timeline)

    return {
        "candidate_chunks": candidate_chunks,
        "selected_chunks": selected_chunks,
        "distilled_chunks": distilled_chunks,
        "lifecycle_facts": lifecycle_facts,
        "operational_evidence": operational_evidence,
        "retrieval_trace": retrieval_trace,
        "diagnostic": diagnostic,
        "retrieval_confidence": retrieval_confidence,
        "lifecycle_timeline": lifecycle_timeline,
        "lifecycle_coherence_score": lifecycle_coherence_score,
        "operational_conflicts": operational_conflicts,
    }