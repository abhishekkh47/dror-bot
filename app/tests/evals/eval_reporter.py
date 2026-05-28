def print_eval_report(results):
    """
    Print regression report with failure details.
    """

    total = len(results)
    passed = len([r for r in results if r["passed"]])

    print("\n===================")
    print("REGRESSION RESULTS")
    print("===================")

    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} - {result['id']}")

        if not result["passed"]:
            for failure in result.get("failures", []):
                print(f"       {failure}")

    print("\n-------------------")
    print(f"PASSED {passed}/{total}")

    if passed < total:
        print(f"FAILED {total - passed}/{total}")

    print("===================\n")
