"""Explicit workspace fixtures; no test fixture claims a real build occurred."""
import json
from pathlib import Path
from app.config import settings
from app.models.session import GenerationSessionDB, SessionLocal, SessionStatus, SessionPhase
from app.services.verification_policy import workspace_fingerprint


def source_delivery(session_id, workspace=None):
    workspace = Path(workspace or Path(settings.WORKSPACE_DIR) / session_id)
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, session_id)
        row.execution_mode = 'SOURCE_ONLY'
        row.status = SessionStatus.COMPLETED
        row.phase = SessionPhase.CODE_GENERATION
        row.error_message = None
        row.verification_metrics_json = json.dumps({
            'verificationSkipped': True, 'allPassed': False, 'fallback_used': False,
            'workspaceFingerprint': workspace_fingerprint(workspace),
        })
        db.commit()


def repair_workspace(session_id, source_files, mode='SOURCE_ONLY'):
    workspace = Path(settings.WORKSPACE_DIR) / session_id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / 'pom.xml').write_text('<project/>', encoding='utf-8')
    for relative, content in source_files.items():
        file = workspace / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding='utf-8')
    with SessionLocal() as db:
        db.merge(GenerationSessionDB(id=session_id, spec_id='repair-test', spec_name='repair-service',
            execution_mode=mode, status=SessionStatus.BLOCKED, phase=SessionPhase.FAILED))
        db.commit()
    return workspace
