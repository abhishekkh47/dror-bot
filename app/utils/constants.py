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