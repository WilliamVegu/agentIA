import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_repair_missing_session_returns_404():
    response = client.post('/api/v1/tests/repair', json={
        'sessionId': 'missing-repair-session', 'iterationNumber': 1,
        'diagnostics': [], 'sourceFiles': {},
    })
    assert response.status_code == 404


def test_repair_busy_workspace_returns_409_without_changing_sources():
    from _support import repair_workspace
    from app.services.queue_service import queue_manager
    files = {'src/main/java/App.java': 'class App {}'}
    ws = repair_workspace('busy-repair-session', files)
    assert queue_manager.try_acquire_slot_sync('busy-repair-session')
    try:
        response = client.post('/api/v1/tests/repair', json={
            'sessionId': 'busy-repair-session', 'iterationNumber': 1,
            'diagnostics': [], 'sourceFiles': files,
        })
        assert response.status_code == 409
        assert (ws / 'src/main/java/App.java').read_text(encoding='utf-8') == files['src/main/java/App.java']
    finally:
        queue_manager.release_slot_sync('busy-repair-session')


def test_repair_stale_sources_returns_409_without_overwriting():
    from _support import repair_workspace
    ws = repair_workspace('stale-repair-session', {'src/main/java/App.java': 'class App {}'})
    response = client.post('/api/v1/tests/repair', json={
        'sessionId': 'stale-repair-session', 'iterationNumber': 1,
        'diagnostics': [], 'sourceFiles': {'src/main/java/App.java': 'class OldApp {}'},
    })
    assert response.status_code == 409
    assert (ws / 'src/main/java/App.java').read_text(encoding='utf-8') == 'class App {}'

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
    from _support import repair_workspace
    repair_workspace(payload['sessionId'], payload['sourceFiles'])
    resp1 = client.post("/api/v1/tests/repair", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["iterationNumber"] == 1

    # A fourth automatic repair exceeds the configured three-attempt limit.
    payload["iterationNumber"] = 4
    resp6 = client.post("/api/v1/tests/repair", json=payload)
    assert resp6.status_code in (400, 422)

def test_get_repairs_and_manual_override(monkeypatch):
    session_id = "blocked-session-999"

    # Simulate the third failed iteration (constitutional exhaustion).
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
    from _support import repair_workspace
    repair_workspace(session_id, payload['sourceFiles'], mode='DOCKER')
    monkeypatch.setattr('app.orchestrator.nodes.sandbox_node.sandbox_node', lambda state: {
        'status': 'BLOCKED', 'error': 'test assertion failed', 'test_metrics': {
            'totalTests': 1, 'passedTests': 0, 'failedTests': 1, 'allPassed': False, 'fallback_used': False}})
    assert client.post("/api/v1/tests/repair", json=payload).status_code == 200

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
    assert man_resp.json()["status"] == "BLOCKED"
    assert man_resp.json()["diagnosticsResolved"] is False
