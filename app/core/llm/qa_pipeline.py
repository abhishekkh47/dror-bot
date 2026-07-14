"""
Lightweight QA pipeline for free-form developer queries.

Uses VectorStore retrieval and generate_response() but skips the
payment-lifecycle layers (extract_lifecycle_facts, validate_retrieval_quality,
operational_distiller) which are specialized for payment state machines and
would misfire on authentication/webhook/refund domain questions.
"""
from typing import AsyncGenerator
from app.core.knowledge.domain_classifier import classify_query_domain
from app.core.knowledge.virtual_step import build_virtual_step
from app.core.knowledge.scope_guard import enforce_drorpay_scope
from app.core.llm.retriever import store
from app.core.llm.llm import generate_response, stream_response
from app.core.security.request_guard import validate_request
from app.core.types import QueryResponse, SourceCitation
from app.core.session_store import SessionStore

QA_SYSTEM_PROMPT = """You are DrorBot, the official DrorPay integration assistant.
You help third-party developers integrate DrorPay into their applications.

DOMAIN: {domain}

CONTEXT (answer from this only):
{context}

CONVERSATION HISTORY:
{history}

RULES:
- Use only the provided context. If it lacks the answer, say so clearly.
- Do not invent API fields, endpoints, or behaviors not in the context.
- Copy field names, header names, event names, endpoint paths, and algorithm names verbatim.
- Include code examples when the context contains them.
- Be precise and concise (3-5 sentences unless a code example is needed).
- When providing an answer, you MUST append a citation block at the end referencing the source topics used. Use the format: `[Source: TOPIC]`.

QUESTION: {query}

ANSWER:"""

NO_CONTEXT_RESPONSE = (
    "I don't have specific documentation for that query in my current knowledge base. "
    "Please refer to the DrorPay integration documentation or contact the DrorPay support team."
)

async def answer_query(query: str, session_id: str = "default", session_store: SessionStore = None) -> QueryResponse:
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
    top_scored_chunks = [(score, chunk) for score, chunk in scored_chunks[:3] if score > 0.4]
    if not top_scored_chunks:
        top_scored_chunks = [scored_chunks[0]]

    top_chunks = [chunk for score, chunk in top_scored_chunks]

    context = "\n\n".join([
        f"[{c['topic']}]\n{c['content']}"
        for c in top_chunks
    ])

    confidence = float(scored_chunks[0][0]) if scored_chunks else 0.0

    history_text = "No previous conversation."
    session = None
    if session_store:
        try:
            session = session_store.get(session_id)
        except Exception:
            session = session_store.create_qa_session(session_id)
        if session.history:
            history_text = "\n".join(session.history[-6:])

    prompt = QA_SYSTEM_PROMPT.format(
        domain=domain,
        context=context,
        history=history_text,
        query=query,
    )
    
    response = generate_response(prompt)
    
    if session and session_store:
        session.history.append(f"User: {query}")
        session.history.append(f"Assistant: {response.strip()}")
        session_store.update(session)

    citations = [
        {
            "file_name": chunk["topic"],
            "snippet": chunk["content"][:200] + "..." if len(chunk["content"]) > 200 else chunk["content"],
            "relevance_score": float(score)
        }
        for score, chunk in top_scored_chunks
    ]

    return QueryResponse(
        answer=response.strip(),
        domain=domain,
        mode="answered",
        confidence=confidence,
        citations=citations
    )


def _build_qa_prompt(query: str, session_id: str = "default", session_store: SessionStore = None):
    """
    Shared logic: validate → classify → retrieve → build prompt.
    Returns (error_message_or_None, prompt, confidence, session).
    If error_message is not None, the caller should stream that message directly.
    """
    is_valid, validation_error = validate_request(query)
    if not is_valid:
        return validation_error, "", 0.0, None

    domain = classify_query_domain(query)

    allowed, reason = enforce_drorpay_scope(domain)
    if not allowed:
        return reason, "", 0.0, None

    virtual_step = build_virtual_step(domain)
    scored_chunks = store.search(query, step=virtual_step, top_k=6)

    if not scored_chunks:
        return NO_CONTEXT_RESPONSE, "", 0.0, None

    top_chunks = [chunk for score, chunk in scored_chunks[:3] if score > 0.4]
    if not top_chunks:
        top_chunks = [scored_chunks[0][1]]

    context = "\n\n".join([
        f"[{c['topic']}]\n{c['content']}"
        for c in top_chunks
    ])
    confidence = float(scored_chunks[0][0])
    
    history_text = "No previous conversation."
    session = None
    if session_store:
        try:
            session = session_store.get(session_id)
        except Exception:
            session = session_store.create_qa_session(session_id)
        if session.history:
            history_text = "\n".join(session.history[-6:])

    prompt = QA_SYSTEM_PROMPT.format(domain=domain, context=context, history=history_text, query=query)
    return None, prompt, confidence, session


async def stream_query(query: str, session_id: str = "default", session_store: SessionStore = None) -> AsyncGenerator[str, None]:
    """
    Streaming version of answer_query.
    Yields tokens as they are generated by the LLM.
    Used by the POST /query/stream SSE endpoint.

    Early-exit messages (blocked, out_of_scope, no_context) are yielded
    as a single chunk so the client always receives something.
    """
    error, prompt, _, session = _build_qa_prompt(query, session_id, session_store)
    if error:
        yield error
        return

    full_response = []
    for token in stream_response(prompt):
        full_response.append(token)
        yield token
        
    if session and session_store:
        session.history.append(f"User: {query}")
        session.history.append(f"Assistant: {''.join(full_response).strip()}")
        session_store.update(session)


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