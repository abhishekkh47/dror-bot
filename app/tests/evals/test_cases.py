from app.core.types import Step


TEST_CASES = [
    {
        "name": "cancellation_after_processing",
        "query": "why was payment cancelled?",
        "step": Step(
            id="payment-status-step",
            title="Payment Status",
            domain=["payment_status"],
            rag_topic="payment_status",
            type="INFO",
            description="Payment status debugging step",
        ),
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
        "step": Step(
            id="auto-completion-step",
            title="Auto Completion",
            domain=["auto_completion"],
            rag_topic="auto_completion",
            type="INFO",
            description="Auto completion step",
        ),
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
        "step": Step(
            id="platform-transaction-step",
            title="Platform Transaction",
            domain=["platform_transaction"],
            rag_topic="platform_transaction",
            type="INFO",
            description="Platform transaction step",
        ),
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