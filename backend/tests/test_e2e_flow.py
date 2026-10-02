import io
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.session import (
    GenerationSessionDB,
    SessionLocal,
    SessionPhase,
    SessionStatus,
)

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

def test_scenario_2_autonomous_generation_and_export(hermetic_container_build):
    """Quickstart Scenario 2: Ingest, create generation session, inspect artifacts, and export ZIP."""
    # 1. Ingest
    spec_id = _ingest_spec()

    # Entered as a context manager so the app's event loop outlives the POST. The
    # session's pipeline is an asyncio background task on that loop; a bare
    # TestClient tears the loop down when the response returns, which leaves the
    # session RUNNING forever and therefore unable to satisfy the verification
    # evidence export now requires.
    with TestClient(app) as live_client:
        # 2. Trigger generation session
        create_resp = live_client.post("/api/v1/sessions", json={"specId": spec_id})
        assert create_resp.status_code == 202
        sess_data = create_resp.json()
        session_id = sess_data.get("sessionId") or sess_data.get("session_id")
        assert session_id is not None

        # Wait for the background pipeline to reach a terminal state.
        for _ in range(60):
            time.sleep(0.5)
            status_resp = live_client.get(f"/api/v1/sessions/{session_id}")
            if status_resp.json().get("status") in ("COMPLETED", "BLOCKED", "FAILED", "CANCELLED"):
                break

        # 3. Query session details
        detail_resp = live_client.get(f"/api/v1/sessions/{session_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["specName"] == "order-service"

        # 4. List artifacts
        art_resp = live_client.get(f"/api/v1/sessions/{session_id}/artifacts")
        assert art_resp.status_code == 200
        artifacts = art_resp.json()
        assert len(artifacts) >= 5

        # 5. Export ZIP (the pipeline verified the workspace, so the gate is satisfied)
        export_resp = live_client.get(f"/api/v1/sessions/{session_id}/export")
        assert export_resp.status_code == 200
        assert export_resp.headers["content-type"] == "application/zip"
        assert len(export_resp.content) > 0

def _prepare_repair_session(sess_id: str, tmp_path, monkeypatch, source_files: dict) -> Path:
    """Create the session row and on-disk sources ``/tests/repair`` now requires.

    The repair route resolves the session through ``workspace_guard(require_exists=True)``
    and rejects any repair source that is not an existing workspace file whose content
    matches the request, so the session has to be real before the loop is exercised.
    """
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    workspace = tmp_path / sess_id
    workspace.mkdir(parents=True, exist_ok=True)
    for relative, content in source_files.items():
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    db = SessionLocal()
    try:
        db.merge(
            GenerationSessionDB(
                id=sess_id,
                spec_id="spec-feature-005",
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
    return workspace


def _stub_sandbox(monkeypatch, results) -> None:
    """Script the sandbox outcome for the repair route (no container build here)."""
    import app.orchestrator.nodes.sandbox_node as sandbox_module

    queue = list(results)

    def fake_sandbox(state):
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(sandbox_module, "sandbox_node", fake_sandbox)


def _sandbox_result(passed: bool) -> dict:
    if passed:
        return {
            "status": "COMPLETED",
            "test_metrics": {
                "totalTests": 2,
                "passedTests": 2,
                "failedTests": 0,
                "allPassed": True,
                "fallback_used": False,
            },
        }
    return {
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


def test_quickstart_feature_005_e2e(tmp_path, monkeypatch):
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
    broken_source = "package com.corp.order.service;\npublic class OrderServiceImpl {}"
    relative = "src/main/java/com/corp/order/service/OrderServiceImpl.java"
    _prepare_repair_session(sess_id, tmp_path, monkeypatch, {relative: broken_source})
    # The automatic iterations fail sandbox verification; the manual edit passes.
    _stub_sandbox(monkeypatch, [
        _sandbox_result(False), _sandbox_result(False), _sandbox_result(True),
    ])

    repair_resp = client.post("/api/v1/tests/repair", json={
        "sessionId": sess_id,
        "iterationNumber": 1,
        "diagnostics": analysis_data["diagnostics"],
        "sourceFiles": {relative: broken_source}
    })
    assert repair_resp.status_code == 200
    repair_record = repair_resp.json()
    assert repair_record["iterationNumber"] == 1
    assert len(repair_record["patchesApplied"]) >= 1
    assert "import java.math.BigDecimal;" in repair_record["diffSummary"]

    # 4. Trigger iteration 5 and verify BLOCKED state (Principle V: max 5 attempts).
    # The route persisted iteration 1's patch, so iteration 5 must send the current
    # workspace content or the route (correctly) rejects it as a stale source.
    patched_source = (tmp_path / sess_id / relative).read_text(encoding="utf-8")
    client.post("/api/v1/tests/repair", json={
        "sessionId": sess_id,
        "iterationNumber": 5,
        "diagnostics": analysis_data["diagnostics"],
        "sourceFiles": {relative: patched_source}
    })
    history_resp = client.get(f"/api/v1/sessions/{sess_id}/repairs")
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert history_data["finalState"] == "BLOCKED"
    assert history_data["canRetryManually"] is True

    # 5. Perform manual repair unblock. The route no longer merely acknowledges the
    # edit ("REPAIR_APPLIED"); it applies it and reports the sandbox outcome, which
    # is the stronger claim.
    manual_resp = client.post(f"/api/v1/sessions/{sess_id}/manual-repair", json={
        "filePath": relative,
        "modifiedCode": "package com.corp.order.service;\nimport java.math.BigDecimal;\npublic class OrderServiceImpl {}",
        "guidanceHint": "Manual import added"
    })
    assert manual_resp.status_code == 200
    assert manual_resp.json()["status"] == "VERIFIED"
    assert manual_resp.json()["diagnosticsResolved"] is True


@pytest.fixture
def hermetic_container_build(monkeypatch):
    """Keep this suite off the container runtime.

    The pipeline now verifies the workspace, which is correct in production. In a
    flow test it makes the run depend on the host (a Docker build, seconds long) and
    on a generated Java project compiling, neither of which is what this test is
    about -- it asserts the API and lifecycle orchestration. The verification seam is
    stubbed to a PASS so the rest of the flow is exercised unchanged, and the
    verification-specific behaviour is covered by test_pipeline_runner.py.

    Both entry points are patched: the sequential runner
    (``pipeline_runner.run_workspace_verification``) and the graph node
    (``sandbox_node.run_workspace_verification``). They each bind the function at
    import time, so patching one leaves the other doing a real build.
    """
    from app.sandbox.docker_runner import DockerExecutionResult
    from app.services.workspace_verification import WorkspaceVerification
    import app.services.pipeline_runner as pr
    import app.orchestrator.nodes.sandbox_node as sandbox_module

    fake = WorkspaceVerification(
        result=DockerExecutionResult(
            exit_code=0,
            stdout="[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0\n",
        ),
        platform_test_path="src/test/java/x/PlatformPersistenceContractTest.java",
    )
    stub = lambda path, log_callback=None: fake
    monkeypatch.setattr(pr, "run_workspace_verification", stub)
    monkeypatch.setattr(sandbox_module, "run_workspace_verification", stub)


def test_full_unified_orchestration_e2e(hermetic_container_build):
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

