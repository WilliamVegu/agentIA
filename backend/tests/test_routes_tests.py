import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def sample_blueprint():
    return {
        "specId": "spec-order-123",
        "serviceName": "order-service",
        "packageName": "com.corp.order",
        "entities": [
            {
                "name": "Order",
                "tableName": "orders",
                "attributes": [
                    {"name": "id", "javaType": "Long", "isPrimaryKey": True},
                    {"name": "orderNumber", "javaType": "String", "isPrimaryKey": False}
                ]
            }
        ],
        "userStories": [
            {
                "id": "US-1",
                "role": "Customer",
                "intent": "create order",
                "benefit": "buy items",
                "scenarios": [
                    {
                        "scenarioId": "AC-1.1",
                        "given": "valid order",
                        "when": "placing order",
                        "then": "return 201 Created"
                    }
                ]
            }
        ]
    }

def test_synthesize_endpoint_400_when_no_blueprint():
    resp = client.post("/api/v1/tests/synthesize", json={"specId": "non-existent-id"})
    assert resp.status_code == 400
    assert "Specification blueprint is required" in resp.json()["detail"]

def test_synthesize_endpoint_success(sample_blueprint):
    resp = client.post("/api/v1/tests/synthesize", json={"blueprint": sample_blueprint})
    assert resp.status_code == 200
    data = resp.json()
    assert data["serviceName"] == "order-service"
    assert len(data["suites"]) == 3
    assert data["totalTestCases"] >= 5

def test_analyze_endpoint_success():
    payload = {
        "rawBuildLogs": "[ERROR] OrderServiceImpl.java:[15,10] cannot find symbol: class BigDecimal",
        "sourceFiles": {
            "src/main/java/com/corp/order/controller/OrderController.java": "import com.corp.order.repository.OrderRepository;"
        }
    }
    resp = client.post("/api/v1/tests/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["hasErrors"] is True
    assert data["constitutionalCompliant"] is False
    assert len(data["diagnostics"]) >= 2

def test_repair_endpoint_success_and_boundary():
    payload = {
        "sessionId": "test-session-123",
        "iterationNumber": 1,
        "diagnostics": [
            {
                "id": "DIAG-1",
                "category": "COMPILATION_ERROR",
                "severity": "BLOCKING",
                "filePath": "src/main/java/com/corp/order/service/OrderServiceImpl.java",
                "errorSummary": "cannot find symbol: class BigDecimal"
            }
        ],
        "sourceFiles": {
            "src/main/java/com/corp/order/service/OrderServiceImpl.java": "package com.corp.order.service;\npublic class OrderServiceImpl {}"
        }
    }

    # Iteration 1
    resp1 = client.post("/api/v1/tests/repair", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["iterationNumber"] == 1

    # Iteration 4 (Must be rejected per Principle V limit <= 3)
    payload["iterationNumber"] = 4
    resp4 = client.post("/api/v1/tests/repair", json=payload)
    assert resp4.status_code in (400, 422)

def test_get_repairs_and_manual_override():
    session_id = "blocked-session-999"

    # Simulate 3rd iteration failure
    payload = {
        "sessionId": session_id,
        "iterationNumber": 3,
        "diagnostics": [
            {
                "id": "DIAG-BLOCK",
                "category": "ASSERTION_FAILURE",
                "severity": "BLOCKING",
                "filePath": "src/main/java/com/corp/order/service/OrderServiceImpl.java",
                "errorSummary": "expected <100> but was <90>"
            }
        ],
        "sourceFiles": {
            "src/main/java/com/corp/order/service/OrderServiceImpl.java": "public class OrderServiceImpl {}"
        }
    }
    client.post("/api/v1/tests/repair", json=payload)

    # Check GET repairs
    rep_resp = client.get(f"/api/v1/sessions/{session_id}/repairs")
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    assert rep_data["finalState"] == "BLOCKED"
    assert rep_data["canRetryManually"] is True

    # Submit manual repair
    man_resp = client.post(
        f"/api/v1/sessions/{session_id}/manual-repair",
        json={
            "filePath": "src/main/java/com/corp/order/service/OrderServiceImpl.java",
            "modifiedCode": "public class OrderServiceImpl { // fixed }",
            "guidanceHint": "Corrected discount calculation logic"
        }
    )
    assert man_resp.status_code == 200
    assert man_resp.json()["status"] == "REPAIR_APPLIED"
