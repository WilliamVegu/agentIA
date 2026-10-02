import json
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from app.main import app
from app.config import settings
from app.models.session import GenerationSessionDB, SessionLocal, SessionPhase, SessionStatus
from app.models.orchestrator import LifecyclePhase


@pytest.fixture
def client_with_session(tmp_path, monkeypatch):
    client = TestClient(app)
    session_id = "test-orch-route-sess"
    ws_path = tmp_path / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))

    db = SessionLocal()
    db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
    sess = GenerationSessionDB(
        id=session_id,
        spec_id="spec-test",
        spec_name="PaymentService",
        status=SessionStatus.QUEUED,
        phase=SessionPhase.INITIALIZATION,
        current_lifecycle_phase="INITIAL",
        lifecycle_mode="GUIDED_STEP",
    )
    db.add(sess)
    db.commit()
    db.close()

    yield client, session_id, ws_path

    db = SessionLocal()
    db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
    db.commit()
    db.close()


def test_get_lifecycle_endpoint(client_with_session):
    client, session_id, ws_path = client_with_session
    resp = client.get(f"/api/v1/orchestrator/sessions/{session_id}/lifecycle")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sessionId"] == session_id
    assert "completionPercentage" in data
    assert len(data["phases"]) == 7


def test_transition_phase_endpoint(client_with_session):
    client, session_id, ws_path = client_with_session

    # Creating spec.md to satisfy phase 1
    (ws_path / "spec.md").write_text("# Payment Service Spec", encoding="utf-8")

    # Transitioning to STORIES should succeed
    resp = client.post(
        f"/api/v1/orchestrator/sessions/{session_id}/transition",
        json={"targetPhase": "STORIES", "force": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["currentPhase"] == "STORIES"

    # Transitioning prematurely to DEVOPS_DEPLOY should return 400
    fail_resp = client.post(
        f"/api/v1/orchestrator/sessions/{session_id}/transition",
        json={"targetPhase": "DEVOPS_DEPLOY", "force": False},
    )
    assert fail_resp.status_code == 400


def test_get_overview_endpoint(client_with_session):
    client, session_id, ws_path = client_with_session
    (ws_path / "spec.md").write_text("# Spec", encoding="utf-8")
    (ws_path / "user_stories.json").write_text(json.dumps([{"id": "US1"}]), encoding="utf-8")

    resp = client.get(f"/api/v1/orchestrator/sessions/{session_id}/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sessionId"] == session_id
    assert data["specName"] == "PaymentService"
    assert data["userStoriesCount"] == 1


def test_pipeline_run_and_pause_endpoints(client_with_session):
    client, session_id, ws_path = client_with_session

    # Run pipeline
    resp = client.post(
        "/api/v1/orchestrator/pipeline/run",
        json={"sessionId": session_id, "targetPhase": "DEVOPS_DEPLOY", "stopOnGate": True},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["sessionId"] == session_id
    assert data["status"] == "RUNNING"

    # Pause pipeline
    pause_resp = client.post(f"/api/v1/orchestrator/pipeline/{session_id}/pause")
    assert pause_resp.status_code in (200, 400)  # 200 if still running, 400 if already completed


def test_export_bundle_endpoint(client_with_session):
    client, session_id, ws_path = client_with_session
    (ws_path / "spec.md").write_text("# Spec Content", encoding="utf-8")
    (ws_path / "docker-compose.yml").write_text("version: '3.8'", encoding="utf-8")

    # The bundle is gated on (a) verification evidence and (b) a Quality Gate that
    # passed. The fixture's session is QUEUED and its workspace is empty, so both
    # preconditions are established here: compliant sources for the gate, and the
    # persisted metrics with a matching fingerprint for the verification policy.
    (ws_path / "pom.xml").write_text(
        "<project><dependencies></dependencies></project>", encoding="utf-8"
    )
    clean_sources = {
        "src/main/java/com/corp/payment/dto/PaymentRequest.java": (
            "package com.corp.payment.dto;\n"
            "import jakarta.validation.constraints.NotNull;\n"
            "import java.math.BigDecimal;\n\n"
            "public record PaymentRequest(@NotNull BigDecimal amount) {}\n"
        ),
        "src/main/java/com/corp/payment/advice/GlobalExceptionHandler.java": (
            "package com.corp.payment.advice;\n"
            "import org.springframework.web.bind.annotation.RestControllerAdvice;\n\n"
            "@RestControllerAdvice\n"
            "public class GlobalExceptionHandler {}\n"
        ),
    }
    for relative, content in clean_sources.items():
        target = ws_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    from app.services.verification_policy import workspace_fingerprint

    db = SessionLocal()
    try:
        row = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        row.status = SessionStatus.COMPLETED
        row.phase = SessionPhase.VERIFIED
        row.error_message = None
        row.verification_metrics_json = json.dumps({
            "totalTests": 5,
            "passedTests": 5,
            "failedTests": 0,
            "allPassed": True,
            "fallback_used": False,
            "workspaceFingerprint": workspace_fingerprint(ws_path),
        })
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/api/v1/orchestrator/sessions/{session_id}/export-bundle")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert len(resp.content) > 0


def test_pipeline_run_with_new_session():
    client = TestClient(app)
    resp = client.post(
        "/api/v1/orchestrator/pipeline/run",
        json={"sessionId": "new", "targetPhase": "DEVOPS_DEPLOY", "stopOnGate": True},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["sessionId"] != "new"
    assert len(data["sessionId"]) > 10
    assert data["status"] == "RUNNING"

    # Cleanup created session
    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == data["sessionId"]).delete()
        db.commit()
    finally:
        db.close()


def test_invalidation_and_resync_flow(client_with_session):
    client, session_id, ws_path = client_with_session

    # Invalidate from STORIES downstream
    inv_resp = client.post(
        f"/api/v1/orchestrator/sessions/{session_id}/invalidate",
        json={"modifiedPhase": "STORIES"},
    )
    assert inv_resp.status_code == 200
    inv_data = inv_resp.json()
    assert inv_data["sessionId"] == session_id

    # Invalidation flags only phases that have actually been BUILT -- a phase with no
    # artifacts is not stale, it is simply not built yet. This fixture session has no
    # architecture on disk, so nothing is flagged and no banner should appear.
    #
    # This previously asserted "ARCHITECTURE" in outdatedPhases, which is what produced
    # the reported false positive: a routine requirements approval raised
    # "upstream modifications detected" for work that had never been done.
    assert inv_data["outdatedPhases"] == []
    assert client.get(
        f"/api/v1/orchestrator/sessions/{session_id}/lifecycle"
    ).json()["isOutdated"] is False

    # With a downstream phase actually built, the same call flags it -- the case the
    # banner exists for.
    (ws_path / "architecture.json").write_text("{}", encoding="utf-8")
    inv_after = client.post(
        f"/api/v1/orchestrator/sessions/{session_id}/invalidate",
        json={"modifiedPhase": "STORIES"},
    )
    assert "ARCHITECTURE" in inv_after.json()["outdatedPhases"]

    # Verify lifecycle marks isOutdated
    lc_resp = client.get(f"/api/v1/orchestrator/sessions/{session_id}/lifecycle")
    assert lc_resp.status_code == 200
    assert lc_resp.json()["isOutdated"] is True

    # Re-sync with force=True
    resync_resp = client.post(
        "/api/v1/orchestrator/pipeline/run",
        json={"sessionId": session_id, "force": True},
    )
    assert resync_resp.status_code == 202

    # Verify outdated cleared
    lc_after = client.get(f"/api/v1/orchestrator/sessions/{session_id}/lifecycle")
    assert lc_after.status_code == 200
    assert lc_after.json()["isOutdated"] is False


def test_pipeline_cancel_endpoints(client_with_session):
    client, session_id, ws_path = client_with_session

    # Cancel via path param
    cancel_resp = client.post(f"/api/v1/orchestrator/pipeline/{session_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # Cancel via body
    cancel_body_resp = client.post(
        "/api/v1/orchestrator/pipeline/cancel",
        json={"sessionId": session_id},
    )
    assert cancel_body_resp.status_code == 200
    assert cancel_body_resp.json()["status"] == "CANCELLED"


