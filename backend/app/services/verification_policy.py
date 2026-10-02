"""Shared acceptance policy: successful generation is not verification."""
import json
import hashlib
from pathlib import Path
from app.config import settings
from fastapi import HTTPException
from app.models.session import SessionPhase, SessionStatus


def tests_really_passed(metrics) -> bool:
    try:
        metrics = json.loads(metrics) if isinstance(metrics, str) else metrics
        if not isinstance(metrics, dict):
            return False
        total, passed = metrics.get("totalTests"), metrics.get("passedTests")
        return (
            type(total) is int and type(passed) is int and total > 0
            and passed == total and metrics.get("failedTests", 0) == 0
            and metrics.get("allPassed") is True
            and metrics.get("fallback_used") is False
        )
    except (ValueError, TypeError):
        return False


def workspace_fingerprint(workspace) -> str:
    root = Path(workspace).resolve()
    digest = hashlib.sha256()
    if not root.is_dir():
        return ""
    files = sorted(p for p in root.rglob("*") if p.is_file()
                   and not any(part in {".git", "target", "build", ".gradle", "node_modules"} for part in p.relative_to(root).parts)
                   and (p.relative_to(root).parts[0] == "src" or p.name in {"pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts", "schema.sql", "data.sql", "spec.md", "specification_draft.json", "user_stories.json", "architecture.json", "domain_model.json"}))
    for file in files:
        if not file.resolve().is_relative_to(root):
            return ""
        digest.update(file.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest() if files else ""


def session_has_current_evidence(session) -> bool:
    if not session or not tests_really_passed(session.verification_metrics_json):
        return False
    try:
        metrics = json.loads(session.verification_metrics_json)
        fingerprint = metrics.get("workspaceFingerprint")
        return bool(fingerprint and fingerprint == workspace_fingerprint(Path(settings.WORKSPACE_DIR) / session.id))
    except (ValueError, TypeError, OSError):
        return False


def session_is_verified(session) -> bool:
    return bool(session and session.status == SessionStatus.COMPLETED
                and session.phase == SessionPhase.VERIFIED and not session.error_message
                and session_has_current_evidence(session))


def session_allows_source_delivery(session) -> bool:
    """Source-only delivery in no-Docker mode; never a verification verdict."""
    if session_is_verified(session):
        return True
    if settings.DOCKER_ENABLED or not session or session.status != SessionStatus.COMPLETED or session.error_message:
        return False
    try:
        metrics = json.loads(session.verification_metrics_json or "{}")
        return bool(metrics.get("verificationSkipped") is True
                    and metrics.get("allPassed") is False
                    and metrics.get("workspaceFingerprint")
                    and metrics["workspaceFingerprint"] == workspace_fingerprint(Path(settings.WORKSPACE_DIR) / session.id))
    except (ValueError, TypeError, OSError):
        return False


def require_source_delivery(session) -> None:
    """Guard only source export/publication, including a fresh SAST audit."""
    if not session_allows_source_delivery(session):
        raise HTTPException(403, "Source delivery requires completed generation and current verification or explicit unexecuted tests in no-Docker mode.")
    from app.services.security_service import audit_workspace
    audit = audit_workspace(str(Path(settings.WORKSPACE_DIR) / session.id), session.id, session.spec_name or "microservice")
    if not audit.qualityGate.canExport:
        raise HTTPException(403, "Source delivery blocked by SAST: " + audit.qualityGate.summaryMessage)


def require_verified_session(session) -> None:
    if not session_is_verified(session):
        raise HTTPException(403, "Project is not verified: execute and pass a nonempty test suite without fallback before exporting or publishing.")
