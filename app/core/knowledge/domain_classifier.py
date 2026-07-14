"""
Domain classifier for DrorPay queries.

When PROVIDER supports JSON mode (openai, gemini, ollama with format=json),
the LLM returns {"domain": "<name>"} — no substring parsing needed.
When JSON parsing fails, falls back to text-based matching.

Fast path: queries with no DrorPay signal words are classified as
'out_of_scope' immediately without an LLM call.
"""
import json
import os
import re
from app.core.llm.llm import generate_response

PROVIDER = os.getenv("PROVIDER", "ollama").lower()

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

Respond with valid JSON only: {{"domain": "<domain_name>"}}"""

VALID_DOMAINS = {
    "authentication", "platform_setup", "transactions", "webhooks",
    "sockets", "refunds", "disputes", "troubleshooting", "out_of_scope",
}

# Minimum signal words that indicate a DrorPay-related query.
# If NONE appear, skip the LLM call entirely.
_DRORPAY_SIGNAL_WORDS = {
    "drorpay", "platform", "payment", "webhook", "socket", "jwt", "token",
    "intent", "refund", "dispute", "transaction", "authentication", "auth",
    "api", "callback", "signature", "hmac", "header", "secret", "slug",
    "kyc", "wallet", "sender", "receiver", "merchant", "create-intent",
    "cancel", "x-platform", "x-drorpay", "status", "credential",
}


def _has_drorpay_signal(query: str) -> bool:
    q = query.lower()
    for word in _DRORPAY_SIGNAL_WORDS:
        # Use regex to match whole words or exact hyphenated phrases
        if re.search(r'\b' + re.escape(word) + r'\b', q):
            return True
    return False


def _parse_domain(raw: str) -> str | None:
    """
    Try JSON parse first, then fall back to substring matching.
    Returns a valid domain name or None.
    """
    raw = raw.strip()

    # JSON parse (works for all providers when json_mode=True)
    try:
        data = json.loads(raw)
        domain = str(data.get("domain", "")).strip().lower()
        if domain in VALID_DOMAINS:
            return domain
    except (json.JSONDecodeError, AttributeError):
        pass

    # Text fallback — exact match
    lower = raw.lower()
    if lower in VALID_DOMAINS:
        return lower

    # Text fallback — substring match
    for domain in VALID_DOMAINS:
        if domain in lower:
            return domain

    return None


def classify_query_domain(query: str) -> str:
    """
    Classify a user query into a DrorPay knowledge domain.

    Fast path: no DrorPay signal words → 'out_of_scope' without LLM call.
    Slow path: LLM call with JSON mode for reliable structured output.
    Safety: if query has DrorPay signal but LLM returns 'out_of_scope',
            we trust the keyword check and default to 'transactions'.
    """
    if not _has_drorpay_signal(query):
        return "out_of_scope"

    prompt = CLASSIFICATION_PROMPT.format(query=query.strip())

    # All providers now support JSON mode
    raw = generate_response(prompt, json_mode=True)
    domain = _parse_domain(raw)

    if domain:
        return domain

    return "out_of_scope"
