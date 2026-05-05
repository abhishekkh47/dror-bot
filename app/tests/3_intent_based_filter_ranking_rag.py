import requests

BASE_URL = "http://localhost:8000"

def start_fresh_flow():
    res = requests.post(f"{BASE_URL}/flow/start", params={"flow_id": "payment_execution"})
    data = res.json()
    return data["session"]["session_id"]

def advance(session_id, user_input="advance"):
    res = requests.post(f"{BASE_URL}/flow/input", params={
        "session_id": session_id,
        "user_input": user_input
    })
    return res.json()


# All 3 queries test intent generalization at check_intent_response.
# They are rephrasings of "payment failed" that avoid the keyword "fail/failure".
# If the system only works with exact keywords, these will break.
#
# Flow: create_intent -> check_intent_response
# We start on create_intent, /flow/input advances to check_intent_response.

queries = [
    {
        "query": "why was payment cancelled?",
        "expected": "Should retrieve cancellation/failure chunks without 'failure' keyword",
    },
    {
        "query": "payment didn't complete",
        "expected": "Should retrieve failure/auto-cancel chunks — no explicit failure keyword",
    },
    {
        "query": "transaction failed after processing",
        "expected": "Should retrieve auto-completion failure chunks — 'failed' keyword present",
    },
]

for i, case in enumerate(queries, 1):
    print("=" * 60)
    print(f"CASE {i}: '{case['query']}' → lands on check_intent_response")
    print(f"  Expected: {case['expected']}")
    print("=" * 60)

    session_id = start_fresh_flow()
    res = advance(session_id, case["query"])

    step = res.get("step", {})
    print(f"Step landed: {step.get('id')}")
    print(f"Response: {res.get('response', res)}")
    print()
