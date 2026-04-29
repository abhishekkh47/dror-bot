from app.core.llm.retriever import retrieve_context
from app.core.llm.prompt import build_prompt
from app.core.llm.llm import generate_response

def ask(query: str):
    context = retrieve_context(query)
    prompt = build_prompt(query, context)
    response = generate_response(prompt)
    return response