

# tests/test_scope_guard.py
from app.core.knowledge.scope_guard import enforce_drorpay_scope, OUT_OF_SCOPE_RESPONSE

def test_valid_domain_passes():
    allowed, msg = enforce_drorpay_scope("webhooks")
    assert allowed is True
    assert msg is None

def test_out_of_scope_blocked():
    allowed, msg = enforce_drorpay_scope("out_of_scope")
    assert allowed is False
    assert "DrorPay" in msg

def test_out_of_scope_response_mentions_drorpay():
    assert "DrorPay" in OUT_OF_SCOPE_RESPONSE