from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.models.security_quality import (
    AuditRequest,
    RemediationRequest,
    RemediationResponse,
    SecurityQualityAuditReport,
)
from app.models.session import GenerationSessionDB, SessionLocal
from app.services.security_service import (
    apply_surgical_remediation,
    audit_workspace,
    calculate_code_metrics,
    evaluate_quality_gate,
    scan_architecture_compliance,
    scan_dependencies_cve,
    scan_sast_vulnerabilities,
    scan_secrets,
)

router = APIRouter(tags=["Security & Quality Audit"])


@router.post("/security/audit", response_model=SecurityQualityAuditReport)
async def audit_code_payload(payload: AuditRequest):
    """Performs an in-memory Static Security, SCA, and Quality Standards evaluation on provided files."""
    secret_findings = scan_secrets(payload.files)
    sast_findings = scan_sast_vulnerabilities(payload.files)
    cve_findings = scan_dependencies_cve(payload.pomXml)
    vulnerabilities = secret_findings + sast_findings + cve_findings

    violations = scan_architecture_compliance(payload.files)
    metrics = calculate_code_metrics(payload.files)
    verdict = evaluate_quality_gate(vulnerabilities, violations, metrics)

    return SecurityQualityAuditReport(
        sessionId="in-memory-audit",
        serviceName=payload.serviceName or "microservice",
        qualityGate=verdict,
        metrics=metrics,
        vulnerabilities=vulnerabilities,
        violations=violations,
    )


@router.get("/sessions/{session_id}/audit", response_model=SecurityQualityAuditReport)
@router.get("/security/{session_id}/report", response_model=SecurityQualityAuditReport)
@router.get("/security/{session_id}/audit", response_model=SecurityQualityAuditReport)
async def audit_session_workspace(session_id: str):
    """Executes or retrieves the comprehensive security and quality audit for an active workspace session."""
    db = SessionLocal()
    service_name = "microservice"
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if sess and sess.spec_name:
            service_name = sess.spec_name
    finally:
        db.close()

    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    if not ws_path.exists() or not ws_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session workspace directory '{session_id}' not found.",
        )

    report = audit_workspace(str(ws_path), session_id, service_name)
    return report


@router.post("/security/remediate", response_model=RemediationResponse)
async def remediate_finding(payload: RemediationRequest):
    """Applies a 1-click surgical auto-repair patch to remediate a supported security or compliance violation."""
    source_code = payload.sourceCode

    # If sourceCode not provided, attempt to locate file in workspace
    target_path = None
    if not source_code:
        # Check if filePath exists as is or inside workspace
        potential_path = Path(payload.filePath)
        if potential_path.exists() and potential_path.is_file():
            target_path = potential_path
            source_code = potential_path.read_text(encoding="utf-8", errors="ignore")
        else:
            # Look in workspace directories
            ws_root = Path(settings.WORKSPACE_DIR)
            matches = list(ws_root.glob(f"**/{payload.filePath}"))
            if matches:
                target_path = matches[0]
                source_code = target_path.read_text(encoding="utf-8", errors="ignore")

    if not source_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source code not provided and could not be resolved from workspace.",
        )

    original, remediated, diff = apply_surgical_remediation(
        payload.findingId, payload.filePath, source_code
    )

    # Persist back to file if target_path was found
    if target_path and target_path.exists() and original != remediated:
        try:
            target_path.write_text(remediated, encoding="utf-8")
        except Exception:
            pass

    return RemediationResponse(
        findingId=payload.findingId,
        filePath=payload.filePath,
        originalCode=original,
        remediatedCode=remediated,
        diff=diff,
        applied=original != remediated,
    )

