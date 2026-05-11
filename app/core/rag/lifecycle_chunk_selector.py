from app.core.rag.chunk_selection_policy import compute_chunk_selection_score


def select_lifecycle_chunks(filtered_chunks, lifecycle_facts, top_k = 5):
    """
    Select chunks that best preserve operational chronology and lifecycle reasoning

    this selector does NOT:
    - use LLMs
    - summarize
    - reason recursively
    - generate chains

    It is - deterministic operational prioritization
    """

    rescored = []

    for score, chunk in filtered_chunks:
        policy_score = compute_chunk_selection_score(chunk, lifecycle_facts)

        final_score = score + policy_score
        rescored.append((final_score, chunk))

    rescored.sort(key=lambda x: x[0], reverse=True)
    return rescored[:top_k]