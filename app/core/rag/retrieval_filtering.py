from app.core.rag.retrieval_metadata import (
    get_capability,
    get_importance,
    get_lifecycle_stage,
    get_knowledge_type,
    get_visibility,
)
from app.core.rag.retrieval_trace import RetrievalDecision, RetrievalTrace


def apply_structured_filters(
    retrieved_chunks,
    step,
):
    """
    Apply metadata-driven retrieval filtering
    and lifecycle-aware score adjustments.

    Responsibility: metadata semantics
    """
    trace = RetrievalTrace(
        query="",
        step_domain=step.domain or [],
        step_topic=step.rag_topic,
        decisions=[],
    )

    step_domains = step.domain or []
    step_topic = step.rag_topic
    filtered_chunks = []

    for score, chunk in retrieved_chunks:

        capability = get_capability(chunk)
        lifecycle_stage = get_lifecycle_stage(chunk)
        knowledge_type = get_knowledge_type(chunk)
        visibility = get_visibility(chunk)

        decision = RetrievalDecision(
            chunk_id=chunk["id"],
            capability=capability,
            lifecycle_stage=lifecycle_stage,
            knowledge_type=knowledge_type,
            importance=get_importance(chunk),
            base_score=score,
            adjusted_score=score,
            included=True,
            score_breakdown={}
        )

        # Never expose internal chunks
        if visibility == "internal_only":
            decision.included = False
            decision.exclusion_reason = "internal_visibility"
            trace.decisions.append(decision)
            continue

        # Hard capability filtering
        if step_domains:
            if capability not in step_domains:
                continue

        lifecycle_score = compute_lifecycle_score(
            lifecycle_stage,
            step_topic,
        )

        knowledge_score = compute_knowledge_type_score(
            knowledge_type
        )
        importance_score = compute_importance_score(
            get_importance(chunk)
        )

        adjusted_score = (
            score
            + lifecycle_score
            + knowledge_score
            + importance_score
        )

        decision.score_breakdown = {
            "lifecycle_score": lifecycle_score,
            "knowledge_score": knowledge_score,
            "importance_score": importance_score,
        }
        decision.adjusted_score = adjusted_score
        trace.decisions.append(decision)

        print(
        f"{adjusted_score:.4f} | "
        f"base={score:.4f} | "
        f"capability={capability} | "
        f"stage={lifecycle_stage} | "
        f"type={knowledge_type} | "
        f"importance={get_importance(chunk)}"
    )
        filtered_chunks.append(
            (adjusted_score, chunk)
        )

    filtered_chunks.sort(
        key=lambda x: x[0],
        reverse=True
    )
    return filtered_chunks, trace

def compute_lifecycle_score(
    chunk_stage,
    step_topic,
):
    """
    Lifecycle-stage relevance scoring.
    """

    if not chunk_stage or not step_topic:
        return 0
    if chunk_stage == step_topic:
        return 0.45

    related_stages = {
        "auto_completion": [
            "completion",
            "cancellation",
            "settlement",
        ],
        "payment_status": [
            "completion",
            "cancellation",
            "processing",
        ],
        "platform_transaction": [
            "processing",
            "completion",
        ],
    }
    related = related_stages.get(
        step_topic,
        []
    )
    if chunk_stage in related:
        return 0.20
    return 0

def compute_knowledge_type_score(
    knowledge_type,
):
    """
    Prioritize operationally-useful chunks.
    """

    boosts = {
        "operational_behavior": 0.30,
        "troubleshooting": 0.25,
        "business_rule": 0.20,
        "integration_guidance": 0.15,
        "transport_behavior": -0.35,
        "payload_schema": -0.40,
    }
    return boosts.get(
        knowledge_type,
        0
    )

def compute_importance_score(
    importance,
):
    """
    Prioritize important chunks.
    """
    boosts = {
        "critical": 0.30,
        "high": 0.20,
        "medium": 0.10,
        "low": 0,
    }
    return boosts.get(
        importance,
        0
    )