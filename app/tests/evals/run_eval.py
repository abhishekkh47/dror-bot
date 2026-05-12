from app.tests.evals.evaluator import run_all_evals


results = run_all_evals()

print("\n" + "=" * 80)
print("RAG EVALUATION RESULTS")
print("=" * 80)

passed_count = 0

for result in results:
    print(f"\nTEST: {result['test']}")
    print(f"QUERY: {result['query']}")
    print(f"PASSED: {result['passed']}")

    print("\nRESPONSE:")
    print(result["response"])

    print("\nEVIDENCE ATTRIBUTION:")
    print(result.evidence_attribution)

    print("\nREASONING BREAKDOWN:")
    print(result.reasoning_breakdown)

    if result["failures"]:
        print("\nFAILURES:")
        for failure in result["failures"]:
            print(f"- {failure}")

    if result["passed"]:
        passed_count += 1

print("\n" + "=" * 80)
print(f"PASSED {passed_count}/{len(results)} TESTS")
print("=" * 80)