"""Verify existing sources without regenerating them or losing previous failures."""
import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException
from app.config import settings
from app.models.execution import ExecutionMode
from app.models.session import SessionLocal, GenerationSessionDB, SessionPhase, SessionStatus
from app.sandbox.docker_runner import parse_test_counts
from app.services.verification_policy import workspace_fingerprint, tests_really_passed


def verify_existing_sources(session_id: str):
    from app.services import docker_service
    import threading
    with docker_service._operations_lock:
        lock = docker_service._operation_locks.setdefault(session_id, threading.Lock())
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "Espere a que finalice la operación actual.")
    try:
        from app.services.local_operations import borrowed_lock
        with borrowed_lock(session_id):
            return _verify_existing_sources(session_id)
    finally:
        lock.release()


def _verify_existing_sources(session_id: str):
    from app.services.workspace_verification import run_workspace_verification
    from app.services.security_service import audit_workspace
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, session_id)
        if not row:
            raise HTTPException(404, "Session not found")
        if row.status in (SessionStatus.RUNNING, SessionStatus.QUEUED):
            raise HTTPException(409, "Espere a que finalice la operación actual.")
        ws = Path(settings.WORKSPACE_DIR) / session_id
        source_roots = [ws / "src", ws / "bootstrap/src", ws / "model/src"]
        from app.services.build_layout import build_layout
        _, _, manifest = build_layout(ws)
        if not any(any(root.rglob('*.java')) for root in source_roots if root.is_dir()) or not manifest.is_file():
            raise HTTPException(409, "Genere primero el código fuente.")
        audit = audit_workspace(str(ws), session_id, row.spec_name)
        if not audit.qualityGate.canExport:
            raise HTTPException(403, audit.qualityGate.summaryMessage)
        previous = json.loads(row.verification_metrics_json or "{}")
        mode = row.execution_mode
        if mode == ExecutionMode.DOCKER:
            from app.services.devops_service import generate_all_devops_assets
            try:
                generate_all_devops_assets(str(ws), session_id, row.spec_name)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
        previous_error = row.error_message
        row.status = SessionStatus.RUNNING
        db.commit()
    try:
        verification = run_workspace_verification(str(ws), mode=mode)
        result = verification.result
        counts = parse_test_counts(result.stdout)
        metrics = {
            "totalTests": counts.total if counts else 0,
            "passedTests": counts.passed if counts else 0,
            "failedTests": counts.failures + counts.errors if counts else 0,
            "allPassed": bool(result.is_success and counts and counts.total > 0 and counts.passed == counts.total),
            "fallback_used": result.fallback_used, "fallback_reason": result.fallback_reason,
            "verificationSkipped": result.verification_skipped,
            "verificationInterrupted": result.verification_interrupted,
            "workspaceFingerprint": getattr(verification, 'workspace_fingerprint', None) or workspace_fingerprint(ws),
            "verificationOutdated": getattr(verification, 'source_changed', False),
            "sourceSnapshotId": getattr(verification, 'snapshot_id', None),
        }
        if previous:
            metrics["previousAttempt"] = {key: value for key, value in previous.items() if key != "previousAttempt"}
        if result.verification_skipped:
            if previous and not previous.get("fallback_used") and previous.get("totalTests", 0) > 0:
                # The choice changes delivery scope, not an executed test outcome.
                metrics = dict(previous)
                metrics["previousError"] = previous_error
                (ws / 'VERIFICATION_STATUS.md').write_text(
                    '# Entrega de fuentes\n\nNo se ejecutaron nuevas pruebas para esta entrega sin Docker.\n'
                    f'La ejecución anterior se conserva: {previous.get("passedTests", 0)}/{previous.get("totalTests", 0)} aprobadas, {previous.get("failedTests", 0)} fallidas.\n'
                    'El cambio de modo no convierte el resultado anterior en una omisión ni en una aprobación.\n', encoding='utf-8')
            metrics["sourceDeliveryReady"] = True
            metrics["sourceDeliveryFingerprint"] = workspace_fingerprint(ws)
        completed = result.verification_skipped or tests_really_passed(metrics)
        with SessionLocal() as db:
            row = db.get(GenerationSessionDB, session_id)
            row.verification_metrics_json = json.dumps(metrics)
            row.status = SessionStatus.COMPLETED if completed else (SessionStatus.PAUSED if result.fallback_used else SessionStatus.BLOCKED)
            row.phase = SessionPhase.CODE_GENERATION if result.verification_skipped else (SessionPhase.VERIFIED if completed else SessionPhase.FAILED)
            row.error_message = None if completed else (result.stderr if result.verification_interrupted else (result.fallback_reason or "La compilación o las pruebas ejecutadas fallaron."))
            row.completed_at = datetime.now(timezone.utc) if completed else None
            db.commit()
        return {"sessionId": session_id, "metrics": metrics, "status": "COMPLETED" if completed else ("PAUSED" if result.fallback_used else "BLOCKED")}
    except Exception:
        with SessionLocal() as db:
            row = db.get(GenerationSessionDB, session_id)
            row.status = SessionStatus.PAUSED
            row.error_message = "Verificación interrumpida. Reintente."
            db.commit()
        raise
