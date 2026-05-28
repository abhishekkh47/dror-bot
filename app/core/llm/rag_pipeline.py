import time
from app.core.cache.cache_keys import build_response_cache_key
from app.core.cache.cache_policy import should_cache_response
from app.core.cache.response_cache import get_cached_response, save_cached_response
from app.core.llm.retriever import retrieve_context, store
from app.core.llm.prompt import build_prompt, build_prompt_with_step
from app.core.llm.llm import generate_response
from app.core.memory.memory_reset import reset_session_memory, should_reset_investigation
from app.core.memory.memory_store import get_session_memory, save_session_memory
from app.core.memory.memory_updater import update_session_memory
from app.core.memory.session_memory import SessionMemory
from app.core.observability.telemetry import build_telemetry_event
from app.core.observability.telemetry_logger import log_telemetry_event
from app.core.rag.confidence_policy import build_confidence_policy
from app.core.rag.context_builder import build_structured_context
from app.core.rag.fallback_policy import determine_response_mode
from app.core.rag.lifecycle_drift import detect_lifecycle_drift
from app.core.rag.reasoning_validator import validate_reasoning_consistency
from app.core.rag.response_governance import build_response_constraints
from app.core.rag.response_reliability import compute_response_reliability
from app.core.rag.retrieval_debugger import print_retrieval_trace
from app.core.rag.retrieval_metadata import get_capability, get_lifecycle_stage
from app.core.rag.retrieval_pipeline import build_retrieval_context
from app.core.rag.retrieval_recovery import should_retry_retrieval
from app.core.types import ExecutionResult
from app.tests.evals.evaluation_metrics import score_response_quality
from app.utils.patterns import RESPONSE_PATTERNS, CONTRADICTION_PATTERNS, CLEANUP_PATTERNS, INTERNAL_PATTERNS
from app.utils.logger import logger
import re

def ask(query: str):
    context = retrieve_context(query)
    prompt = build_prompt(query, context)
    response = generate_response(prompt)
    return response

def handle_out_of_scope(query: str, step):
    return f"""
    This question is outside the current step: "{step.title}".

    You're currently working on: {step.title}

    If you're trying to understand payment headers, go back to the "Create Intent" step.

    Otherwise, ask something related to:
    - payment status
    - success/failure handling
    """.strip()

def sanitize_response(resp: str):
    forbidden = ["internal vector", "embedding", "retrieval score"]

    for word in forbidden:
        resp = resp.replace(word, "")

    for pattern, replacement in CONTRADICTION_PATTERNS.items():
        resp = re.sub(
            pattern,
            replacement,
            resp,
            flags=re.IGNORECASE
        )
    
    for pattern in CLEANUP_PATTERNS:
        resp = re.sub(
            pattern,
            "",
            resp,
            flags=re.IGNORECASE
        )

    for pattern in INTERNAL_PATTERNS:
        resp = re.sub(
            pattern,
            "",
            resp,
            flags=re.IGNORECASE
        )
    resp = re.sub(r'\s+', ' ', resp).strip()

    return resp.strip()

def detect_response_intent(query: str):
    q = query.lower()

    # WHY something got cancelled
    if any(x in q for x in [
        "why cancelled",
        "why was payment cancelled",
        "cancelled"
    ]):
        return "cancellation_reason"

    # payment did not complete
    if any(x in q for x in [
        "didn't complete",
        "not complete",
        "did not complete",
        "payment incomplete"
    ]):
        return "completion_failure"

    # failed after processing started
    if any(x in q for x in [
        "failed after processing",
        "after processing",
        "processing failed"
    ]):
        return "post_processing_failure"

    return "generic_failure"

# def ask_with_context(query: str, step, session_memory=None):
def ask_with_context(query: str, step, session_id: str = "default"):
    """
    High-level RAG orchestration layer.

    Pipeline:
    1. Retrieval orchestration
    2. Structured filtering
    3. Lifecycle-aware selection
    4. Retrieval validation
    5. Operational distillation
    6. Structured context assembly
    7. Prompt generation
    8. LLM response generation
    9. Response sanitization
    """

    try:
        print("\nSTEP DOMAIN:", step.domain)
        print("STEP RAG TOPIC:", step.rag_topic)
        request_start = time.time()

        session_memory = get_session_memory(session_id)

        if session_memory and should_reset_investigation(session_memory = session_memory, current_query = query):
            session_memory = reset_session_memory(session_id)
        
        if not session_memory:
            session_memory = SessionMemory(session_id=session_id)
        
        # RESPONSE CACHE CHECK
        cache_key = build_response_cache_key(
            query=query,
            step=step,
        )

        cached_response = get_cached_response(
            cache_key
        )

        if cached_response:
            cached_result = ExecutionResult(
                **cached_response
            )
            cache_latency_ms = int(
                (time.time() - request_start) * 1000
            )
            log_telemetry_event(
                build_telemetry_event(
                    execution_result=cached_result,
                    query=query,
                    step=step,
                    total_latency_ms=cache_latency_ms,
                    cache_hit=True,
                )
            )
            return cached_result

        retrieval_context = build_retrieval_context(query=query, step=step, session_memory=session_memory)
        diagnostic = retrieval_context.get("diagnostic")
        # TEMP DEVELOPMENT RESPONSE
        if diagnostic and diagnostic.failed_stage:
            response = (
                f"No relevant context found. "
                f"Failed at: {diagnostic.failed_stage}"
            )
            return ExecutionResult(
                response=response,
                retrieval_confidence=0.0,
                reasoning_issues=[],
                response_mode="fallback",
                quality_score=0,
                selected_chunks=[],
                lifecycle_drift_issues=[],
                retrieval_recovery_eligible=False,
                retry_attempted=False,
                initial_retrieval_confidence=0.0,
                final_retrieval_confidence=0.0,
                retry_confidence_delta=0.0,
                retrieval_stability_score=100,
                lifecycle_coherence_score=0,
                operational_conflicts=[],
                response_reliability_score=100,
                evidence_attribution={},
                reasoning_breakdown={},
                operational_ambiguities=[],
            )
        
        retrieval_trace = retrieval_context["retrieval_trace"]
        # TEMP DEBUGGING ONLY
        print_retrieval_trace(retrieval_trace)
        distilled_chunks = retrieval_context["distilled_chunks"]
        lifecycle_facts = retrieval_context["lifecycle_facts"]
        operational_evidence = retrieval_context["operational_evidence"]
        retrieval_confidence = retrieval_context["retrieval_confidence"]
        lifecycle_timeline = retrieval_context["lifecycle_timeline"]
        selected_chunks = retrieval_context["selected_chunks"]
        evidence_attribution = retrieval_context.get("evidence_attribution",{})
        reasoning_breakdown = retrieval_context.get("reasoning_breakdown",{})
        operational_ambiguities = retrieval_context.get("operational_ambiguities",[])
        retry_attempted = retrieval_context.get(
            "retry_attempted",
            False
        )
        initial_retrieval_confidence = (
            retrieval_context.get(
                "initial_retrieval_confidence",
                retrieval_confidence,
            )
        )
        final_retrieval_confidence = (
            retrieval_context.get(
                "final_retrieval_confidence",
                retrieval_confidence,
            )
        )
        retry_confidence_delta = (
            retrieval_context.get(
                "retry_confidence_delta",
                0.0,
            )
        )
        retrieval_stability_score = (
            retrieval_context.get(
                "retrieval_stability_score",
                100,
            )
        )

        lifecycle_coherence_score = (
            retrieval_context.get(
                "lifecycle_coherence_score",
                0,
            )
        )

        operational_conflicts = (
            retrieval_context.get(
                "operational_conflicts",
                [],
            )
        )

        response_reliability_score = compute_response_reliability(
            retrieval_confidence=retrieval_confidence,
            lifecycle_coherence_score=lifecycle_coherence_score,
            retrieval_stability_score=retrieval_stability_score,
            operational_conflicts=operational_conflicts,
            operational_ambiguities=operational_ambiguities,
        )

        lifecycle_drift_issues = detect_lifecycle_drift(
            lifecycle_facts=lifecycle_facts,
            selected_chunks=selected_chunks,
        )

        context = build_structured_context(
            context_chunks=distilled_chunks,
            operational_evidence=operational_evidence,
            lifecycle_timeline=lifecycle_timeline
        )

        response_constraints = build_response_constraints(
            retrieval_confidence=retrieval_confidence,
            lifecycle_facts=lifecycle_facts,
        )
        
        confidence_policy = build_confidence_policy(retrieval_confidence)

        response_intent = detect_response_intent(query)
        response_pattern = RESPONSE_PATTERNS.get(
            response_intent,
            ""
        )

        memory_summary = (
            session_memory.investigation_summary
        )

        memory_context = (
            f"Lifecycle States: "
            f"{memory_summary.get('active_lifecycle_states', [])}\n"

            f"Operational Findings: "
            f"{memory_summary.get('major_operational_findings', [])}\n"

            f"Active Topics: "
            f"{memory_summary.get('active_topics', [])}"
        )

        prompt = build_prompt_with_step(
            query=query,
            context=context,
            step=step,
            response_pattern=response_pattern,
            failure_summary=lifecycle_facts,
            operational_evidence=operational_evidence,
            response_constraints=response_constraints,
            confidence_policy=confidence_policy,
            memory_context=memory_context,
        )

        response = generate_response(prompt)
        session_memory = update_session_memory(
            session_memory = session_memory,
            lifecycle_facts = lifecycle_facts,
            reasoning_breakdown = reasoning_breakdown,
            evidence_attribution = evidence_attribution,
            response = response,
        )
        save_session_memory(session_memory)
        reasoning_issues = (
            validate_reasoning_consistency(
                response=response,
                lifecycle_facts=lifecycle_facts,
            )
        )
        if reasoning_issues:
            logger.warning(
                "Reasoning consistency validation failed",
                extra={
                    "issues": reasoning_issues,
                    "query": query,
                    "retrieval_confidence": retrieval_confidence,
                }
            )
        
        # reasoning_issues.extend(
        #     lifecycle_drift_issues
        # )
        reasoning_issues.extend(
            operational_conflicts
        )
        
        retrieval_recovery_eligible = (
            should_retry_retrieval(
                retrieval_confidence=
                    retrieval_confidence,

                lifecycle_drift_issues=
                    lifecycle_drift_issues,
            )
        )
        
        response_mode = determine_response_mode(
            retrieval_confidence=retrieval_confidence,
            reasoning_issues=reasoning_issues,
            response_reliability_score=response_reliability_score,
        )

        response = sanitize_response(response)
        if response_mode == "fallback":
            response = (
                "The available operational evidence "
                "is insufficient to reliably determine "
                "the payment failure cause."
            )
        if response_mode == "clarification":
            response = (
                "Additional operational details may "
                "be required to determine the exact "
                "payment failure reason."
            )
        
        quality_score = score_response_quality(
            response=response,
            retrieval_confidence=retrieval_confidence,
            reasoning_issues=reasoning_issues,
            response_mode=response_mode,
        )

        execution_result = ExecutionResult(
            response=response,
            retrieval_confidence=retrieval_confidence,
            reasoning_issues=reasoning_issues,
            response_mode=response_mode,
            quality_score=quality_score,
            selected_chunks=selected_chunks,
            lifecycle_drift_issues=lifecycle_drift_issues,
            retrieval_recovery_eligible=retrieval_recovery_eligible,
            retry_attempted=retry_attempted,
            initial_retrieval_confidence=initial_retrieval_confidence,
            final_retrieval_confidence=final_retrieval_confidence,
            retry_confidence_delta=retry_confidence_delta,
            retrieval_stability_score=retrieval_stability_score,
            lifecycle_coherence_score=lifecycle_coherence_score,
            operational_conflicts=operational_conflicts,
            response_reliability_score=response_reliability_score,
            evidence_attribution=evidence_attribution,
            reasoning_breakdown=reasoning_breakdown,
            operational_ambiguities=operational_ambiguities,
        )
        
        total_latency_ms = int(
            (
                time.time() - request_start
            ) * 1000
        )

        telemetry_event = build_telemetry_event(
            execution_result=execution_result,
            query=query,
            step=step,
            total_latency_ms=total_latency_ms,
        )
        log_telemetry_event(telemetry_event)

        if should_cache_response(execution_result):
            save_cached_response(
                cache_key=cache_key,
                payload=execution_result.model_dump(),
            )

        return execution_result
    except Exception as e:
        logger.error(f"Error asking with context: {e}")
        return ExecutionResult(
            response="An internal processing error occurred.",
            retrieval_confidence=0.0,
            reasoning_issues=[],
            response_mode="fallback",
            quality_score=0,
            selected_chunks=[],
            lifecycle_drift_issues=[],
            retrieval_recovery_eligible=False,
            retry_attempted=False,
            initial_retrieval_confidence=0.0,
            final_retrieval_confidence=0.0,
            retry_confidence_delta=0.0,
            retrieval_stability_score=100,
            lifecycle_coherence_score=0,
            operational_conflicts=[],
            response_reliability_score=100,
            evidence_attribution={},
            reasoning_breakdown={},
            operational_ambiguities=[],
        )