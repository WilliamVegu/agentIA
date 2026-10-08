"""Sealed source archive and disposable execution copy, without Docker or secrets."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
import zipfile
import xml.etree.ElementTree as ET
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[3]
STAGING = ROOT / '.run' / 'verification-snapshots'
EXCLUDED = {'.git', '.agentia-runtime', '.operation-locks', 'target', 'build', '.gradle', '.m2', 'node_modules',
            '__pycache__', '.venv', '.run', '.idea'}


def _io_path(path):
    """Use Windows extended paths for I/O without changing canonical identities."""
    path = Path(path)
    if os.name != 'nt':
        return path
    absolute = str(path.absolute())
    if absolute.startswith('\\\\?\\'):
        return path
    if absolute.startswith('\\\\'):
        return Path('\\\\?\\UNC\\' + absolute[2:])
    return Path('\\\\?\\' + absolute)


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
                        _io_path(target.parent).mkdir(parents=True, exist_ok=True)
                        _io_path(target).write_bytes(data)
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
            counts.total > 0 and counts.passed == counts.total and not result.fallback_used and not result.verification_skipped and not result.verification_interrupted and not result.evidence_error else ('OUTDATED' if source_changed else 'NOT_PASSED'),
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
                    data = _io_path(source).read_bytes()
                    target = self.directory / 'reports' / relative
                    _io_path(target.parent).mkdir(parents=True, exist_ok=True)
                    _io_path(target).write_bytes(data)
                    reports[relative.as_posix()] = hashlib.sha256(data).hexdigest()
        self.manifest['reports'] = reports
        if self.manifest['verification'] == 'PASSED':
            totals=[0,0,0,0]
            try:
                if not reports: raise ValueError('No se conservaron informes XML')
                for relative in reports:
                    root=ET.parse(_io_path(self.directory/'reports'/relative)).getroot()
                    suites=[root] if root.tag=='testsuite' else root.findall('testsuite')
                    if not suites: raise ValueError('Informe sin suite')
                    for suite in suites:
                        values=[int(suite.get(key,'0')) for key in ['tests','failures','errors','skipped']]
                        if any(value<0 for value in values): raise ValueError('Conteos negativos')
                        totals=[left+right for left,right in zip(totals,values)]
                if totals[0]<=0 or totals[1:]!=[0,0,0] or not counts or counts.total!=totals[0]:
                    raise ValueError('XML y resumen de pruebas no acreditan la misma suite aprobada')
            except (ValueError,OSError,ET.ParseError) as error:
                self.manifest['verification']='NOT_PASSED'
                result.evidence_error=str(error)
                result.exit_code=result.exit_code or 1
        artifacts = {}
        candidates=[root for root in (self.working/'target/quarkus-app',self.working/'build/quarkus-app') if (root/'quarkus-run.jar').is_file()]
        if len(candidates)==1:
            native=candidates[0]
            with zipfile.ZipFile(_io_path(native/'quarkus-run.jar')) as jar:
                if jar.testzip() or b'Main-Class: io.quarkus.bootstrap.runner.QuarkusEntryPoint' not in jar.read('META-INF/MANIFEST.MF'):
                    raise ValueError('Runner Quarkus inválido')
            native_io=_io_path(native)
            for discovered in native_io.rglob('*'):
                source=native/discovered.relative_to(native_io)
                if source.is_symlink() or not source.resolve().is_relative_to(native.resolve()):
                    raise ValueError('Artefacto Quarkus enlazado')
                if _io_path(source).is_file():
                    relative=source.relative_to(self.working)
                    data=_io_path(source).read_bytes()
                    target=self.directory/'artifacts'/relative
                    _io_path(target.parent).mkdir(parents=True,exist_ok=True)
                    _io_path(target).write_bytes(data)
                    artifacts[relative.as_posix()]=hashlib.sha256(data).hexdigest()
            self.manifest['artifactRoot']=native.relative_to(self.working).as_posix()
        self.manifest['artifactLayout']='quarkus-fast-jar' if artifacts else None
        self.manifest['nativeArtifacts']=artifacts
        self.manifest['executableJars']={}
        self.manifest['exitCode']=result.exit_code
        self._save()

    def close(self):
        if self.stage.resolve().parent != STAGING.resolve():
            raise ValueError('Directorio de ejecución inesperado')
        shutil.rmtree(_io_path(self.stage))


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
    for category, key in [('reports', 'reports'), ('artifacts', 'nativeArtifacts')]:
        for relative, expected in manifest.get(key, {}).items():
            file = directory / category / relative
            if file.is_symlink() or not file.resolve().is_relative_to(directory.resolve()) or hashlib.sha256(_io_path(file).read_bytes()).hexdigest() != expected:
                raise ValueError('Integridad del artefacto de snapshot inválida')
    return manifest, archive


@contextmanager
def materialize_snapshot(workspace, snapshot_id, fingerprint):
    manifest, archive = validate_snapshot(workspace, snapshot_id, fingerprint)
    if manifest.get('verification') != 'PASSED' or manifest.get('exitCode') != 0 or manifest.get('tests', 0) <= 0:
        raise ValueError('Snapshot sin verificación aprobada')
    if manifest.get('artifactLayout') != 'quarkus-fast-jar' or not manifest.get('nativeArtifacts'):
        raise ValueError('Snapshot sin layout ejecutable Quarkus verificado')
    STAGING.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='d-', dir=STAGING))
    working = stage / Path(workspace).name
    working.mkdir()
    try:
        with zipfile.ZipFile(archive) as contents:
            for name in contents.namelist():
                target = working / name
                _io_path(target.parent).mkdir(parents=True, exist_ok=True)
                _io_path(target).write_bytes(contents.read(name))
        from app.services.verification_policy import workspace_fingerprint
        if workspace_fingerprint(working) != fingerprint:
            raise ValueError('Snapshot cambió al materializar')
        artifact_root=manifest['artifactRoot']
        combined=hashlib.sha256()
        for relative,expected in sorted(manifest['nativeArtifacts'].items()):
            native_relative=Path(relative).relative_to(artifact_root)
            file=snapshot_directory(workspace,snapshot_id)/'artifacts'/relative
            payload=_io_path(file).read_bytes()
            if hashlib.sha256(payload).hexdigest()!=expected:
                raise ValueError('Artefacto Quarkus corrupto')
            target=working/'.verified-artifact/quarkus-app'/native_relative
            _io_path(target.parent).mkdir(parents=True,exist_ok=True);_io_path(target).write_bytes(payload)
            combined.update(relative.encode());combined.update(expected.encode())
        yield working,combined.hexdigest()
    finally:
        if stage.resolve().parent != STAGING.resolve():
            raise ValueError('Directorio de ejecución inesperado')
        shutil.rmtree(_io_path(stage))
