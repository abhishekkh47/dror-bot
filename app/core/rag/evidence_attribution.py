def build_evidence_attribution(
    selected_chunks,
    lifecycle_facts,
):
    """
    Build operational evidence attribution.
    """

    attribution = {
        "supporting_topics": [],
        "grounded_lifecycle_facts": [],
        "evidence_chunk_ids": [],
    }

    # Supporting topics
    topics = set()

    for _, chunk in selected_chunks:

        metadata = chunk.get(
            "metadata",
            {}
        )

        topic = metadata.get(
            "topic"
        )

        if topic:
            topics.add(topic)

        chunk_id = chunk.get("id")

        if chunk_id:
            attribution[
                "evidence_chunk_ids"
            ].append(chunk_id)

    attribution[
        "supporting_topics"
    ] = list(topics)

    # Lifecycle grounding
    if lifecycle_facts.intent_created:
        attribution[
            "grounded_lifecycle_facts"
        ].append(
            "intent_created"
        )

    if lifecycle_facts.processing_started:
        attribution[
            "grounded_lifecycle_facts"
        ].append(
            "processing_started"
        )

    if lifecycle_facts.processing_failed:
        attribution[
            "grounded_lifecycle_facts"
        ].append(
            "processing_failed"
        )

    if lifecycle_facts.transaction_cancelled:
        attribution[
            "grounded_lifecycle_facts"
        ].append(
            "transaction_cancelled"
        )

    return attribution