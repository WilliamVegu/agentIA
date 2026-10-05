"""Stage new versioned assets; preserve edits and refuse unowned existing outputs."""
import hashlib
import json
import shutil
import uuid
import tempfile
from pathlib import Path

TEMPLATE_VERSION = 4
STAGING_ROOT = Path(__file__).resolve().parents[3] / '.run' / 'asset-staging'
EXCLUDED = {'.git', '.agentia-runtime', 'target', 'build', '.gradle', '.m2', 'node_modules', '__pycache__'}
OWNED = {
    'Dockerfile', '.dockerignore', 'docker-compose.yml', 'Dockerfile.prepare', 'Dockerfile.runtime',
    'prepare-local.ps1', 'start-local.ps1', 'stop-local.ps1', 'restart-local.ps1', 'cleanup-local.ps1',
    'runtime-common.ps1', '.env.example', 'LOCAL_DEPLOYMENT.md', 'LOCAL_DELIVERY.json',
    'export-offline-kit.ps1', 'import-offline-kit.ps1', 'OFFLINE_KIT.md', 'ASSET_CONFIGURATION.json',
    '.github/workflows/ci-cd.yml', '.gitlab-ci.yml',
    'k8s/deployment.yaml', 'k8s/service.yaml', 'k8s/configmap.yaml', 'k8s/ingress.yaml',
}


class AssetConflict(ValueError):
    pass


def inventory(root):
    result = {}
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if any(part in EXCLUDED for part in relative.parts) or (path.name.startswith('.env') and path.name != '.env.example'):
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise AssetConflict('Ruta enlazada fuera del proyecto; no se modifican activos.')
        if path.is_file():
            result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def generate_safely(workspace, session_id, writer, **configuration):
    from app.services import docker_service
    import threading
    root = Path(workspace).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with docker_service._operations_lock:
        lock = docker_service._operation_locks.setdefault(session_id, threading.Lock())
    from app.services.local_operations import has_borrowed_lock
    borrowed = has_borrowed_lock(session_id)
    if not borrowed and not lock.acquire(blocking=False):
        raise AssetConflict('Hay una operacion local activa; espere antes de regenerar manifiestos.')
    stage_parent = None
    try:
        if not (root / '.agentia-runtime').resolve().is_relative_to(root):
            raise AssetConflict('Registro operativo fuera del proyecto; no se modifican activos.')
        baseline = inventory(root)
        ledger_file = root / '.agentia-runtime' / 'generated-assets.json'
        if ledger_file.exists():
            try:
                ledger = json.loads(ledger_file.read_text(encoding='utf-8'))
                if ledger['sessionId'] != session_id or ledger['formatVersion'] != 1:
                    raise ValueError('identity')
                if type(ledger.get('templateVersion')) is not int or ledger['templateVersion'] > TEMPLATE_VERSION:
                    raise ValueError('version')
                hashes = ledger['files']
                if not isinstance(hashes, dict) or not set(hashes).issubset(OWNED):
                    raise ValueError('files')
            except (ValueError, KeyError, TypeError) as exc:
                raise AssetConflict('Registro de activos invalido; no se sobrescriben archivos.') from exc
            conflicts = [name for name, digest in hashes.items() if baseline.get(name) != digest]
            conflicts += [name for name in OWNED if name in baseline and name not in hashes]
        else:
            conflicts = sorted(OWNED.intersection(baseline))
        if conflicts:
            raise AssetConflict('Activos existentes sin propiedad o editados: ' + ', '.join(sorted(set(conflicts))) +
                                '. Conserve sus cambios; restaure el contenido registrado o use una carpeta nueva.')
        if not STAGING_ROOT.resolve().is_relative_to(Path(__file__).resolve().parents[3]):
            raise AssetConflict('Ruta temporal fuera del repositorio.')
        STAGING_ROOT.mkdir(parents=True, exist_ok=True)
        stage_parent = Path(tempfile.mkdtemp(prefix='a-', dir=STAGING_ROOT))
        stage = stage_parent / root.name
        stage.mkdir(parents=True)
        for name in baseline:
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, destination)
        bundle = writer(str(stage), session_id, **configuration)
        from app.services.build_layout import build_layout
        tool, directory, _ = build_layout(stage)
        config = {'formatVersion': 1, 'templateVersion': TEMPLATE_VERSION,
                  'sessionId': session_id, 'serviceName': bundle.serviceName,
                  'databaseEngine': bundle.databaseEngine.value,
                  'hostPort': configuration.get('host_port', 8080),
                  'buildTool': tool, 'buildDirectory': directory}
        (stage / 'ASSET_CONFIGURATION.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
        staged = inventory(stage)
        if inventory(root) != baseline:
            raise AssetConflict('El proyecto cambio durante la generacion; no se publican los activos preparados.')
        changed = [name for name, digest in staged.items() if baseline.get(name) != digest]
        # Each file is replaced atomically; rollback restores files if any commit step fails.
        originals = {name: (root / name).read_bytes() if name in baseline else None for name in changed}
        try:
            for name in changed:
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_name(destination.name + '.agentia-' + uuid.uuid4().hex + '.tmp')
                try:
                    shutil.copyfile(stage / name, temporary)
                    temporary.replace(destination)
                finally:
                    temporary.unlink(missing_ok=True)
            ledger = {'formatVersion': 1, 'templateVersion': TEMPLATE_VERSION, 'sessionId': session_id,
                      'configuration': config, 'files': {name: staged[name] for name in sorted(OWNED.intersection(staged))}}
            ledger_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = ledger_file.with_name(ledger_file.name + '.' + uuid.uuid4().hex + '.tmp')
            try:
                temporary.write_text(json.dumps(ledger, indent=2), encoding='utf-8')
                temporary.replace(ledger_file)
            finally:
                temporary.unlink(missing_ok=True)
        except Exception:
            for name, content in originals.items():
                if content is None:
                    (root / name).unlink(missing_ok=True)
                else:
                    (root / name).write_bytes(content)
            raise
        return bundle
    finally:
        # Only this UUID staging checkout is removed; never original sources or runtime data.
        try:
            if stage_parent is not None and stage_parent.exists():
                resolved = stage_parent.resolve()
                if resolved.parent != STAGING_ROOT.resolve():
                    raise RuntimeError('Ruta de staging inesperada')
                shutil.rmtree(resolved)
        finally:
            if not borrowed:
                lock.release()
