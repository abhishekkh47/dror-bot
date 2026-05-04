from app.core.llm.embedding import get_embedding
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
    This question is not relevant to the current step: "{step.title}".

    You are currently in a different part of the integration flow.

    Ask a question related to this step or move to the appropriate step.
    """.strip()

def ask_with_context(query: str, step):
    # 1. retrieve candidates
    context_chunks = store.search(query)

    def is_relevant(chunk, step):
        # 1. topic partial match
        if step.rag_topic in chunk["topic"]:
            return True
        
        # 2. Tag overlap
        step_tokens = step.rag_topic.split("_")
        chunk_tags = chunk.get("tags", [])

        if any(token in chunk_tags for token in step_tokens):
            return True
        return False

    # 2. strict topic filter
    filtered = [
        c for c in context_chunks if is_relevant(c, step)
    ]

    # 3. enforce boundary
    if not filtered: 
        # return handle_out_of_scope(query, step)
        # Add soft fallback instead -> this prevents total failure
        filtered = context_chunks[:2]
    
    if not filtered:
        return handle_out_of_scope(query, step)
    
    # if similarity too low -> reject
    query_vec = np.array(get_embedding(query))
    top_chunk_vec = np.array(get_embedding(filtered[0]["content"]))

    top_score = store.cosine_similarity(query_vec, top_chunk_vec)
    
    if top_score < 0.5:
        return handle_out_of_scope(query, step)
    
    # context = retrieve_context(
    #     query=query,
    #     rag_topic=step.rag_topic
    # )

    #👉 retrieve_context was doing too much implicitly:
    # search
    # filtering
    # fallback

    # 4. Build context
    context = "\n\n".join([
        f"[{c['topic']}]\n{c['content']}"
        for c in filtered
    ])

    prompt = build_prompt_with_step(
        query=query,
        context=context,
        step=step
    )

    return generate_response(prompt)