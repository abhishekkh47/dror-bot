from app.core.knowledge.virtual_step import build_virtual_step
from app.core.types import Step

def test_virtual_step_has_correct_domain():
    step = build_virtual_step("webhooks")
    assert step.domain == ["webhooks"]
    assert step.type == "INFO"
    assert "webhooks" in step.id

def test_virtual_step_for_all_domains():
    domains = ["authentication", "platform_setup", "transactions", "webhooks",
               "sockets", "refunds", "disputes", "troubleshooting"]
    for domain in domains:
        step = build_virtual_step(domain)
        assert step.domain == [domain]

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