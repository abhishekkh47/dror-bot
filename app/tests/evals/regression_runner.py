import json

from app.core.llm.rag_pipeline import ask_with_context
from app.tests.evals.mock_step import EVAL_STEPS, MOCK_STEP


async def run_regression_suite(step=None):
    """
    Run structured regression suite.
    Each test case can specify its own step_id,
    falling back to the provided step or MOCK_STEP.
    """

    with open("app/tests/evals/eval_dataset.json") as f:
        dataset = json.load(f)

    results = []

    for test in dataset:
        test_step = EVAL_STEPS.get(
            test.get("step_id", ""),
            step or MOCK_STEP,
        )

        result = await ask_with_context(
            query=test["query"],
            step=test_step,
            session_id=f"eval_{test['id']}",
        )

        response_lower = result.response.lower()
        passed = True
        failures = []

        for pattern in test.get("expected_response_patterns", []):
            if pattern not in response_lower:
                passed = False
                failures.append(
                    f"Missing expected pattern: '{pattern}'"
                )

        for pattern in test.get("forbidden_patterns", []):
            if pattern in response_lower:
                passed = False
                failures.append(
                    f"Found forbidden pattern: '{pattern}'"
                )

        expected_mode = test.get("expected_response_mode")
        if expected_mode and result.response_mode != expected_mode:
            passed = False
            failures.append(
                f"Response mode: expected '{expected_mode}', got '{result.response_mode}'"
            )

        expected_escalation = test.get("expected_escalation")
        if expected_escalation is not None and result.human_escalation_required != expected_escalation:
            passed = False
            failures.append(
                f"Escalation: expected {expected_escalation}, got {result.human_escalation_required}"
            )

        results.append({
            "id": test["id"],
            "passed": passed,
            "failures": failures,
            "response_mode": result.response_mode,
            "reliability_score": result.response_reliability_score,
            "escalated": result.human_escalation_required,
        })

    return results
