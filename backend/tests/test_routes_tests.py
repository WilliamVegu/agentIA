import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.session import GenerationSessionDB, SessionLocal, SessionPhase, SessionStatus

client = TestClient(app)


def _prepare_workspace(session_id: str, tmp_path, monkeypatch, source_files: dict) -> None:
    """Create the session row and the on-disk sources the repair route now requires.

    ``POST /tests/repair`` no longer patches files it has never seen: it resolves the
    session through ``workspace_guard(require_exists=True)`` and refuses any repair
    source that is not an existing workspace file with matching content. That is the
    precondition these tests have to establish before the repair contract is exercised.
    """
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    workspace = tmp_path / session_id
    workspace.mkdir(parents=True, exist_ok=True)
    for relative, content in source_files.items():
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    db = SessionLocal()
    try:
        db.merge(
            GenerationSessionDB(
                id=session_id,
                spec_id="spec-repair",
                spec_name="order-service",
                status=SessionStatus.RUNNING,
                phase=SessionPhase.SELF_REPAIR,
                current_lifecycle_phase="CODE_TESTS",
                lifecycle_mode="GUIDED_STEP",
                repair_attempts=0,
            )
        )
        db.commit()
    finally:
        db.close()


def _stub_sandbox(monkeypatch, results) -> None:
    """Replace the sandbox verification with scripted outcomes.

    The repair route persists the patch and then establishes the outcome through a real
    build. Scripting it keeps the test hermetic and deterministic; the value of the
    verification rule itself is covered by the verification suite.
    """
    import app.orchestrator.nodes.sandbox_node as sandbox_module

    queue = list(results)

    def fake_sandbox(state):
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(sandbox_module, "sandbox_node", fake_sandbox)


_PASSING_SANDBOX = {
    "status": "COMPLETED",
    "test_metrics": {
        "totalTests": 2,
        "passedTests": 2,
        "failedTests": 0,
        "allPassed": True,
        "fallback_used": False,
    },
}

_FAILING_SANDBOX = {
    "status": "BLOCKED",
    "test_metrics": {
        "totalTests": 2,
        "passedTests": 0,
        "failedTests": 2,
        "allPassed": False,
        "fallback_used": False,
    },
    "error": "tests still failing",
}


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

def test_repair_endpoint_success_and_boundary(tmp_path, monkeypatch):
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
    _prepare_workspace(payload["sessionId"], tmp_path, monkeypatch, payload["sourceFiles"])
    _stub_sandbox(monkeypatch, [_PASSING_SANDBOX])

    # Iteration 1
    resp1 = client.post("/api/v1/tests/repair", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["iterationNumber"] == 1

    # Iteration 6 (Must be rejected per Principle V limit <= 5)
    payload["iterationNumber"] = 6
    resp6 = client.post("/api/v1/tests/repair", json=payload)
    assert resp6.status_code in (400, 422)

def test_get_repairs_and_manual_override(tmp_path, monkeypatch):
    session_id = "blocked-session-999"

    # Simulate 5th iteration failure (Constitutional Exhaustion)
    payload = {
        "sessionId": session_id,
        "iterationNumber": 5,
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
    _prepare_workspace(session_id, tmp_path, monkeypatch, payload["sourceFiles"])
    # The automatic iteration fails verification (the cap is exhausted); the manual
    # edit is then verified and is what unblocks the session.
    _stub_sandbox(monkeypatch, [_FAILING_SANDBOX, _PASSING_SANDBOX])

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
    # The route no longer acknowledges the edit ("REPAIR_APPLIED"); it applies it and
    # reports the verification outcome, which is the stronger claim.
    assert man_resp.json()["status"] == "VERIFIED"
    assert man_resp.json()["diagnosticsResolved"] is True
