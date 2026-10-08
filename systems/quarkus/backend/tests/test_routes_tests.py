import pytest
from test_draft_authority import session
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

def test_repair_endpoint_success_and_boundary(session):
    payload = {
        "sessionId": "draft-authority",
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

    from app.services.workspace_guard import atomic_write_workspace_file
    for path,source in payload['sourceFiles'].items(): atomic_write_workspace_file('draft-authority',path,source)
    # Iteration 1 applies a patch; SOURCE_ONLY cannot verify it.
    resp1 = client.post("/api/v1/tests/repair", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["iterationNumber"] == 1
    assert resp1.json()["outcome"] != "SUCCESS"

    # Iteration 4 exceeds the constitutional cap of three
    payload["iterationNumber"] = 4
    resp6 = client.post("/api/v1/tests/repair", json=payload)
    assert resp6.status_code in (400, 422)

def test_get_repairs_and_manual_override(session):
    from app.services.workspace_guard import atomic_write_workspace_file
    session_id='draft-authority'
    relative='src/main/java/com/corp/order/service/OrderServiceImpl.java'
    atomic_write_workspace_file(session_id,relative,'public class OrderServiceImpl {}')
    # A source-only session has no invented automatic failures or history.
    response=client.get(f'/api/v1/sessions/{session_id}/repairs')
    assert response.status_code==200
    assert response.json()['totalIterations']==0
    assert response.json()['finalState']=='UNVERIFIED'
    manual=client.post(f'/api/v1/sessions/{session_id}/manual-repair',json={'filePath':relative,'modifiedCode':'public class OrderServiceImpl { // fixed\n}','guidanceHint':'Corrected calculation logic'})
    assert manual.status_code==200,manual.text
    assert manual.json()['status']=='APPLIED_UNVERIFIED'
    assert manual.json()['diagnosticsResolved'] is False
    assert (session/relative).read_text()=='public class OrderServiceImpl { // fixed\n}'
    history=client.get(f'/api/v1/sessions/{session_id}/repairs').json()
    assert history['finalState']=='BLOCKED'
    assert history['canRetryManually'] is True
    assert history['totalIterations']==0
