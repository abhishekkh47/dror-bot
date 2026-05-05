from app.core.llm.retriever import retrieve_context, store
from app.core.llm.prompt import build_prompt, build_prompt_with_step
from app.core.llm.llm import generate_response
import numpy as np

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

# Detect intent mismatch (deprecated)
def is_query_related_to_step(scored_chunks, step, threshold=0.55):
    """
    Check if any of the top chunks relevant to this step
    have sufficient similarity score
    """

    # Check if any top chunk belongs to this step's domain
    for score, chunk in scored_chunks:
        if chunk["topic"].startswith(step.rag_topic.split("_")[0]):
            if score >= threshold:
                return True

    return False

def is_query_related_to_step_v2(query: str, step, store, threshold=0.55):
    """
    Determine if query is relevant to current step
    using embedding similarity against step-specific chunks
    """

    # get top candidates (already domain filtered)
    scored_chunks = store.search(query, step=step, top_k=8)

    if not scored_chunks:
        return False
    
    top_score = scored_chunks[0][0]

    return top_score >= threshold

def is_chunk_relevant(chunk, step):
    step_tokens = step.rag_topic.split("_")
    chunk_tags = chunk.get("tags", [])

    # tag-based relevance (primary)
    overlap = sum(1 for t in step_tokens if t in chunk_tags)

    if overlap >= 1:
        return True

    # fallback: topic prefix (secondary)
    step_prefix = step_tokens[0]
    return chunk["topic"].startswith(step_prefix)

def ask_with_context(query: str, step):
    """
    Here we will use store.search to get the top 8 chunks and then filter them based on the step.rag_topic
    This is similar to retrieve data from cache
    recompute embedding -> slow, redundant
    reuse stored vectors -> fast, clean
    We will use a 3-layer filter to get the most relevant chunks
    1. topic partial match
    2. Tag overlap
    3. Soft fallback
    4. Similarity threshold
    5. Build context
    6. Build prompt
    7. Generate response
    """
    # 1. retrieve candidates
    scored_chunks = store.search(query, step, top_k=8)

    filtered = [
        (score, chunk)
        for score, chunk in scored_chunks
        if is_chunk_relevant(chunk, step)
    ]

    # 3. enforce boundary
    if not filtered: 
        # return handle_out_of_scope(query, step)
        # Add soft fallback instead -> this prevents total failure

        # if not is_query_related_to_step(scored_chunks, step):
        if not is_query_related_to_step_v2(query, step, store):
            return handle_out_of_scope(query, step)
        
        # allow soft fallback only if query is related to step
        filtered = scored_chunks[:2]
    
    # use score directly 
    top_score = filtered[0][0]
    
    if top_score < 0.6:
        return handle_out_of_scope(query, step)
    
    # 4. Build context
    context = "\n\n".join([
        f"[{chunk['topic']}]\n{chunk['content']}"
        for score, chunk in filtered
    ])

    prompt = build_prompt_with_step(
        query=query,
        context=context,
        step=step
    )

    return generate_response(prompt)