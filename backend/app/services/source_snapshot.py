"""Sealed source archive and disposable execution copy, without Docker or secrets."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
import zipfile
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[3]
STAGING = ROOT / '.run' / 'verification-snapshots'
EXCLUDED = {'.git', '.agentia-runtime', 'target', 'build', '.gradle', '.m2', 'node_modules',
            '__pycache__', '.venv', '.run', '.idea'}


def snapshot_directory(workspace, snapshot_id):
    if not isinstance(snapshot_id, str) or len(snapshot_id) != 32 or any(c not in '0123456789abcdef' for c in snapshot_id):
        raise ValueError('Identidad de snapshot inválida')
    ws = Path(workspace).resolve()
    root = ws / '.agentia-runtime' / 'snapshots'
    if not root.resolve().is_relative_to(ws):
        raise ValueError('Snapshot fuera del workspace')
    directory = root / snapshot_id
    if not directory.resolve().is_relative_to(ws):
        raise ValueError('Snapshot enlazado fuera del workspace')
    return directory


class SourceSnapshot:
    def __init__(self, workspace):
        from app.services.verification_policy import workspace_fingerprint
        self.workspace = Path(workspace).resolve()
        self.id = uuid.uuid4().hex
        self.directory = snapshot_directory(self.workspace, self.id)
        self.directory.mkdir(parents=True)
        STAGING.mkdir(parents=True, exist_ok=True)
        self.stage = Path(tempfile.mkdtemp(prefix='s-', dir=STAGING))
        self.working = self.stage / self.workspace.name
        self.working.mkdir()
        try:
            before = workspace_fingerprint(self.workspace)
            files = {}
            archive = self.directory / 'sources.zip'
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
                for root, dirs, names in os.walk(self.workspace, followlinks=False):
                    for d in dirs:
                        if (Path(root) / d).is_symlink():
                            raise ValueError('Directorios enlazados no admitidos en snapshot')
                    dirs[:] = [d for d in dirs if d not in EXCLUDED]
                    for name in sorted(names):
                        if name in {'images.tar', 'DELIVERY_STATUS.json', '.DS_Store', 'Thumbs.db'} or name.endswith('.pyc') or (name.startswith('.env') and name != '.env.example'):
                            continue
                        source = Path(root) / name
                        if source.is_symlink() or not source.resolve().is_relative_to(self.workspace):
                            raise ValueError('Archivo enlazado no admitido en snapshot')
                        relative = source.relative_to(self.workspace).as_posix()
                        data = source.read_bytes()
                        output.writestr(relative, data)
                        target = self.working / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
                        files[relative] = hashlib.sha256(data).hexdigest()
            fingerprint = workspace_fingerprint(self.working)
            if not before or fingerprint != before or workspace_fingerprint(self.workspace) != before:
                raise ValueError('Las fuentes cambiaron al capturar snapshot; reintente')
            self.manifest = {'formatVersion': 1, 'snapshotId': self.id, 'sessionId': self.workspace.name,
                'workspaceFingerprint': fingerprint, 'archiveSha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                'files': files, 'verification': 'NOT_RUN'}
            self._save()
        except Exception:
            self.close()
            raise

    def _save(self):
        temporary = self.directory / 'manifest.tmp'
        temporary.write_text(json.dumps(self.manifest, indent=2), encoding='utf-8')
        temporary.replace(self.directory / 'manifest.json')

    def finish(self, result, source_changed):
        from app.sandbox.docker_runner import parse_test_counts
        counts = parse_test_counts(result.stdout)
        self.manifest.update(verification='PASSED' if result.is_success and not source_changed and counts and
            counts.total > 0 and counts.all_passed else ('OUTDATED' if source_changed else 'NOT_PASSED'),
            exitCode=result.exit_code, tests=counts.total if counts else 0)
        reports = {}
        for root, dirs, files in os.walk(self.working):
            dirs[:] = [d for d in dirs if d not in {'.git', '.gradle', 'node_modules'}]
            for name in files:
                source = Path(root) / name
                relative = source.relative_to(self.working)
                if name.endswith('.xml') and ('surefire-reports' in relative.parts or 'test-results' in relative.parts):
                    if source.is_symlink() or not source.resolve().is_relative_to(self.working):
                        raise ValueError('Informe enlazado no admitido')
                    data = source.read_bytes()
                    target = self.directory / 'reports' / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    reports[relative.as_posix()] = hashlib.sha256(data).hexdigest()
        self.manifest['reports'] = reports
        jars = {}
        for source in self.working.rglob('*.jar'):
            relative = source.relative_to(self.working)
            if not ({'target', 'build'} & set(relative.parts)) or source.name.startswith('original-') or source.name.endswith(('-plain.jar', '-sources.jar', '-javadoc.jar')):
                continue
            if source.is_symlink() or not source.resolve().is_relative_to(self.working):
                raise ValueError('JAR enlazado no admitido')
            try:
                with zipfile.ZipFile(source) as jar:
                    if jar.testzip() or not any(n.startswith('BOOT-INF/') for n in jar.namelist()) or b'Main-Class: org.springframework.boot.loader.' not in jar.read('META-INF/MANIFEST.MF'):
                        continue
            except (OSError, KeyError, zipfile.BadZipFile):
                continue
            data = source.read_bytes()
            target = self.directory / 'artifacts' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            jars[relative.as_posix()] = hashlib.sha256(data).hexdigest()
        self.manifest['executableJars'] = jars
        self._save()

    def close(self):
        if self.stage.resolve().parent != STAGING.resolve():
            raise ValueError('Directorio de ejecución inesperado')
        shutil.rmtree(self.stage)


def validate_snapshot(workspace, snapshot_id, fingerprint):
    try:
        return _validate_snapshot(workspace, snapshot_id, fingerprint)
    except (KeyError, TypeError, AttributeError, zipfile.BadZipFile) as exc:
        raise ValueError('Snapshot malformado') from exc


def _validate_snapshot(workspace, snapshot_id, fingerprint):
    from app.services.verification_policy import fingerprint_input
    directory = snapshot_directory(workspace, snapshot_id)
    metadata = directory / 'manifest.json'
    if metadata.is_symlink() or not metadata.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Metadata de snapshot enlazada no admitida')
    manifest = json.loads(metadata.read_text(encoding='utf-8'))
    if manifest.get('formatVersion') != 1 or manifest.get('snapshotId') != snapshot_id or manifest.get('sessionId') != Path(workspace).name or manifest.get('workspaceFingerprint') != fingerprint:
        raise ValueError('Snapshot de fuentes incompatible')
    archive = directory / 'sources.zip'
    if archive.is_symlink() or hashlib.sha256(archive.read_bytes()).hexdigest() != manifest.get('archiveSha256'):
        raise ValueError('Integridad de snapshot inválida')
    with zipfile.ZipFile(archive) as contents:
        names = contents.namelist()
        if len(names) != len(set(names)) or set(names) != set(manifest['files']):
            raise ValueError('Catálogo de snapshot inválido')
        digest = hashlib.sha256()
        for name in sorted(names, key=Path):
            if Path(name).is_absolute() or ':' in name or '..' in Path(name).parts or '\\' in name:
                raise ValueError('Ruta de snapshot inválida')
            data = contents.read(name)
            if hashlib.sha256(data).hexdigest() != manifest['files'][name]:
                raise ValueError('Archivo de snapshot corrupto')
            if fingerprint_input(name):
                digest.update(name.encode()); digest.update(b'\0'); digest.update(data); digest.update(b'\0')
        if digest.hexdigest() != fingerprint:
            raise ValueError('Fingerprint del contenido del snapshot inválido')
    for category, key in [('reports', 'reports'), ('artifacts', 'executableJars')]:
        for relative, expected in manifest.get(key, {}).items():
            file = directory / category / relative
            if file.is_symlink() or not file.resolve().is_relative_to(directory.resolve()) or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
                raise ValueError('Integridad del artefacto de snapshot inválida')
    return manifest, archive


@contextmanager
def materialize_snapshot(workspace, snapshot_id, fingerprint):
    manifest, archive = validate_snapshot(workspace, snapshot_id, fingerprint)
    if manifest.get('verification') != 'PASSED' or manifest.get('exitCode') != 0 or manifest.get('tests', 0) <= 0:
        raise ValueError('Snapshot sin verificación aprobada')
    if len(manifest.get('executableJars', {})) != 1:
        raise ValueError('Snapshot requiere exactamente un JAR ejecutable verificado')
    STAGING.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='d-', dir=STAGING))
    working = stage / Path(workspace).name
    working.mkdir()
    try:
        with zipfile.ZipFile(archive) as contents:
            for name in contents.namelist():
                target = working / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(contents.read(name))
        from app.services.verification_policy import workspace_fingerprint
        if workspace_fingerprint(working) != fingerprint:
            raise ValueError('Snapshot cambió al materializar')
        relative, jar_hash = next(iter(manifest['executableJars'].items()))
        jar = snapshot_directory(workspace, snapshot_id) / 'artifacts' / relative
        payload = jar.read_bytes()
        if hashlib.sha256(payload).hexdigest() != jar_hash:
            raise ValueError('JAR verificado corrupto')
        (working / '.verified-artifact').mkdir()
        (working / '.verified-artifact/application.jar').write_bytes(payload)
        yield working, jar_hash
    finally:
        if stage.resolve().parent != STAGING.resolve():
            raise ValueError('Directorio de ejecución inesperado')
        shutil.rmtree(stage)
