from app.core.llm.retriever import retrieve_context
from app.core.llm.prompt import build_prompt, build_prompt_with_step
from app.core.llm.llm import generate_response
from app.core.rag.retrieval_pipeline import build_retrieval_context
from app.utils.patterns import RESPONSE_PATTERNS, CONTRADICTION_PATTERNS, CLEANUP_PATTERNS, INTERNAL_PATTERNS
from app.utils.logger import logger
from app.core.llm.lifecycle_facts import LifecycleFacts
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

    Responsibility: high-level orchestration
    """

    try:
        print("\nSTEP DOMAIN:", step.domain)
        print("STEP RAG TOPIC:", step.rag_topic)

        retrieval_context = build_retrieval_context(query=query, step=step)
        if not retrieval_context:
            return "No relevant context found for this query."
        
        filtered = retrieval_context["filtered_chunks"]
        distilled_chunks = retrieval_context["distilled_chunks"]
        lifecycle_facts = retrieval_context["lifecycle_facts"]
        operational_evidence = retrieval_context["operational_evidence"]

        # Step 4 — build context
        normalized_chunks = []
        for chunk in distilled_chunks:
            content = chunk["content"]

            replacements = {
                "payment intent creation failed":
                    "payment processing failed after intent creation",

                "intent creation failed":
                    "processing failed after intent creation",

                "payment intent creation failed after processing":
                    "payment processing failed after intent creation",

                "intent was not created successfully":
                    "payment processing did not complete successfully",

                "payment intent was not created successfully":
                    "payment processing did not complete successfully",

                "transaction creation failed":
                    "transaction processing failed",
            }

            for wrong, correct in replacements.items():
                content = re.sub(
                    wrong,
                    correct,
                    content,
                    flags=re.IGNORECASE
                )

            normalized_chunks.append(f"""
            SOURCE_TOPIC: {chunk['topic']}
            SOURCE_TAGS: {", ".join(chunk.get("tags", []))}

            CONTENT:
            {content}
            """.strip())

        evidence_block = "\n".join([
            f"- {item}"
            for item in operational_evidence
        ])

        raw_context = "\n\n".join(normalized_chunks)

        context = f"""
        OPERATIONAL_EVIDENCE:
        {evidence_block}

        SUPPORTING_CONTEXT:
        {raw_context}
        """.strip()

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
            operational_evidence=operational_evidence
        )

        response = generate_response(prompt)
        return sanitize_response(response)
    except Exception as e:
        logger.error(f"Error asking with context: {e}")
        return f"An error occurred while processing your request: {e}. Please try again later."