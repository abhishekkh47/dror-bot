import json

from app.core.llm.qa_pipeline import answer_query
from app.core.llm.rag_pipeline import ask_with_context
from app.tests.evals.mock_step import EVAL_STEPS, MOCK_STEP


async def run_regression_suite(step=None):
    """
    Run structured regression suite.

    Routing:
    - step_id starts with "qa_" → answer_query() (lightweight QA pipeline)
    - all other step_ids → ask_with_context() (flow/lifecycle pipeline)

    Each pipeline returns different result shapes:
    - answer_query() → QueryResponse (fields: answer, domain, mode, confidence)
    - ask_with_context() → ExecutionResult (fields: response, response_mode, ...)
    """

    with open("app/tests/evals/eval_dataset.json") as f:
        dataset = json.load(f)

    results = []

    for test in dataset:
        step_id = test.get("step_id", "")
        is_qa_case = step_id.startswith("qa_")

        if is_qa_case:
            result = await answer_query(
                query=test["query"],
                session_id=f"eval_{test['id']}",
            )
            response_text = result.answer
            response_mode = result.mode
            reliability_score = int(result.confidence * 100)
            escalated = False
        else:
            test_step = EVAL_STEPS.get(step_id, step or MOCK_STEP)
            result = await ask_with_context(
                query=test["query"],
                step=test_step,
                session_id=f"eval_{test['id']}",
            )
            response_text = result.response
            response_mode = result.response_mode
            reliability_score = result.response_reliability_score
            escalated = result.human_escalation_required

        response_lower = response_text.lower()
        passed = True
        failures = []

        for pattern in test.get("expected_response_patterns", []):
            if pattern.lower() not in response_lower:
                passed = False
                failures.append(f"Missing expected pattern: '{pattern}'")

        for pattern in test.get("forbidden_patterns", []):
            if pattern.lower() in response_lower:
                passed = False
                failures.append(f"Found forbidden pattern: '{pattern}'")

        expected_mode = test.get("expected_response_mode")
        if expected_mode and response_mode != expected_mode:
            passed = False
            failures.append(
                f"Response mode: expected '{expected_mode}', got '{response_mode}'"
            )

        if not is_qa_case:
            expected_escalation = test.get("expected_escalation")
            if expected_escalation is not None and escalated != expected_escalation:
                passed = False
                failures.append(
                    f"Escalation: expected {expected_escalation}, got {escalated}"
                )

        results.append({
            "id": test["id"],
            "passed": passed,
            "failures": failures,
            "response_mode": response_mode,
            "reliability_score": reliability_score,
            "escalated": escalated,
        })

    return results
