import io
import time
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLE_SPEC_MARKDOWN = """
# Feature Specification: Order Service
**Feature Branch**: `001-order-service`

### Key Entities
- **Order**: Represents purchase order. id (Long), customerEmail (String), totalAmount (BigDecimal)

### User Scenarios & Acceptance Criteria
- **US-1**: As a Buyer, I want to create an order, so that I can buy items.
  - **AC-1.1**: Given valid items, when POST /orders is called, then order is created with status 201.
"""

def test_system_healthz():
    """T041: Validates system healthcheck endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"
    assert "Microservice Code Studio" in data["app"]

def _ingest_spec() -> str:
    file_bytes = SAMPLE_SPEC_MARKDOWN.encode("utf-8")
    response = client.post(
        "/api/v1/specifications/upload",
        files={"file": ("spec.md", io.BytesIO(file_bytes), "text/markdown")}
    )
    assert response.status_code == 201
    summary = response.json()
    assert summary["isValid"] is True
    assert summary["serviceName"] == "order-service"
    assert summary["entityCount"] >= 1
    return summary["specId"]

def test_scenario_1_dual_ingestion():
    """Quickstart Scenario 1: Upload spec Markdown file and get validated blueprint."""
    spec_id = _ingest_spec()
    assert spec_id is not None

def test_scenario_2_autonomous_generation_and_export():
    """Quickstart Scenario 2: Ingest, create generation session, inspect artifacts, and export ZIP."""
    # 1. Ingest
    spec_id = _ingest_spec()

    # 2. Trigger generation session
    create_resp = client.post("/api/v1/sessions", json={"specId": spec_id})
    assert create_resp.status_code == 202
    sess_data = create_resp.json()
    session_id = sess_data.get("sessionId") or sess_data.get("session_id")
    assert session_id is not None

    # Wait briefly for background pipeline
    time.sleep(1.5)

    # 3. Query session details
    detail_resp = client.get(f"/api/v1/sessions/{session_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["specName"] == "order-service"

    # 4. List artifacts
    art_resp = client.get(f"/api/v1/sessions/{session_id}/artifacts")
    assert art_resp.status_code == 200
    artifacts = art_resp.json()
    assert len(artifacts) >= 5

    # 5. Export ZIP
    export_resp = client.get(f"/api/v1/sessions/{session_id}/export")
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"] == "application/zip"
    assert len(export_resp.content) > 0

def test_quickstart_feature_005_e2e():
    """Validates Feature 005 quickstart scenarios: test synthesis, diagnostic analysis, 3-step repair, and manual unblock."""
    spec_id = _ingest_spec()

    # 1. Synthesize hybrid test suites
    synth_resp = client.post("/api/v1/tests/synthesize", json={"specId": spec_id})
    assert synth_resp.status_code == 200
    synth_data = synth_resp.json()
    assert len(synth_data["suites"]) == 3
    assert synth_data["totalTestCases"] >= 5

    # 2. Analyze failure logs and static code compliance
    analysis_resp = client.post("/api/v1/tests/analyze", json={
        "rawBuildLogs": "[ERROR] OrderServiceImpl.java:[42,18] cannot find symbol: class BigDecimal",
        "sourceFiles": {
            "src/main/java/com/corp/order/service/OrderServiceImpl.java": "package com.corp.order.service;\npublic class OrderServiceImpl {}"
        }
    })
    assert analysis_resp.status_code == 200
    analysis_data = analysis_resp.json()
    assert analysis_data["hasErrors"] is True
    assert len(analysis_data["diagnostics"]) >= 1

    # 3. Execute self-repair iteration loop
    sess_id = f"test-sess-{int(time.time())}"
    repair_resp = client.post("/api/v1/tests/repair", json={
        "sessionId": sess_id,
        "iterationNumber": 1,
        "diagnostics": analysis_data["diagnostics"],
        "sourceFiles": {
            "src/main/java/com/corp/order/service/OrderServiceImpl.java": "package com.corp.order.service;\npublic class OrderServiceImpl {}"
        }
    })
    assert repair_resp.status_code == 200
    repair_record = repair_resp.json()
    assert repair_record["iterationNumber"] == 1
    assert len(repair_record["patchesApplied"]) >= 1
    assert "import java.math.BigDecimal;" in repair_record["diffSummary"]

    # 4. Trigger iteration 5 and verify BLOCKED state (Principle V: max 5 attempts)
    client.post("/api/v1/tests/repair", json={
        "sessionId": sess_id,
        "iterationNumber": 5,
        "diagnostics": analysis_data["diagnostics"],
        "sourceFiles": {
            "src/main/java/com/corp/order/service/OrderServiceImpl.java": "package com.corp.order.service;\npublic class OrderServiceImpl {}"
        }
    })
    history_resp = client.get(f"/api/v1/sessions/{sess_id}/repairs")
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert history_data["finalState"] == "BLOCKED"
    assert history_data["canRetryManually"] is True

    # 5. Perform manual repair unblock
    manual_resp = client.post(f"/api/v1/sessions/{sess_id}/manual-repair", json={
        "filePath": "src/main/java/com/corp/order/service/OrderServiceImpl.java",
        "modifiedCode": "package com.corp.order.service;\nimport java.math.BigDecimal;\npublic class OrderServiceImpl {}",
        "guidanceHint": "Manual import added"
    })
    assert manual_resp.status_code == 200
    assert manual_resp.json()["status"] == "REPAIR_APPLIED"


def test_full_unified_orchestration_e2e():
    """T045: Validates end-to-end unified orchestration across all 8 features."""
    # 1. Quick-Start Session
    qs_resp = client.post("/api/v1/sessions/quick-start", json={
        "specName": "payment-service",
        "prompt": "Payment processing microservice with transactions, credit cards, and refunds",
        "databaseEngine": "POSTGRESQL",
        "autoRun": False,
    })
    assert qs_resp.status_code == 201
    qs_data = qs_resp.json()
    session_id = qs_data["sessionId"]
    assert session_id is not None
    assert qs_data["specName"] == "payment-service"

    # 2. Verify Session Listing
    list_resp = client.get("/api/v1/sessions")
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    assert any(s["sessionId"] == session_id for s in sessions)

    # 3. Query Overview & Lifecycle
    ov_resp = client.get(f"/api/v1/orchestrator/sessions/{session_id}/overview")
    assert ov_resp.status_code == 200
    ov_data = ov_resp.json()
    assert ov_data["specName"] == "payment-service"
    assert "lifecycle" in ov_data

    # 4. Run Pipeline Auto-Pilot
    run_resp = client.post("/api/v1/orchestrator/pipeline/run", json={"sessionId": session_id})
    assert run_resp.status_code == 202

    # 5. In-Flight Pause & Resume
    pause_resp = client.post("/api/v1/orchestrator/pipeline/pause", json={"sessionId": session_id})
    assert pause_resp.status_code == 200
    resume_resp = client.post("/api/v1/orchestrator/pipeline/resume", json={"sessionId": session_id})
    assert resume_resp.status_code == 200

    # Wait for pipeline completion
    for _ in range(30):
        time.sleep(0.3)
        st_resp = client.get(f"/api/v1/orchestrator/pipeline/status/{session_id}")
        if st_resp.status_code == 200:
            status_info = st_resp.json()
            if status_info.get("status") in ("COMPLETED", "FAILED"):
                break

    # 6. Verify Artifacts & Security Audit Report
    sec_resp = client.get(f"/api/v1/security/{session_id}/report")
    assert sec_resp.status_code == 200
    sec_data = sec_resp.json()
    assert "qualityGate" in sec_data
    assert "vulnerabilities" in sec_data
    assert "metrics" in sec_data

    # 7. 1-Click Surgical Remediation
    remed_resp = client.post("/api/v1/security/remediate", json={
        "findingId": "SEC-FIX-001",
        "filePath": "src/main/resources/application.properties",
        "sourceCode": "jwt.secret=supersecretkey1234567890\n",
    })
    assert remed_resp.status_code == 200
    assert "diff" in remed_resp.json()

    # 8. Verify DevOps & Despliegue Status
    devops_resp = client.get(f"/api/v1/devops/{session_id}/status")
    assert devops_resp.status_code == 200

    # 9. Verify Complete Bundle ZIP Export
    bundle_resp = client.get(f"/api/v1/orchestrator/sessions/{session_id}/export-bundle")
    assert bundle_resp.status_code == 200
    assert bundle_resp.headers["content-type"] == "application/zip"
    assert len(bundle_resp.content) > 0

    # 10. Downstream Force Re-sync
    resync_resp = client.post("/api/v1/orchestrator/pipeline/run", json={"sessionId": session_id, "force": True})
    assert resync_resp.status_code == 202

