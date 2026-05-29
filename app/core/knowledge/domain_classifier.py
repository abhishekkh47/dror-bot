from app.core.llm.llm import generate_response

CLASSIFICATION_PROMPT = """You are a DrorPay query classifier.

Classify the user query into exactly ONE of these domains:

- authentication: API headers, JWT tokens, X-Platform-Secret, X-Platform-Code, auth errors, credentials, KYC, phone verification
- platform_setup: creating a platform, generating platform secret, platform onboarding, platform slug, admin setup
- transactions: create-intent, payment creation, transaction status, listing transactions, platform_order_id, platform_transaction_id, auto-completion
- webhooks: webhook events, payment callback URL, webhook signature, HMAC verification, retry behavior, payment.created, payment.completed
- sockets: socket.io, real-time updates, join-payment-room, payment room, socket events, websocket
- refunds: cancel-and-refund, partial refund, full refund, refund amount, platform_transaction_detail_ids
- disputes: dispute creation, dispute status, dispute resolution, flagging transactions
- troubleshooting: payment failed, payment cancelled immediately, errors, debugging, signature fails, P2P not allowed
- out_of_scope: anything unrelated to DrorPay integration

User query: {query}

Respond with ONLY the domain name, nothing else. No explanation."""

VALID_DOMAINS = {
    "authentication", "platform_setup", "transactions", "webhooks",
    "sockets", "refunds", "disputes", "troubleshooting", "out_of_scope",
}

def classify_query_domain(query: str) -> str:
    """
    Classify a user query into a Drorpay knowledge domain using the LLM.
    Returns domain name string. Falls back to 'transactions' if LLM returns invalid output.
    """
    prompt = CLASSIFICATION_PROMPT.format(query=query.strip())
    raw = generate_response(prompt).strip().lower()

    # Exact match first
    if raw in VALID_DOMAINS:
        return raw
    
    # Check if any valid domain appears in the response (handles verbose LLM output)
    for domain in VALID_DOMAINS:
        if domain in raw:
            return domain

    # Default to transactions (most common developer query type)
    return "transactions"