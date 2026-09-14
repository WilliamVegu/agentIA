import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.security_quality import QualityGateStatus
from app.models.session import GenerationSessionDB, SessionLocal, SessionPhase, SessionStatus

client = TestClient(app)


def test_audit_in_memory_clean():
    payload = {
        "serviceName": "payment-service",
        "files": {
            "src/main/java/com/corp/payment/dto/PaymentRequest.java": """
package com.corp.payment.dto;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;

public record PaymentRequest(@NotNull BigDecimal amount) {}
""",
            "src/main/java/com/corp/payment/advice/GlobalExceptionHandler.java": """
package com.corp.payment.advice;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {}
"""
        },
        "pomXml": "<project><dependencies></dependencies></project>"
    }

    response = client.post("/api/v1/security/audit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["serviceName"] == "payment-service"
    assert data["qualityGate"]["status"] == "PASS"
    assert data["qualityGate"]["canExport"] is True
    assert len(data["vulnerabilities"]) == 0
    assert len(data["violations"]) == 0


def test_audit_in_memory_blocked_by_secret_and_injection():
    payload = {
        "serviceName": "vulnerable-service",
        "files": {
            "src/main/resources/application.yml": "openai: sk-proj-12345678901234567890abcdef",
            "src/main/java/com/corp/repository/OrderRepository.java": """
package com.corp.repository;
import org.springframework.data.jpa.repository.Query;

public interface OrderRepository {
    @Query("SELECT o FROM Order o WHERE o.name = '" + name + "'")
    List<Order> findByName(String name);
}
"""
        },
        "pomXml": "<project></project>"
    }

    response = client.post("/api/v1/security/audit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["qualityGate"]["status"] == "BLOCKED"
    assert data["qualityGate"]["canExport"] is False
    assert data["qualityGate"]["criticalCount"] >= 1
    assert data["qualityGate"]["highCount"] >= 1
    assert len(data["vulnerabilities"]) >= 2


def test_remediate_endpoint():
    payload = {
        "findingId": "CONST-VIOL-001",
        "filePath": "src/main/java/com/corp/dto/ItemRequest.java",
        "sourceCode": """package com.corp.dto;

public class ItemRequest {
    private String name;
    private int quantity;
}
"""
    }

    response = client.post("/api/v1/security/remediate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["applied"] is True
    assert "public record ItemRequest(String name, int quantity)" in data["remediatedCode"]
    assert "--- a/src/main/java/com/corp/dto/ItemRequest.java" in data["diff"]


def test_session_audit_and_export_blocking():
    session_id = "test-security-blocked-session"
    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    # Insecure file with hardcoded secret
    (ws_path / "application.properties").write_text(
        "api.secret=sk-proj-99998888777766665555444433332222", encoding="utf-8"
    )
    (ws_path / "pom.xml").write_text("<project></project>", encoding="utf-8")

    db = SessionLocal()
    try:
        sess = GenerationSessionDB(
            id=session_id,
            spec_id="dummy-spec",
            spec_name="blocked-service",
            status=SessionStatus.COMPLETED,
            phase=SessionPhase.VERIFIED,
            repair_attempts=0,
        )
        db.merge(sess)
        db.commit()
    finally:
        db.close()

    # Verify session audit endpoint
    audit_res = client.get(f"/api/v1/sessions/{session_id}/audit")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["qualityGate"]["status"] == "BLOCKED"
    assert audit_data["qualityGate"]["canExport"] is False

    # Verify export is blocked with HTTP 403
    export_res = client.get(f"/api/v1/sessions/{session_id}/export")
    assert export_res.status_code == 403
    assert "Quality Gate is BLOCKED" in export_res.json()["detail"]

    # Verify git publish is also blocked with HTTP 403
    publish_res = client.post(
        f"/api/v1/sessions/{session_id}/publish",
        json={"repositoryUrl": "https://github.com/corp/repo.git", "branchName": "feature/test"},
    )
    assert publish_res.status_code == 403
    assert "Quality Gate is BLOCKED" in publish_res.json()["detail"]

