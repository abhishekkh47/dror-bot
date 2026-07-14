


TEST_CASES = [
    {
        "name": "cancellation_after_processing",
        "query": "why was payment cancelled?",
        "domain": "payment_status",
        "must_include": [
            "cancel",
        ],
        "must_not_include": [
            "intent creation failed",
            "payment intent creation failed",
            "webhook",
            "socket",
        ],
        "expected_final_state": "cancelled",
    },
    {
        "name": "processing_failure",
        "query": "payment didn't complete",
        "domain": "auto_completion",
        "must_include": [
            "failed",
        ],
        "must_not_include": [
            "intent creation failed",
            "webhook",
            "socket",
        ],
        "expected_final_state": "failed",
    },
    {
        "name": "post_processing_failure",
        "query": "transaction failed after processing",
        "domain": "platform_transaction",
        "must_include": [
            "processing",
        ],
        "must_not_include": [
            "intent creation failed",
            "creation failed after processing",
        ],
        "expected_final_state": "failed",
    },
]