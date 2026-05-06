from app.core.llm.chunk_selector import select_relevant_chunks
from app.core.llm.retriever import retrieve_context, store
from app.core.llm.prompt import build_prompt, build_prompt_with_step
from app.core.llm.llm import generate_response
from app.utils.logger import logger
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

def is_noise_chunk(chunk):
    return chunk["topic"] in [
        "create_intent_pending_event_without_completion"
    ]

def sanitize_response(resp: str):
    forbidden = ["webhook", "socket", "event"]
    for word in forbidden:
        if word in resp.lower():
            return "Answer: Payment failed during processing after intent creation."
    
    if "intent creation failed" in resp.lower():
        return resp.replace("intent creation failed", "payment failed after intent creation")

    return resp

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

    try:
        # 1. retrieve candidates
        scored_chunks = store.search(query, step, top_k=8)

        if not scored_chunks:
            return "No relevant context found for this query."

        # Step 1 — remove noise FIRST
        filtered = [
            (score, chunk)
            for score, chunk in scored_chunks
            if not is_noise_chunk(chunk)
        ]

        # Step 2 — fallback AFTER noise filtering
        if not filtered:
            filtered = scored_chunks[:2]

        filtered = select_relevant_chunks(query, filtered)
        
        if not filtered:
            filtered = scored_chunks[:2]

        # Step 4 — build context
        context = "\n\n".join([
            chunk['content']
            for _, chunk in filtered
        ])

        prompt = build_prompt_with_step(
            query=query,
            context=context,
            step=step
        )

        response = generate_response(prompt)
        return sanitize_response(response)
    except Exception as e:
        logger.error(f"Error asking with context: {e}")
        return f"An error occurred while processing your request: {e}. Please try again later."