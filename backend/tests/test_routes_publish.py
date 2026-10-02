import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.models.session import GenerationSessionDB, SessionStatus, SessionPhase, SessionLocal

client = TestClient(app)

CLEAN_JAVA_FILES = {
    "src/main/java/com/corp/order/dto/OrderRequest.java": (
        "package com.corp.order.dto;\n"
        "import jakarta.validation.constraints.NotNull;\n"
        "import java.math.BigDecimal;\n\n"
        "public record OrderRequest(@NotNull BigDecimal amount) {}\n"
    ),
    "src/main/java/com/corp/order/advice/GlobalExceptionHandler.java": (
        "package com.corp.order.advice;\n"
        "import org.springframework.web.bind.annotation.RestControllerAdvice;\n\n"
        "@RestControllerAdvice\n"
        "public class GlobalExceptionHandler {}\n"
    ),
}


def _write_clean_workspace(ws_path: Path) -> None:
    """A workspace the Quality Gate actually passes, not merely an empty one.

    An empty workspace is now BLOCKED ("No source code was audited"), so an export
    test has to ship auditable, compliant sources for the gate to be about anything.
    """
    (ws_path / "pom.xml").write_text(
        "<project><dependencies></dependencies></project>", encoding="utf-8"
    )
    for relative, content in CLEAN_JAVA_FILES.items():
        target = ws_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _mark_verified(session_id: str, ws_path: Path) -> None:
    """Record the verification evidence the export guard now requires.

    ``require_verified_session`` only accepts a session whose persisted metrics carry
    a workspace fingerprint that still matches the files on disk. The pipeline that
    produces that evidence has its own tests; here it is the precondition for
    exercising the export contract.
    """
    from app.services.verification_policy import workspace_fingerprint

    metrics = {
        "totalTests": 4,
        "passedTests": 4,
        "failedTests": 0,
        "allPassed": True,
        "fallback_used": False,
        "workspaceFingerprint": workspace_fingerprint(ws_path),
    }
    db = SessionLocal()
    try:
        row = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        row.verification_metrics_json = json.dumps(metrics)
        row.status = SessionStatus.COMPLETED
        row.phase = SessionPhase.VERIFIED
        row.error_message = None
        db.commit()
    finally:
        db.close()


@pytest.fixture
def mock_export_session():
    session_id = "test-export-session-001"
    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    _write_clean_workspace(ws_path)

    db = SessionLocal()
    try:
        sess = GenerationSessionDB(
            id=session_id,
            spec_id="dummy-spec",
            spec_name="order-service",
            status=SessionStatus.COMPLETED,
            phase=SessionPhase.VERIFIED,
            repair_attempts=0
        )
        db.merge(sess)
        db.commit()
    finally:
        db.close()

    _mark_verified(session_id, ws_path)

    yield session_id

def test_export_zip(mock_export_session):
    sess_id = mock_export_session
    response = client.get(f"/api/v1/sessions/{sess_id}/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "order-service.zip" in response.headers["content-disposition"]
    assert len(response.content) > 0

def test_export_zip_not_found():
    response = client.get("/api/v1/sessions/non-existent-session/export")
    assert response.status_code == 404
