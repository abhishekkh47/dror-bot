import asyncio
from app.tests.evals.regression_runner import run_regression_suite
from app.tests.evals.eval_reporter import print_eval_report
from app.tests.evals.mock_step import MOCK_STEP


async def main():
    results = await run_regression_suite(step=MOCK_STEP)
    print_eval_report(results)

if __name__ == "__main__":
    asyncio.run(main())