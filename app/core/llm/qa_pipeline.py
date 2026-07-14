"""
Lightweight QA pipeline for free-form developer queries.

Uses VectorStore retrieval and generate_response() but skips the
payment-lifecycle layers (extract_lifecycle_facts, validate_retrieval_quality,
operational_distiller) which are specialized for payment state machines and
would misfire on authentication/webhook/refund domain questions.
"""
from typing import AsyncGenerator
from app.core.knowledge.domain_classifier import classify_query_domain
from app.core.knowledge.scope_guard import enforce_drorpay_scope
from app.core.llm.retriever import store
from app.core.llm.llm import generate_response, stream_response
from app.core.security.request_guard import validate_request
from app.core.types import QueryResponse, SourceCitation
from app.core.session_store import SessionStore
import time
import logging

logger = logging.getLogger("drorbot.telemetry")
logger.setLevel(logging.INFO)

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

REFORMULATE_PROMPT = """Given the following conversation history and a follow-up query, rephrase the follow-up query to be a standalone query that can be used to search a knowledge base.
Do not answer the query, just rewrite it. If the query is already standalone, return it as is.

CONVERSATION HISTORY:
{history}

FOLLOW-UP QUERY: {query}

STANDALONE QUERY:"""

FALLBACK_PROMPT = """A developer asked a question about DrorPay but our knowledge base did not contain the answer. 
Write a brief, polite response acknowledging the specific question they asked, explaining we lack documentation on it, and suggesting they contact support or check the main API docs.
Keep it under 3 sentences.

QUESTION: {query}"""

async def answer_query(query: str, session_id: str = None, session_store: SessionStore = None) -> QueryResponse:
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
    start_time = time.time()
    
    is_valid, validation_error = validate_request(query)
    if not is_valid:
        return QueryResponse(
            answer=validation_error,
            domain="blocked",
            mode="blocked",
            session_id=session_id or "",
            confidence=0.0,
        )
    
    history_text = "No previous conversation."
    session = None
    if session_store and session_id:
        try:
            session = session_store.get(session_id)
        except Exception:
            session = session_store.create_qa_session(session_id)
        if session.history:
            history_text = "\n".join(session.history[-6:])

    search_query = query
    if session and session.history:
        reformulated = generate_response(REFORMULATE_PROMPT.format(history=history_text, query=query)).strip()
        search_query = reformulated if reformulated else query
    
    domain = classify_query_domain(search_query)

    allowed, reason = enforce_drorpay_scope(domain)
    if not allowed:
        return QueryResponse(
            answer=reason,
            domain="out_of_scope",
            mode="blocked",
            session_id=session_id or "",
            confidence=0.0,
        )

    scored_chunks = store.search(search_query, domain=domain, top_k=6)

    # Filter for high relevance chunks
    top_scored_chunks = [(score, chunk) for score, chunk in scored_chunks[:3] if score > 0.4]
    
    # If no highly relevant chunks found with domain filter, try without it
    if not top_scored_chunks:
        fallback_chunks = store.search(search_query, domain=None, top_k=6)
        top_scored_chunks = [(score, chunk) for score, chunk in fallback_chunks[:3] if score > 0.4]
        if not top_scored_chunks and fallback_chunks:
            top_scored_chunks = [fallback_chunks[0]]
            scored_chunks = fallback_chunks
            
    if not top_scored_chunks and scored_chunks:
        top_scored_chunks = [scored_chunks[0]]

    if not top_scored_chunks:
        fallback_msg = generate_response(FALLBACK_PROMPT.format(query=query)).strip()
        return QueryResponse(
            answer=fallback_msg,
            domain=domain,
            mode="no_context",
            session_id=session_id or "",
            confidence=0.0,
        )

    top_chunks = [chunk for score, chunk in top_scored_chunks]

    context = "\n\n".join([
        f"[TOPIC: {c.get('topic', 'N/A')}]\n"
        f"[CAPABILITY: {c.get('metadata', {}).get('capability', 'general')}]\n"
        f"[LIFECYCLE: {c.get('metadata', {}).get('lifecycle_stage', 'general')}]\n"
        f"{c['content']}"
        for c in top_chunks
    ])

    confidence = float(scored_chunks[0][0]) if scored_chunks else 0.0

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

    latency = time.time() - start_time
    logger.info(f"[TELEMETRY] type=qa_response | mode=answered | latency={latency:.2f}s | confidence={confidence:.2f} | domain={domain}")

    return QueryResponse(
        answer=response.strip(),
        domain=domain,
        mode="answered",
        session_id=session_id or "",
        confidence=confidence,
        citations=citations
    )


def _build_qa_prompt(query: str, session_id: str = None, session_store: SessionStore = None):
    """
    Shared logic: validate → classify → retrieve → build prompt.
    Returns (error_message_or_None, prompt, confidence, session).
    If error_message is not None, the caller should stream that message directly.
    """
    is_valid, validation_error = validate_request(query)
    if not is_valid:
        return validation_error, "", 0.0, None

    history_text = "No previous conversation."
    session = None
    if session_store and session_id:
        try:
            session = session_store.get(session_id)
        except Exception:
            session = session_store.create_qa_session(session_id)
        if session.history:
            history_text = "\n".join(session.history[-6:])

    search_query = query
    if session and session.history:
        reformulated = generate_response(REFORMULATE_PROMPT.format(history=history_text, query=query)).strip()
        search_query = reformulated if reformulated else query

    domain = classify_query_domain(search_query)

    allowed, reason = enforce_drorpay_scope(domain)
    if not allowed:
        return reason, "", 0.0, None

    scored_chunks = store.search(search_query, domain=domain, top_k=6)

    # Filter for high relevance chunks
    top_chunks = [chunk for score, chunk in scored_chunks[:3] if score > 0.4]
    
    # If no highly relevant chunks found with domain filter, try without it
    if not top_chunks:
        fallback_chunks = store.search(search_query, domain=None, top_k=6)
        top_chunks = [chunk for score, chunk in fallback_chunks[:3] if score > 0.4]
        if not top_chunks and fallback_chunks:
            top_chunks = [fallback_chunks[0][1]]
            scored_chunks = fallback_chunks
            
    if not top_chunks and scored_chunks:
        top_chunks = [scored_chunks[0][1]]

    if not top_chunks:
        fallback_msg = generate_response(FALLBACK_PROMPT.format(query=query)).strip()
        return fallback_msg, "", 0.0, None

    context = "\n\n".join([
        f"[TOPIC: {c.get('topic', 'N/A')}]\n"
        f"[CAPABILITY: {c.get('metadata', {}).get('capability', 'general')}]\n"
        f"[LIFECYCLE: {c.get('metadata', {}).get('lifecycle_stage', 'general')}]\n"
        f"{c['content']}"
        for c in top_chunks
    ])
    confidence = float(scored_chunks[0][0])

    prompt = QA_SYSTEM_PROMPT.format(domain=domain, context=context, history=history_text, query=query)
    return None, prompt, confidence, session


async def stream_query(query: str, session_id: str = None, session_store: SessionStore = None) -> AsyncGenerator[str, None]:
    """
    Streaming version of answer_query.
    Yields tokens as they are generated by the LLM.
    Used by the POST /query/stream SSE endpoint.

    Early-exit messages (blocked, out_of_scope, no_context) are yielded
    as a single chunk so the client always receives something.
    """
    start_time = time.time()
    error, prompt, confidence, session = _build_qa_prompt(query, session_id, session_store)
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
        
    latency = time.time() - start_time
    logger.info(f"[TELEMETRY] type=qa_stream | mode=answered | latency={latency:.2f}s | confidence={confidence:.2f}")


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