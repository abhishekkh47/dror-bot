"""
Lightweight QA pipeline for free-form developer queries.

Uses VectorStore retrieval and generate_response() but skips the
payment-lifecycle layers (extract_lifecycle_facts, validate_retrieval_quality,
operational_distiller) which are specialized for payment state machines and
would misfire on authentication/webhook/refund domain questions.
"""
from app.core.knowledge.domain_classifier import classify_query_domain
from app.core.knowledge.virtual_step import build_virtual_step
from app.core.knowledge.scope_guard import enforce_drorpay_scope
from app.core.llm.retriever import store
from app.core.llm.llm import generate_response
from app.core.security.request_guard import validate_request
from app.core.types import QueryResponse

QA_SYSTEM_PROMPT = """You are DrorBot, the official DrorPay integration assistant.
You help third-party developers integrate DrorPay into their applications.

DOMAIN: {domain}

CONTEXT (answer from this only — do not invent information):
{context}

STRICT RULES:
- Use only the provided context. If the context does not contain enough information, say so clearly.
- Do not mention internal system details, database schemas, secrets, or admin-only endpoints.
- Do not invent API fields, endpoints, or behaviors not stated in the context.
- Be precise and developer-focused.
- Include code examples only when the context contains them.
- Keep the answer to 3–5 sentences unless a code example is required.

QUESTION: {query}

ANSWER:"""

NO_CONTEXT_RESPONSE = (
    "I don't have specific documentation for that query in my current knowledge base. "
    "Please refer to the DrorPay integration documentation or contact the DrorPay support team."
)

async def answer_query(query: str, session_id: str = "default") -> QueryResponse:
    """
    Full QA pipeline:
    1. Validate request (security guard)
    2. Classify domain via LLM
    3. Enforce DrorPay scope
    4. Retrieve relevant chunks from VectorStore (domain-filtered)
    5. Build focused prompt
    6. Generate response
    7. Return structured result
    """
    is_valid, validation_error = validate_request(query)
    if not is_valid:
        return QueryResponse(
            answer=validation_error,
            domain="blocked",
            mode="blocked",
            confidence=0.0,
        )
    
    domain = classify_query_domain(query)

    allowed, reason = enforce_drorpay_scope(domain)
    if not allowed:
        return QueryResponse(
            answer=reason,
            domain="out_of_scope",
            mode="blocked",
            confidence=0.0,
        )

    virtual_step = build_virtual_step(domain)

    scored_chunks = store.search(query, step=virtual_step, top_k=6)

    if not scored_chunks:
        return QueryResponse(
            answer=NO_CONTEXT_RESPONSE,
            domain=domain,
            mode="no_context",
            confidence=0.0,
        )

    # Take top 3 chunks by score; skip noise-penalized ones if score < 0.4
    top_chunks = [chunk for score, chunk in scored_chunks[:3] if score > 0.4]
    if not top_chunks:
        top_chunks = [scored_chunks[0][1]]

    context = "\n\n".join([
        f"[{c['topic']}]\n{c['content']}"
        for c in top_chunks
    ])

    confidence = float(scored_chunks[0][0]) if scored_chunks else 0.0

    prompt = QA_SYSTEM_PROMPT.format(
        domain=domain,
        context=context,
        query=query,
    )
    
    response = generate_response(prompt)

    return QueryResponse(
        answer=response.strip(),
        domain=domain,
        mode="answered",
        confidence=confidence,
    )

"""
Example usage:
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "how do I create a payment intent?"}' | python -m json.tool

curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "what headers are required?"}' | python -m json.tool

curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "how do I verify webhook signatures?"}' | python -m json.tool

curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the capital of France?"}' | python -m json.tool
"""