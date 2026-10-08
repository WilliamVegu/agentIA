"""Append-only historical outcomes; validity may change when inputs change."""
import json
from app.models.session import SessionLocal, GenerationSessionDB
from app.models.reliability import VerificationRun, AuditRun
from app.services.verification_policy import tests_really_passed, workspace_fingerprint
from app.services.secret_redaction import redact


def verification_metrics(verification):
    from app.sandbox.docker_runner import parse_test_counts
    result=verification.result
    counts=parse_test_counts(result.stdout)
    metrics={'totalTests':counts.total if counts else 0, 'passedTests':counts.passed if counts else 0,
        'failedTests':counts.failures+counts.errors if counts else 0, 'allPassed':bool(result.is_success and counts and counts.total>0 and counts.passed==counts.total),
        'fallback_used':result.fallback_used, 'fallback_reason':redact(result.fallback_reason),
        'verificationSkipped':result.verification_skipped, 'verificationInterrupted':result.verification_interrupted,
        'workspaceFingerprint':verification.workspace_fingerprint, 'sourceSnapshotId':verification.snapshot_id,
        'verificationOutdated':verification.source_changed, 'evidenceError':redact(result.evidence_error),
        'executionDurationMs':result.duration_ms}
    metrics['allPassed']=tests_really_passed(metrics) and result.exit_code==0
    return metrics


def record_verification(session_id, verification, runner):
    metrics=verification_metrics(verification)
    result=verification.result
    outcome=('SKIPPED_BY_CHOICE' if result.verification_skipped else 'INTERRUPTED' if result.verification_interrupted
        else 'ENVIRONMENT_UNAVAILABLE' if result.fallback_used else 'PASSED' if metrics['allPassed'] else 'FAILED')
    with SessionLocal() as db:
        session=db.get(GenerationSessionDB, session_id)
        if not session:
            return None
        db.query(VerificationRun).filter_by(session_id=session_id, validity='CURRENT').update({'validity':'OUTDATED'})
        reports=[]
        if verification.snapshot_id:
            from pathlib import Path
            from app.config import settings
            from app.services.source_snapshot import validate_snapshot
            manifest,_=validate_snapshot(Path(settings.WORKSPACE_DIR)/session_id,verification.snapshot_id,verification.workspace_fingerprint)
            reports=list(manifest.get('reports',{}))
        record=VerificationRun(session_id=session_id, revision_id=session.revision_id,
            fingerprint=verification.workspace_fingerprint, snapshot_id=verification.snapshot_id,
            outcome=outcome, validity='OUTDATED' if verification.source_changed else 'CURRENT',
            runner=runner, exit_code=result.exit_code, metrics_json=json.dumps(metrics), report_paths_json=json.dumps(reports))
        db.add(record);db.commit()
        return record.run_id


def record_audit(session_id, workspace, report):
    with SessionLocal() as db:
        if not db.get(GenerationSessionDB, session_id):
            return None
        fingerprint=workspace_fingerprint(workspace)
        db.query(AuditRun).filter_by(session_id=session_id, validity='CURRENT').update({'validity':'OUTDATED'})
        record=AuditRun(session_id=session_id, fingerprint=fingerprint, evaluated_status=report.evaluatedStatus,
            score=report.qualityGate.score, source_count=report.metrics.totalLinesOfCode,
            rule_set_version='reliability-v1', findings_json=json.dumps({'formatVersion':2,'report':redact(report.model_dump(mode='json'))},ensure_ascii=False))
        db.add(record);db.commit()
        return record.run_id


def invalidate_evidence(session_id):
    with SessionLocal() as db:
        for model in (VerificationRun, AuditRun):
            db.query(model).filter_by(session_id=session_id).update({'validity':'OUTDATED'})
        db.commit()



def current_audit(session_id,workspace):
    """Read the complete durable audit only when its input still matches."""
    from app.models.security_quality import SecurityQualityAuditReport
    fingerprint=workspace_fingerprint(workspace)
    if not fingerprint: return None
    with SessionLocal() as db:
        row=db.query(AuditRun).filter_by(session_id=session_id,validity='CURRENT').order_by(AuditRun.created_at.desc()).first()
        if not row or row.fingerprint!=fingerprint: return None
        try:
            payload=json.loads(row.findings_json)
            if not isinstance(payload,dict) or payload.get('formatVersion')!=2: return None
            report=SecurityQualityAuditReport.model_validate(payload['report'])
            if report.sessionId!=session_id: return None
            return report
        except (ValueError,TypeError,KeyError): return None
