from app.core.llm.llm import generate_response

CLASSIFICATION_PROMPT = """You are a DrorPay query classifier.

Classify the user query into exactly ONE of these domains:

- authentication: API headers, JWT tokens, X-Platform-Secret, X-Platform-Code, auth errors, credentials, KYC, phone verification, 401 errors
- platform_setup: creating a platform, generating platform secret, platform onboarding, platform slug, admin setup, retrieve secret
- transactions: create-intent, payment creation, transaction status, listing transactions, platform_order_id, platform_transaction_id, auto-completion, does the user approve, auto-complete, payment lifecycle, when does a payment complete
- webhooks: webhook events, payment callback URL, webhook signature, HMAC verification, retry behavior, payment.created, payment.completed, delivery
- sockets: socket.io, real-time updates, join-payment-room, payment room, socket events, websocket, when to join
- refunds: cancel-and-refund, partial refund, full refund, refund amount, platform_transaction_detail_ids, fees refunded
- disputes: dispute creation, dispute status, dispute resolution, flagging transactions
- troubleshooting: payment failed, payment cancelled, errors, debugging, signature fails, P2P not allowed, not receiving webhooks, unauthorized transaction, chargeback, money deducted, funds not received
- out_of_scope: geography, history, science, cooking, sports, React, Python tutorials, unrelated to DrorPay

User query: {query}

Respond with ONLY the domain name, nothing else. No explanation."""

VALID_DOMAINS = {
    "authentication", "platform_setup", "transactions", "webhooks",
    "sockets", "refunds", "disputes", "troubleshooting", "out_of_scope",
}

# Minimum signal words that indicate a query is DrorPay-related.
# If NONE of these appear in the query, skip the LLM call and return out_of_scope immediately.
_DRORPAY_SIGNAL_WORDS = {
    "drorpay", "platform", "payment", "webhook", "socket", "jwt", "token",
    "intent", "refund", "dispute", "transaction", "authentication", "auth",
    "api", "callback", "signature", "hmac", "header", "secret", "slug",
    "kyc", "wallet", "sender", "receiver", "merchant", "create-intent",
    "cancel", "x-platform", "x-drorpay", "status", "credential",
}


def _has_drorpay_signal(query: str) -> bool:
    """Return True if the query contains at least one DrorPay-related term."""
    words = set(query.lower().split())
    # Also check raw string for hyphenated terms like "create-intent"
    return bool(words & _DRORPAY_SIGNAL_WORDS) or any(
        term in query.lower() for term in ("create-intent", "x-platform", "x-drorpay")
    )


def classify_query_domain(query: str) -> str:
    """
    Classify a user query into a DrorPay knowledge domain.

    Fast path: if the query contains no DrorPay signal words, return
    'out_of_scope' immediately without an LLM call.

    Slow path: call gemma:2b with a focused classification prompt.
    If the query passed the keyword pre-check, we never return 'out_of_scope'
    from the LLM — the keyword check is the authoritative scope gate.
    Falls back to 'transactions' if the LLM returns ambiguous output.
    """
    if not _has_drorpay_signal(query):
        return "out_of_scope"

    prompt = CLASSIFICATION_PROMPT.format(query=query.strip())
    raw = generate_response(prompt).strip().lower()

    # Exact match — skip out_of_scope because query already passed keyword check
    if raw in VALID_DOMAINS and raw != "out_of_scope":
        return raw

    # Substring match — handles verbose model output; skip out_of_scope
    for domain in VALID_DOMAINS:
        if domain in raw and domain != "out_of_scope":
            return domain

    # Default to transactions (most common developer query type)
    return "transactions"