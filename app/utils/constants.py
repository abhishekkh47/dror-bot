TAG_PRIORITY = {
    "failure": 2.5,
    "success": 1.8,
    "error_handling": 2.2,
    "webhook": 1.5,
    "status": 1.5,
    "api": 1.2,
    "authentication": 1.2,
    "flow": 1.1
}

CRITICAL_TAGS = {
    "failure": 2.0,
    "error": 1.8,
    "cancellation": 1.7,
    "rollback": 1.6
}

CONTEXT_TAGS = {
    "api": 1.2,
    "flow": 1.1,
    "processing": 1.1,
    "status": 1.0
}

INTENT_DEFINITIONS = {
    "failure": [
        "payment failed",
        "transaction failed",
        "payment cancelled",
        "payment did not complete",
        "payment error",
        "payment unsuccessful"
    ],
    "success": [
        "payment successful",
        "transaction completed",
        "payment done"
    ]
}

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