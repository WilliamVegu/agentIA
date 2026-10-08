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

    from app.services.workspace_guard import get_validated_workspace_path
    ws_path = get_validated_workspace_path(session_id, require_exists=True)
    if not ws_path.exists() or not ws_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session workspace directory '{session_id}' not found.",
        )

    report = audit_workspace(str(ws_path), session_id, service_name)
    return report


@router.post("/security/remediate", response_model=RemediationResponse)
async def remediate_finding(payload: RemediationRequest):
    """Preview in memory; persistence is scoped to one existing session."""
    from app.services.workspace_guard import resolve_workspace_file, atomic_write_workspace_file, validate_relative_file, io_path
    source_code = payload.sourceCode
    persist = payload.persist if payload.persist is not None else source_code is None
    target_path = None
    if persist or source_code is None:
        if not payload.sessionId:
            raise HTTPException(422, "sessionId is required to read or persist workspace code; preview requires sourceCode")
        target_path = resolve_workspace_file(payload.sessionId, payload.filePath, require_exists=True)
        current = io_path(target_path).read_text(encoding="utf-8")
        import hashlib
        if payload.expectedFingerprint and hashlib.sha256(current.encode()).hexdigest() != payload.expectedFingerprint:
            raise HTTPException(409, "Source changed; reload before remediating")
        if source_code is not None and source_code != current:
            raise HTTPException(409, "Provided source is outdated; reload before remediating")
        source_code = current
    else:
        validate_relative_file(payload.filePath)
    if not source_code:
        raise HTTPException(422, "Provide nonempty sourceCode for preview")
    original, remediated, diff = apply_surgical_remediation(payload.findingId, payload.filePath, source_code)
    if persist and original != remediated:
        from app.services.session_operation_lock import SessionOperationLock
        lock = SessionOperationLock(payload.sessionId)
        if not lock.acquire(False):
            raise HTTPException(409, "Session has an active operation")
        try:
            if io_path(target_path).read_text(encoding="utf-8") != original:
                raise HTTPException(409, "Source changed during remediation")
            from app.services.verification_evidence import invalidate_evidence
            invalidate_evidence(payload.sessionId)
            atomic_write_workspace_file(payload.sessionId, payload.filePath, remediated)
        finally:
            lock.release()
    return RemediationResponse(findingId=payload.findingId, filePath=payload.filePath,
                               originalCode=original, remediatedCode=remediated, diff=diff, applied=original != remediated)
