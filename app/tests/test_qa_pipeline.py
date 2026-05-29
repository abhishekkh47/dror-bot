from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_query_endpoint_exists():
    response = client.post("/query", json={"query": "what headers are required?"})
    assert response.status_code == 200

def test_query_returns_answer():
    response = client.post("/query", json={"query": "how do I verify webhook signatures?"})
    data = response.json()
    assert "answer" in data
    assert "domain" in data
    assert data["domain"] == "webhooks"
    assert len(data["answer"]) > 20

def test_out_of_scope_is_refused():
    response = client.post("/query", json={"query": "what is the capital of France?"})
    data = response.json()
    assert data["domain"] == "out_of_scope"
    assert "DrorPay" in data["answer"]

def test_query_requires_query_field():
    response = client.post("/query", json={})
    assert response.status_code == 422

def test_query_authentication_domain():
    response = client.post("/query", json={"query": "what is X-Platform-Secret?"})
    data = response.json()
    assert data["domain"] == "authentication"
    assert data["mode"] in ("answered", "no_context", "blocked")