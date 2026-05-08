from app.core.rag.retrieval_metadata import (
    get_capability,
    get_lifecycle_stage,
    get_knowledge_type,
    get_visibility,
)


def apply_structured_filters(
    retrieved_chunks,
    step,
):
    """
    Apply metadata-driven retrieval filtering
    and lifecycle-aware score adjustments.

    Responsibility: metadata semantics
    """

    step_domains = step.domain or []

    step_topic = step.rag_topic

    filtered_chunks = []

    for score, chunk in retrieved_chunks:

        capability = get_capability(chunk)

        lifecycle_stage = get_lifecycle_stage(chunk)

        knowledge_type = get_knowledge_type(chunk)

        visibility = get_visibility(chunk)

        # Never expose internal chunks
        if visibility == "internal_only":
            continue

        # Hard capability filtering
        if step_domains:
            if capability not in step_domains:
                continue

        # Lifecycle-aware boosting
        lifecycle_boost = 0

        if lifecycle_stage == step_topic:
            lifecycle_boost += 0.35

        # Suppress transport-heavy chunks
        if knowledge_type == "transport_behavior":
            lifecycle_boost -= 0.25

        adjusted_score = score + lifecycle_boost

        print(
            f"{adjusted_score:.4f} | "
            f"capability={capability} | "
            f"stage={lifecycle_stage} | "
            f"type={knowledge_type}"
        )

        filtered_chunks.append(
            (adjusted_score, chunk)
        )

    filtered_chunks.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return filtered_chunks