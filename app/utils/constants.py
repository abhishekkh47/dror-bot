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
    "failure": 3.0,
    "success": 2.5,
}

CONTEXT_TAGS = {
    "error_handling": 1.5,
    "webhook": 1.5,
    "status": 1.5,
    "api": 1.2,
    "flow": 1.1
}

INTENT_DEFINITIONS = {
    "creation_failure": [
        "intent creation failed",
        "api failed to create intent"
    ],
    "processing_failure": [
        "payment failed after processing",
        "auto completion failed",
        "payment cancelled",
        "payment didn't complete"
    ],
    "success": [
        "payment successful",
        "transaction completed"
    ]
}