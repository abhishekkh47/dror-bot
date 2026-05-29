from app.core.types import Step

DOMAIN_TITLES = {
    "authentication": "Platform Authentication",
    "platform_setup": "Platform Setup",
    "transactions": "Payment Transactions",
    "webhooks": "Webhook Integration",
    "sockets": "Socket Integration",
    "refunds": "Refunds",
    "disputes": "Disputes",
    "troubleshooting": "Troubleshooting",
}
def build_virtual_step(domain: str) -> Step:
    """
    Construct a Step for free-form QA mode.
    The Step carries the domain for VectorStore filtering.
    It is not part of any flow — it bypasses flow validation.
    """
    return Step(
        id=f"qa_{domain}",
        type="INFO",
        title=DOMAIN_TITLES.get(domain, f"DrorPay {domain}"),
        description=f"Developer question about DrorPay {domain}",
        domain=[domain],
        rag_topic=domain,
        next=None,
    )