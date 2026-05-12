from app.core.llm.rag_pipeline import ask_with_context

from app.tests.evals.evaluation_metrics import score_response_quality
from app.tests.evals.execution_metrics import build_execution_metrics
from app.tests.evals.test_cases import TEST_CASES


def evaluate_response(test_case, response):
    """
    Evaluate lifecycle correctness and safety constraints.
    """

    response_lower = response.lower()

    passed = True
    failures = []

    # Required phrases
    for phrase in test_case["must_include"]:
        if phrase.lower() not in response_lower:
            passed = False
            failures.append(
                f"Missing required phrase: {phrase}"
            )

    # Forbidden phrases
    for phrase in test_case["must_not_include"]:
        if phrase.lower() in response_lower:
            passed = False
            failures.append(
                f"Forbidden phrase detected: {phrase}"
            )

    return {
        "passed": passed,
        "failures": failures,
    }


def run_all_evals():
    """
    Run all regression evaluations.
    """

    results = []

    for test_case in TEST_CASES:
        result = ask_with_context(test_case["query"], test_case["step"])
        response = result.response
        execution_metrics = build_execution_metrics(result)

        print(f"RESPONSE:\n{response}")
        print("\nEXECUTION METRICS:")
        for key, value in execution_metrics.items():
            print(f"- {key}: {value}")
        
        evaluation = evaluate_response(
            test_case,
            response
        )

        results.append({
            "test": test_case["name"],
            "query": test_case["query"],
            "response": response,
            "passed": evaluation["passed"],
            "failures": evaluation["failures"],
        })

    return results