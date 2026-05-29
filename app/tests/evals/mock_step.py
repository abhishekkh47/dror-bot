from app.core.types import Step
from app.core.knowledge.virtual_step import build_virtual_step

EVAL_STEPS = {
    # Existing payment-lifecycle steps.
    # domain=["create_intent"] matches create_intent_* chunk topics in the knowledge base.
    "payment-status-step": Step(
        id="payment-status-step",
        title="Payment Status",
        domain=["create_intent"],
        rag_topic="create_intent_failure",
        type="INFO",
        description="Payment status debugging step",
    ),
    "platform-transaction-step": Step(
        id="platform-transaction-step",
        title="Platform Transaction",
        domain=["create_intent"],
        rag_topic="create_intent_lifecycle",
        type="INFO",
        description="Platform transaction step",
    ),
    "auto-completion-step": Step(
        id="auto-completion-step",
        title="Auto Completion",
        domain=["create_intent"],
        rag_topic="create_intent_auto_completion",
        type="INFO",
        description="Auto completion step",
    ),
    # QA domain virtual steps — routed through answer_query() in regression_runner
    "qa_authentication": build_virtual_step("authentication"),
    "qa_platform_setup": build_virtual_step("platform_setup"),
    "qa_transactions": build_virtual_step("transactions"),
    "qa_webhooks": build_virtual_step("webhooks"),
    "qa_sockets": build_virtual_step("sockets"),
    "qa_refunds": build_virtual_step("refunds"),
    "qa_disputes": build_virtual_step("disputes"),
    "qa_troubleshooting": build_virtual_step("troubleshooting"),
    "qa_out_of_scope": build_virtual_step("troubleshooting"),  # placeholder; runner blocks on scope
}

MOCK_STEP = EVAL_STEPS["payment-status-step"]
