from app.core.types import Step

EVAL_STEPS = {
    "payment-status-step": Step(
        id="payment-status-step",
        title="Payment Status",
        domain=["payment_status"],
        rag_topic="payment_status",
        type="INFO",
        description="Payment status debugging step",
    ),
    "platform-transaction-step": Step(
        id="platform-transaction-step",
        title="Platform Transaction",
        domain=["platform_transaction"],
        rag_topic="platform_transaction",
        type="INFO",
        description="Platform transaction step",
    ),
    "auto-completion-step": Step(
        id="auto-completion-step",
        title="Auto Completion",
        domain=["auto_completion"],
        rag_topic="auto_completion",
        type="INFO",
        description="Auto completion step",
    ),
}

MOCK_STEP = EVAL_STEPS["payment-status-step"]
