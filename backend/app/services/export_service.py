import io
import os
import zipfile
import json
from pathlib import Path


def delivery_status(workspace):
    """Source ZIP status is database evidence, never a Docker availability probe."""
    from app.config import settings
    from app.models.session import SessionLocal, GenerationSessionDB
    from app.services.verification_policy import verification_outcome, workspace_fingerprint
    ws = Path(workspace).resolve()
    status = {'formatVersion': 1, 'packageKind': 'SOURCES', 'includesImages': False,
              'verificationOutcome': 'NOT_EXECUTED', 'executionMode': 'SOURCE_ONLY',
              'workspaceFingerprint': workspace_fingerprint(ws),
              'note': 'Fuentes y scripts; las imagenes requieren el kit separado. No acredita ejecucion offline en otro equipo.'}
    if ws == (Path(settings.WORKSPACE_DIR) / ws.name).resolve():
        with SessionLocal() as db:
            row = db.get(GenerationSessionDB, ws.name)
            if row:
                status['executionMode'] = row.execution_mode
                status['verificationOutcome'] = verification_outcome(row).value
                metrics = json.loads(row.verification_metrics_json or '{}')
                status['tests'] = {key: metrics.get(key) for key in ('totalTests', 'passedTests', 'failedTests', 'allPassed',
                    'verificationSkipped', 'verificationInterrupted', 'fallback_used') if key in metrics}
    return status

def create_project_zip(workspace_path: str) -> bytes:
    """
    Packages the generated project into a standalone, clean ZIP archive in-memory.
    Excludes build directories (target/), caches, and VCS files.
    """
    ws_dir = Path(workspace_path).resolve()
    buffer = io.BytesIO()
    status = delivery_status(ws_dir)
    sealed_archive = None
    from app.config import settings
    from app.models.session import SessionLocal, GenerationSessionDB
    if ws_dir == (Path(settings.WORKSPACE_DIR) / ws_dir.name).resolve():
        with SessionLocal() as db:
            row = db.get(GenerationSessionDB, ws_dir.name)
            metrics = json.loads(row.verification_metrics_json or '{}') if row else {}
            if status['verificationOutcome'] == 'PASSED' and metrics.get('sourceSnapshotId'):
                from app.services.source_snapshot import validate_snapshot
                manifest, sealed_archive = validate_snapshot(ws_dir, metrics['sourceSnapshotId'], status['workspaceFingerprint'])
                if manifest['verification'] != 'PASSED':
                    raise ValueError('Snapshot sin verificación aprobada')
                status['sourceSnapshotId'] = metrics['sourceSnapshotId']

    ignored_dirs = {".git", "target", "build", ".gradle", ".idea", "__pycache__", ".m2", ".agentia-runtime", "node_modules"}
    ignored_files = {".DS_Store", "Thumbs.db", "DELIVERY_STATUS.json", "images.tar"}

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if sealed_archive:
            with zipfile.ZipFile(sealed_archive) as sealed:
                for name in sealed.namelist():
                    zf.writestr(name, sealed.read(name))
        for root, dirs, files in ([] if sealed_archive else os.walk(ws_dir)):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file in files:
                if file in ignored_files or file.endswith(".pyc") or (file.startswith(".env") and file != ".env.example"):
                    continue
                full_path = Path(root) / file
                if full_path.is_symlink() or not full_path.resolve().is_relative_to(ws_dir):
                    continue
                rel_path = str(full_path.relative_to(ws_dir)).replace("\\", "/")
                zf.write(full_path, arcname=rel_path)

        from app.services.verification_policy import workspace_fingerprint
        if workspace_fingerprint(ws_dir) != status['workspaceFingerprint']:
            raise RuntimeError('Las fuentes cambiaron durante la exportacion. Reintente con el proyecto sin operaciones activas.')
        zf.writestr('DELIVERY_STATUS.json', json.dumps(status, indent=2))

    buffer.seek(0)
    return buffer.getvalue()


def export_full_bundle(workspace_path: str) -> bytes:
    """Packages the complete microservice workspace bundle (specs, stories, architecture,

    models, code, tests, security audits, Dockerfile, CI/CD, and Kubernetes manifests)
    into a clean production ZIP archive.
    """
    return create_project_zip(workspace_path)

