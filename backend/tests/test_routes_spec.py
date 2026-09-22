from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_upload_spec_markdown():
    spec_content = """
    # Feature Specification: Payment Service
    **Feature Branch**: `002-payment-service`
    ### Key Entities
    - **Payment**: id (UUID, PK), amount (BigDecimal, @Positive)
    ### User Story 1 - Process Payment (Priority: P1)
    As a user I want to pay so that my account is credited.
    1. **Given** valid funds, **When** payment is submitted, **Then** 201 is returned.
    """
    files = {"file": ("spec.md", spec_content.encode("utf-8"), "text/markdown")}
    response = client.post("/api/v1/specifications/upload", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["serviceName"] == "payment-service"
    assert data["isValid"] is True

def test_submit_spec_json_success():
    payload = {
        "serviceName": "inventory-service",
        "packageName": "com.corp.inventory",
        "basePort": 8082,
        "entities": [
            {
                "name": "Item",
                "tableName": "items",
                "attributes": [
                    {"name": "id", "type": "UUID", "isPrimaryKey": True},
                    {"name": "sku", "type": "String", "validationRules": ["@NotBlank"]}
                ]
            }
        ],
        "userStories": [
            {
                "id": "US-1",
                "priority": "P1",
                "role": "Warehouse Manager",
                "intent": "track inventory",
                "benefit": "know stock levels",
                "scenarios": [
                    {
                        "scenarioId": "AC-1.1",
                        "given": "sku exists",
                        "when": "query item",
                        "then": "return current quantity"
                    }
                ]
            }
        ]
    }
    response = client.post("/api/v1/specifications", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["serviceName"] == "inventory-service"
    assert data["entityCount"] == 1

def test_submit_spec_json_invalid_payload():
    invalid_payload = {"serviceName": "Bad Service Name With Spaces"}
    response = client.post("/api/v1/specifications", json=invalid_payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] == 400

def test_submit_spec_json_frontend_transfer_payload():
    payload = {
        "serviceName": "customer-billing-service",
        "packageName": "com.tcs.billing",
        "basePort": 8080,
        "databaseMode": "PostgreSQL",
        "entities": [
            {
                "name": "Invoice",
                "tableName": "invoices",
                "attributes": [
                    {"name": "id", "type": "Long", "isPrimaryKey": True, "nullable": False, "validationRules": []},
                    {"name": "customerId", "type": "String", "isPrimaryKey": False, "nullable": False, "validationRules": ["@NotBlank"]},
                    {"name": "amount", "type": "BigDecimal", "isPrimaryKey": False, "nullable": False, "validationRules": ["@NotNull"]},
                    {"name": "createdAt", "type": "Instant", "isPrimaryKey": False, "nullable": True, "validationRules": []}
                ]
            }
        ],
        "userStories": [
            {
                "id": "US-1",
                "priority": "P1",
                "role": "BillingManager",
                "intent": "Emit invoice for completed order",
                "benefit": "Collect payment from customer",
                "scenarios": [
                    {
                        "scenarioId": "AC-1.1",
                        "given": "Valid order with customer ID and amount",
                        "when": "POST request sent to /api/v1/invoices",
                        "then": "Invoice is persisted and HTTP 201 Created is returned"
                    }
                ]
            }
        ]
    }
    response = client.post("/api/v1/specifications", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["serviceName"] == "customer-billing-service"
    assert data["isValid"] is True
    assert "specId" in data


