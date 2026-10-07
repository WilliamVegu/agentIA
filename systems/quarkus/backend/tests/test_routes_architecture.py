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

def test_design_architecture_success():
    draft = create_sample_draft_payload()
    payload = {
        "draft": draft,
        "apiKey": "mock-key",
    }
    response = client.post("/api/v1/architecture/design", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["serviceName"] == "order-service"
    assert data["packageName"] == "com.corp.order"

    # Verify 4-layer topology + infrastructure
    layers = {c["layer"] for c in data["components"]}
    assert "controller" in layers
    assert "service" in layers
    assert "repository" in layers
    assert "model" in layers
    assert "infrastructure" in layers

    # Verify cross-cutting GlobalExceptionHandler
    assert any(c["name"] == "GlobalExceptionHandler" for c in data["components"])

    # Verify derived endpoints with status codes
    assert len(data["endpoints"]) >= 1
    post_ep = next(e for e in data["endpoints"] if e["method"] == "POST")
    assert post_ep["successStatus"] == 201
    assert post_ep["requestDto"] == "CreateOrderRequest"
    assert post_ep["responseDto"] == "OrderResponse"

    # Verify Mermaid and OpenAPI YAML are generated
    assert "flowchart TD" in data["mermaidDiagram"]
    assert "openapi: 3.0.3" in data["openapiYaml"]
    assert "# Architectural Blueprint" in data["architectureMarkdown"]

def test_design_architecture_missing_api_key_returns_401(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    payload = {
        "draft": create_sample_draft_payload(),
    }
    response = client.post("/api/v1/architecture/design", json=payload)
    assert response.status_code == 401
    assert "LLM API key is required" in response.text

def test_refine_architecture_success():
    # First generate design
    draft = create_sample_draft_payload()
    design_resp = client.post("/api/v1/architecture/design", json={"draft": draft, "apiKey": "mock-key"})
    assert design_resp.status_code == 200
    current_design = design_resp.json()

    refine_payload = {
        "currentDesign": current_design,
        "feedbackPrompt": "Añadir un componente de servicio para notificaciones y auditoría",
        "apiKey": "mock-key",
    }
    refine_resp = client.post("/api/v1/architecture/refine", json=refine_payload)
    assert refine_resp.status_code == 200
    refined_data = refine_resp.json()

    # Check updated component in service layer
    comp_names = [c["name"] for c in refined_data["components"]]
    assert any("Audit" in name or "Notification" in name for name in comp_names)
    assert "flowchart TD" in refined_data["mermaidDiagram"]

def test_handoff_architecture_design_to_generator_pipeline():
    """Validates US4: Architecture design converts directly into an ArchitectureBlueprint in Feature 001."""
    draft = create_sample_draft_payload()
    design_resp = client.post("/api/v1/architecture/design", json={"draft": draft, "apiKey": "mock-key"})
    assert design_resp.status_code == 200
    design_data = design_resp.json()

    # Submit to /api/v1/specifications
    spec_payload = {
        "serviceName": design_data["serviceName"],
        "packageName": design_data["packageName"],
        "basePort": design_data["basePort"],
        "entities": design_data["entities"],
        "userStories": design_data["userStories"],
    }
    spec_resp = client.post("/api/v1/specifications", json=spec_payload)
    assert spec_resp.status_code == 201
    summary = spec_resp.json()
    assert summary["serviceName"] == "order-service"
    assert summary["isValid"] is True
    assert "specId" in summary

