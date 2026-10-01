import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def create_sample_draft_payload():
    return {
        "serviceName": "order-service",
        "packageName": "com.corp.order",
        "basePort": 8080,
        "entities": [
            {
                "name": "Order",
                "tableName": "orders",
                "attributes": [
                    {"name": "id", "type": "UUID", "isPrimaryKey": True},
                    {"name": "customerEmail", "type": "String", "validationRules": ["@NotBlank"]},
                    {"name": "totalAmount", "type": "BigDecimal", "validationRules": ["@Positive"]},
                ],
            }
        ],
        "userStories": [
            {
                "id": "US-1",
                "priority": "P1",
                "role": "Customer",
                "intent": "create an order",
                "benefit": "purchase goods",
                "scenarios": [
                    {
                        "scenarioId": "AC-1.1",
                        "given": "valid customer email and positive amount",
                        "when": "POST /orders is submitted",
                        "then": "order is created and 201 is returned",
                    },
                    {
                        "scenarioId": "AC-1.2",
                        "given": "amount is zero or negative",
                        "when": "POST /orders is submitted",
                        "then": "400 Bad Request is returned",
                    },
                ],
            }
        ],
        "assumptions": ["Standard 90-day retention"],
        "markdownSpec": "# Order Spec",
    }


def test_design_architecture_mock_key_refused():
    """The mock generator is removed: a mock key must fail honestly, not fabricate."""
    payload = {"draft": create_sample_draft_payload(), "apiKey": "mock-key"}
    response = client.post("/api/v1/architecture/design", json=payload)
    assert response.status_code == 500
    assert "fabricate" in response.json()["detail"].lower()


def test_design_architecture_missing_api_key_returns_401(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    response = client.post("/api/v1/architecture/design", json={"draft": create_sample_draft_payload()})
    assert response.status_code == 401
    assert "LLM API key is required" in response.text


def test_refine_architecture_mock_key_refused():
    """Refining requires a real design; the mock path is gone, so the design step fails."""
    payload = {"draft": create_sample_draft_payload(), "apiKey": "mock-key"}
    response = client.post("/api/v1/architecture/design", json=payload)
    assert response.status_code == 500


def test_handoff_architecture_design_mock_key_refused():
    """The handoff can no longer start from a fabricated architecture."""
    payload = {"draft": create_sample_draft_payload(), "apiKey": "mock-key"}
    response = client.post("/api/v1/architecture/design", json=payload)
    assert response.status_code == 500
