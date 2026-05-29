from app.core.knowledge.domain_classifier import classify_query_domain

def test_transaction_query():
    assert classify_query_domain("how do I create a payment intent?") == "transactions"

def test_webhook_query():
    assert classify_query_domain("how do I verify webhook signatures?") == "webhooks"

def test_auth_query():
    assert classify_query_domain("what headers are required for the API?") == "authentication"

def test_refund_query():
    assert classify_query_domain("how do I issue a partial refund?") == "refunds"

def test_socket_query():
    assert classify_query_domain("how do I receive real-time payment updates?") == "sockets"

def test_troubleshooting_query():
    assert classify_query_domain("payment was cancelled immediately") == "troubleshooting"

def test_platform_setup_query():
    assert classify_query_domain("how do I set up a new platform?") == "platform_setup"

def test_out_of_scope_query():
    assert classify_query_domain("what is the capital of France?") == "out_of_scope"