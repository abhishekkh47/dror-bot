import requests

BASE_URL = "http://localhost:8000"

def start_fresh_flow():
    res = requests.post(f"{BASE_URL}/flow/start", params={"flow_id": "payment_execution"})
    data = res.json()
    return data["session"]["session_id"]

def advance(session_id, user_input="advance"):
    """Advance flow by one step."""
    res = requests.post(f"{BASE_URL}/flow/input", params={
        "session_id": session_id,
        "user_input": user_input
    })
    return res.json()


# Note: /flow/input advances to the NEXT step and runs RAG on that next step.
# So to test RAG at step X, you need to be on the step BEFORE X.
#
# Flow path: create_intent -> check_intent_response -> store_transaction_id ->
#            system_auto_processing -> receive_update -> evaluate_status -> ...

print("=" * 60)
print("CASE 1: 'what headers are required?' → lands on check_intent_response")
print("  (start on create_intent, rag_topic: create_intent_response_handling)")
print("  Expected: Should give API-level answer about the intent response")
print("=" * 60)
session_id = start_fresh_flow()
# On create_intent, this advances to check_intent_response
res = advance(session_id, "what headers are required?")
print(f"Step landed: {res.get('step', {}).get('id')}")
print(f"Response: {res.get('response', res)}\n")


print("=" * 60)
print("CASE 2: 'what headers are required?' → lands on evaluate_status")
print("  (start on receive_update, rag_topic: payment_status_evaluation)")
print("  Expected: Should NOT give API header details (wrong context)")
print("=" * 60)
session_id = start_fresh_flow()
# Advance: create_intent -> check_intent_response
advance(session_id, "advance")
# Advance: check_intent_response (DECISION: success) -> store_transaction_id
advance(session_id, "success")
# Advance: store_transaction_id -> system_auto_processing
advance(session_id, "advance")
# Advance: system_auto_processing -> receive_update
advance(session_id, "advance")
# Now on receive_update — this advances to evaluate_status
res = advance(session_id, "what headers are required?")
print(f"Step landed: {res.get('step', {}).get('id')}")
print(f"Response: {res.get('response', res)}\n")


print("=" * 60)
print("CASE 3: 'what happens if payment fails?' → lands on check_intent_response")
print("  (start on create_intent, rag_topic: create_intent_response_handling)")
print("  Expected: Edge case - should answer about failure at intent creation")
print("=" * 60)
session_id = start_fresh_flow()
# On create_intent, this advances to check_intent_response
res = advance(session_id, "what happens if payment fails?")
print(f"Step landed: {res.get('step', {}).get('id')}")
print(f"Response: {res.get('response', res)}\n")
