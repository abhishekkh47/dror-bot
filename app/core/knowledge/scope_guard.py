OUT_OF_SCOPE_RESPONSE = (
    "I can only answer questions about DrorPay integration — "
    "API usage, authentication, payment flows, webhooks, sockets, "
    "refunds, disputes, platform setup, and troubleshooting. "
    "Please ask a question related to integrating or using the DrorPay platform."
)

VALID_DOMAINS = {
    "authentication", "platform_setup", "transactions", "webhooks",
    "sockets", "refunds", "disputes", "troubleshooting",
}


def enforce_drorpay_scope(domain: str) -> tuple[bool, str | None]:
    """Returns (allowed, reason_if_blocked)."""
    if domain == "out_of_scope" or domain not in VALID_DOMAINS:
        return False, OUT_OF_SCOPE_RESPONSE
    return True, None