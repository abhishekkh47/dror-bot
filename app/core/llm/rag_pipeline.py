from app.core.llm.retriever import retrieve_context, store
from app.core.llm.prompt import build_prompt, build_prompt_with_step
from app.core.llm.llm import generate_response

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

    # 2. strict topic filter
    filtered = [
        c for c in context_chunks if c['topic'] == step.rag_topic
    ]

    # 3. enforce boundary
    if not filtered: 
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