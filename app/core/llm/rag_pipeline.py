from app.core.llm.retriever import retrieve_context
from app.core.llm.prompt import build_prompt, build_prompt_with_step
from app.core.llm.llm import generate_response
from app.core.rag.confidence_policy import build_confidence_policy
from app.core.rag.context_builder import build_structured_context
from app.core.rag.fallback_policy import determine_response_mode
from app.core.rag.reasoning_validator import validate_reasoning_consistency
from app.core.rag.response_governance import build_response_constraints
from app.core.rag.retrieval_debugger import print_retrieval_trace
from app.core.rag.retrieval_metadata import get_capability, get_lifecycle_stage
from app.core.rag.retrieval_pipeline import build_retrieval_context
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

def ask_with_context(query: str, step):
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

        retrieval_context = build_retrieval_context(query=query, step=step)
        diagnostic = retrieval_context.get("diagnostic")
        # TEMP DEVELOPMENT RESPONSE
        if diagnostic and diagnostic.failed_stage:
            return (
                f"No relevant context found. "
                f"Failed at: {diagnostic.failed_stage}"
            )
        
        retrieval_trace = retrieval_context["retrieval_trace"]
        # TEMP DEBUGGING ONLY
        print_retrieval_trace(retrieval_trace)
        distilled_chunks = retrieval_context["distilled_chunks"]
        lifecycle_facts = retrieval_context["lifecycle_facts"]
        operational_evidence = retrieval_context["operational_evidence"]
        retrieval_confidence = retrieval_context["retrieval_confidence"]
        lifecycle_timeline = retrieval_context["lifecycle_timeline"]

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

        prompt = build_prompt_with_step(
            query=query,
            context=context,
            step=step,
            response_pattern=response_pattern,
            failure_summary=lifecycle_facts,
            operational_evidence=operational_evidence,
            response_constraints=response_constraints,
            confidence_policy=confidence_policy,
        )

        response = generate_response(prompt)
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
        
        response_mode = determine_response_mode(
            retrieval_confidence=retrieval_confidence,
            reasoning_issues=reasoning_issues,
        )

        response = sanitize_response(response)
        if response_mode == "fallback":
            return (
                "The available operational evidence "
                "is insufficient to reliably determine "
                "the payment failure cause."
            )
        if response_mode == "clarification":
            return (
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

        return ExecutionResult(
            response=response,
            retrieval_confidence=retrieval_confidence,
            reasoning_issues=reasoning_issues,
            response_mode=response_mode,
            quality_score=quality_score,
        )
    except Exception as e:
        logger.error(f"Error asking with context: {e}")
        return f"An error occurred while processing your request: {e}. Please try again later."