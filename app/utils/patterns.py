RESPONSE_PATTERNS = {
    "cancellation_reason": """
Focus on:
- why cancellation happened
- what stage failed
- final cancelled state

Avoid:
- detailed lifecycle explanation
- broad processing discussion
""",

    "completion_failure": """
Focus on:
- payment did not complete successfully
- operational outcome
- resulting state

Avoid:
- deep cancellation reasoning
- architectural internals
""",

    "post_processing_failure": """
Focus on:
- failure happened AFTER processing started
- distinguish from intent creation failure
- mention processing/auto-completion stage

Avoid:
- generic cancellation explanation
"""
}

CONTRADICTION_PATTERNS = {
    r"payment intent creation failed after processing":
        "payment processing failed after intent creation",

    r"intent creation failed after processing":
        "processing failed after intent creation",

    r"payment intent creation failed during processing":
        "payment processing failed during auto-completion",

    r"intent creation failed during processing":
        "processing failed during auto-completion",

    r"payment intent creation failed because":
        "payment processing failed after intent creation because",

    r"intent creation failed because":
        "processing failed after intent creation because",
}

CLEANUP_PATTERNS = [
    r"Sure, here's the answer to the user's question:\s*",
    r"no 'payment\.created' webhook was sent\.?",
    r"no 'payment\.cancelled' webhook was sent\.?",
]

INTERNAL_PATTERNS = [
    r"no\s+'.*?webhook.*?\.",
    r"no\s+\".*?webhook.*?\.",
    r".*webhook was sent\.?",
    r".*webhooks were sent\.?",
    r".*socket event.*?\.",
]

NOISE_PATTERNS = [
    # Socket internals
    r".*socket event.*",
    r".*room payment-order.*",
    r".*socket emitted.*",

    # Webhook internals
    r".*webhook.*",
    r".*callback url.*",
    r".*retry.*",

    # Audit / observability
    r".*audit.*",
    r".*logging.*",

    # Infra / transaction mechanics
    r".*database transaction.*",
    r".*wallet lock.*",
    r".*locks wallets.*",

    # Notification systems
    r".*push notification.*",
    r".*whatsapp.*",
]