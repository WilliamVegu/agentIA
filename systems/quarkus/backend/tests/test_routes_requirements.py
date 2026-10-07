import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_transform_requirements_success_with_payload_key():
    payload = {
        "rawText": "Quiero un microservicio para gestionar órdenes de compra con email de cliente y monto total.",
        "serviceName": "order-service",
        "packageName": "com.corp.order",
        "apiKey": "mock-key",
    }
    response = client.post("/api/v1/requirements/transform", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["serviceName"] == "order-service"
    assert data["packageName"] == "com.corp.order"
    assert len(data["entities"]) >= 1
    assert len(data["userStories"]) >= 3
    # Check scenario exhaustiveness (at least 2 scenarios per story)
    for story in data["userStories"]:
        assert len(story["scenarios"]) >= 2
        assert any("valid" in sc["given"].lower() or "active" in sc["given"].lower() for sc in story["scenarios"])
    assert "markdownSpec" in data
    assert "# Feature Specification:" in data["markdownSpec"]

def test_transform_requirements_success_with_header_key():
    payload = {
        "rawText": "Sistema de facturación electrónica que valida números de factura y calcula impuestos.",
        "serviceName": "invoice-service",
    }
    headers = {"X-LLM-API-Key": "mock-key"}
    response = client.post("/api/v1/requirements/transform", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["serviceName"] == "invoice-service"
    assert len(data["userStories"]) >= 3

def test_transform_requirements_missing_api_key_returns_401(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    payload = {
        "rawText": "Requisitos válidos con longitud suficiente sin clave de API suministrada.",
    }
    response = client.post("/api/v1/requirements/transform", json=payload)
    assert response.status_code == 401
    assert "LLM API key is required" in response.text

def test_transform_requirements_too_short_text_returns_400():
    payload = {
        "rawText": "Corto",
        "apiKey": "mock-key",
    }
    response = client.post("/api/v1/requirements/transform", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] == 400

def test_refine_requirements_global_feedback():
    draft_payload = {
        "serviceName": "payment-service",
        "packageName": "com.corp.payment",
        "basePort": 8080,
        "entities": [
            {
                "name": "Payment",
                "tableName": "payments",
                "attributes": [
                    {"name": "id", "type": "UUID", "isPrimaryKey": True},
                    {"name": "amount", "type": "BigDecimal", "validationRules": ["@Positive"]},
                ],
            }
        ],
        "userStories": [
            {
                "id": "US-1",
                "priority": "P1",
                "role": "Customer",
                "intent": "submit payment",
                "benefit": "complete checkout",
                "scenarios": [
                    {
                        "scenarioId": "AC-1.1",
                        "given": "valid card",
                        "when": "payment is sent",
                        "then": "201 Created",
                    },
                    {
                        "scenarioId": "AC-1.2",
                        "given": "insufficient funds",
                        "when": "payment is sent",
                        "then": "400 Bad Request",
                    },
                ],
            }
        ],
        "assumptions": [],
        "markdownSpec": "# Spec",
    }
    refine_payload = {
        "currentDraft": draft_payload,
        "feedbackPrompt": "Añadir validación para tarjetas vencidas",
        "apiKey": "mock-key",
    }
    response = client.post("/api/v1/requirements/refine", json=refine_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["serviceName"] == "payment-service"
    assert len(data["userStories"][0]["scenarios"]) >= 3

def test_refine_requirements_target_story():
    draft_payload = {
        "serviceName": "order-service",
        "packageName": "com.corp.order",
        "basePort": 8080,
        "entities": [
            {
                "name": "Order",
                "tableName": "orders",
                "attributes": [{"name": "id", "type": "UUID", "isPrimaryKey": True}],
            }
        ],
        "userStories": [
            {
                "id": "US-1",
                "priority": "P1",
                "role": "Buyer",
                "intent": "place order",
                "benefit": "buy items",
                "scenarios": [
                    {"scenarioId": "AC-1.1", "given": "valid cart", "when": "checkout", "then": "success"},
                    {"scenarioId": "AC-1.2", "given": "empty cart", "when": "checkout", "then": "error"},
                ],
            },
            {
                "id": "US-2",
                "priority": "P2",
                "role": "Buyer",
                "intent": "cancel order",
                "benefit": "stop delivery",
                "scenarios": [
                    {"scenarioId": "AC-2.1", "given": "pending order", "when": "cancel", "then": "cancelled"},
                    {"scenarioId": "AC-2.2", "given": "shipped order", "when": "cancel", "then": "cannot cancel"},
                ],
            },
        ],
        "assumptions": [],
        "markdownSpec": "# Order Spec",
    }
    refine_payload = {
        "currentDraft": draft_payload,
        "feedbackPrompt": "Añadir escenario de reembolso automático en cancelación",
        "targetStoryId": "US-2",
        "apiKey": "mock-key",
    }
    response = client.post("/api/v1/requirements/refine", json=refine_payload)
    assert response.status_code == 200
    data = response.json()
    us2 = next(s for s in data["userStories"] if s["id"] == "US-2")
    assert len(us2["scenarios"]) >= 3

def test_handoff_transformed_draft_to_specifications_pipeline():
    """
    Validates US4: A SpecificationDraft transformed from requirements can be submitted
    directly to POST /api/v1/specifications to create an active blueprint for Code Studio.
    """
    transform_payload = {
        "rawText": "Servicio de inventario para gestionar almacenes y stock de productos.",
        "serviceName": "warehouse-service",
        "packageName": "com.corp.warehouse",
        "apiKey": "mock-key",
    }
    trans_resp = client.post("/api/v1/requirements/transform", json=transform_payload)
    assert trans_resp.status_code == 200
    draft_data = trans_resp.json()

    # Submit blueprint payload to /api/v1/specifications
    spec_payload = {
        "serviceName": draft_data["serviceName"],
        "packageName": draft_data["packageName"],
        "basePort": draft_data["basePort"],
        "entities": draft_data["entities"],
        "userStories": draft_data["userStories"],
    }
    spec_resp = client.post("/api/v1/specifications", json=spec_payload)
    assert spec_resp.status_code == 201
    summary = spec_resp.json()
    assert summary["serviceName"] == "warehouse-service"
    assert summary["isValid"] is True
    assert "specId" in summary

def test_transform_requirements_with_explicit_provider_gemini():
    payload = {
        "rawText": "Gestión de pedidos con entrega a domicilio y seguimiento GPS.",
        "apiKey": "mock-key",
        "provider": "gemini",
    }
    response = client.post("/api/v1/requirements/transform", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["userStories"]) >= 1

def test_transform_requirements_with_provider_header_groq():
    payload = {
        "rawText": "Gestión de inventario y compras con cálculo de impuestos.",
        "apiKey": "mock-key",
    }
    headers = {
        "X-LLM-Provider": "groq",
        "X-LLM-API-Key": "mock-key",
    }
    response = client.post("/api/v1/requirements/transform", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["userStories"]) >= 1


