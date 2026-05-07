from app.utils.prompts import LIFECYCLE_RULES, PROMPT_TEMPLATE, RESPONSE_RULES, SYSTEM_RULES


def build_prompt(query: str, context: str) -> str:
    return f"""
    You are a drorpay integration assistant.

    Rules:
    - Only use provided context
    - Answer ONLY what is asked
    - Do not invent APIs
    - If missing, say: Not available in public docs
    - Do not mention internal phases, step numbers, or system internals
    - Do not add extra details unless explicitly required

    Context: 
    {context}

    Question: 
    {query}

    Answer:
    """

def build_prompt_with_step_v1(query: str, context: str, step) -> str:
    return f"""
    You are an API integration assistant.

    Your job is to answer the user's question ONLY using the provided context.
    
    Your task is factual extraction, not explanation.

    Only restate facts explicitly present in context.
    Do not generalize or interpret beyond the provided information.

    -----------------------------------
    USER QUESTION
    -----------------------------------
    {query}

    -----------------------------------
    CURRENT STEP
    -----------------------------------
    Step: {step.title}
    Description: {step.description}

    -----------------------------------
    CONTEXT
    -----------------------------------
    {context}

    -----------------------------------
    CORE RULES
    -----------------------------------
    1. Use ONLY information explicitly present in the context.
    2. Do NOT invent APIs, flows, statuses, timelines, or behaviors.
    3. If the answer is not clearly present in the context, say:
    "The provided context does not contain this information."

    4. Do NOT infer missing implementation details.
    5. Do NOT generalize beyond the provided context.
    6. Answer ONLY the user's actual question.
    7. Keep the answer concise and operational.
    8. Do NOT infer possible causes.
    9. Do NOT provide examples unless explicitly present in context.
    10. Do NOT explain generic payment failure scenarios.

    -----------------------------------
    IMPORTANT FACTS
    -----------------------------------
    - Payment intent creation and payment processing are DIFFERENT phases.
    - In this context:
        - the payment intent WAS already created
        - the failure happened LATER during processing or auto-completion
    - Therefore:
        - NEVER incorrectly describe a processing failure
        as an intent creation failure.
    - If failure occurs after creation:
        describe it as:
        - failure during processing
        - failure during auto-completion
        - failure after intent creation
    - Mention webhooks, socket events, polling, notifications,
    or internal signals ONLY if the user explicitly asks about them.
    - Ignore unrelated implementation details even if they appear in context.

    -----------------------------------
    QUERY-AWARE ANSWERING
    -----------------------------------
    Tailor the answer specifically to the user's wording.
    Examples:
    - If user asks:
    "why was payment cancelled?"
    → explain the cancellation cause

    - If user asks:
    "payment didn't complete"
    → explain incomplete processing outcome

    - If user asks:
    "transaction failed after processing"
    → explain failure timing/stage after processing started

    Do NOT give the same generic answer to every failure-related query.

    -----------------------------------
    GOOD VS BAD ANSWERS
    -----------------------------------
    BAD:
    "The payment intent creation failed."
    WHY BAD:
    This incorrectly mixes intent creation
    with later processing failure.
    GOOD:
    "The payment failed during processing after intent creation."

    BAD:
    "The webhook was not sent."
    WHY BAD:
    The user did not ask about webhooks.
    GOOD:
    "The payment was cancelled during auto-completion."

    -----------------------------------
    ANSWER STRUCTURE
    -----------------------------------
    Structure the answer as:
    1. What failed
    2. When/stage it failed
    3. Outcome/result only if relevant

    -----------------------------------
    RESPONSE STYLE
    -----------------------------------
    - Maximum 2-4 sentences
    - No markdown headings
    - No bullet points unless explicitly requested
    - No speculative explanations
    - No architectural assumptions
    - Prefer operational facts over implementation details

    -----------------------------------
    ANSWER
    -----------------------------------
    """

def build_prompt_with_step(
    query: str,
    context: str,
    step,
    response_pattern: str,
    failure_summary: dict,
    operational_evidence: list[str]
) -> str:
    evidence_block = "\n".join([
        f"- {item}"
        for item in operational_evidence
    ])

    return PROMPT_TEMPLATE.format(
        system_rules=SYSTEM_RULES,

        query=query,

        step_title=step.title,
        step_description=step.description,

        intent_created=failure_summary.intent_created,
        processing_started=failure_summary.processing_started,
        processing_failed=failure_summary.processing_failed,
        transaction_cancelled=failure_summary.transaction_cancelled,
        final_state=failure_summary.final_state,

        lifecycle_rules=LIFECYCLE_RULES,
        operational_evidence=evidence_block,
        context=context,
        response_rules=RESPONSE_RULES,
        response_pattern=response_pattern,
    )