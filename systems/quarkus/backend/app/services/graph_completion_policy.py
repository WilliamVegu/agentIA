"""A graph terminal label is qualified against current retained evidence."""
import json
from pathlib import Path
from app.models.execution import ExecutionMode
from app.services.verification_policy import tests_really_passed,workspace_fingerprint


def previous_failed(session):
    try: metrics=json.loads(session.verification_metrics_json or '{}')
    except (ValueError,TypeError): return True
    return bool(metrics and not metrics.get('verificationSkipped') and not metrics.get('fallback_used') and not tests_really_passed(metrics))


def qualify_completion(session,workspace,state):
    metrics=state.get('test_metrics') or {}
    fingerprint=workspace_fingerprint(workspace)
    if session.execution_mode==ExecutionMode.SOURCE_ONLY and metrics.get('verificationSkipped'):
        if previous_failed(session): return False
        from app.services.security_service import audit_workspace
        report=audit_workspace(str(workspace),session.id,session.spec_name)
        if not fingerprint or not report.qualityGate.canExport: return False
        state['test_metrics']={**metrics,'totalTests':0,'passedTests':0,'failedTests':0,'allPassed':False,'sourceDeliveryReady':True,'sourceDeliveryFingerprint':fingerprint}
        return True
    if session.execution_mode!=ExecutionMode.DOCKER or not tests_really_passed(metrics) or not fingerprint or metrics.get('workspaceFingerprint')!=fingerprint or not metrics.get('sourceSnapshotId'):
        return False
    from app.services.source_snapshot import validate_snapshot
    try:
        manifest,_=validate_snapshot(Path(workspace),metrics['sourceSnapshotId'],fingerprint)
        return bool(manifest.get('verification')=='PASSED' and manifest.get('tests')==metrics.get('totalTests') and (manifest.get('nativeArtifacts') or manifest.get('executableJars')))
    except (OSError,ValueError,TypeError): return False
