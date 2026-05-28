def apply_memory_retrieval_boost(
    retrieved_chunks,
    session_memory,
):
    """
    Boost retrieval scores using
    ongoing operational memory.
    """

    boosted_chunks = []

    discussed_topics = set(
        session_memory.discussed_topics
    )

    operational_history = " ".join(
        session_memory.operational_history
    ).lower()

    for score, chunk in retrieved_chunks:
        adjusted_score = score
        metadata = chunk.get("metadata",{})
        topic = metadata.get("topic")

        # Topic continuity boost
        if (
            topic
            and topic in discussed_topics
        ):
            adjusted_score += 0.08

        # Lifecycle continuity boost
        chunk_text = chunk.get("text","").lower()

        if (
            "processing"
            in operational_history
            and "processing"
            in chunk_text
        ):
            adjusted_score += 0.05

        if (
            "cancel"
            in operational_history
            and "cancel"
            in chunk_text
        ):
            adjusted_score += 0.05

        boosted_chunks.append((adjusted_score, chunk))

    boosted_chunks.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return boosted_chunks