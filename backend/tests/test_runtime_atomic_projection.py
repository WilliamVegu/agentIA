import json
from pathlib import Path
import pytest
from app.config import settings
from app.models.devops import LocalDeploymentSession, DeploymentStatus
from app.services.local_runtime import persist


@pytest.mark.parametrize('persistent', [False, True])
def test_runtime_projection_retries_only_transient_windows_locks(tmp_path, monkeypatch, persistent):
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path))
    row = LocalDeploymentSession(sessionId='projection-lock', status=DeploymentStatus.RUNNING)
    persist(row)
    directory = tmp_path / row.sessionId / '.agentia-runtime'
    previous = (directory / 'deployment.json').read_bytes()
    original = Path.replace
    calls = []
    pauses = []

    def sharing_lock(path, target):
        if path.name.startswith('deployment-'):
            calls.append(str(path))
            if persistent or len(calls) < 3:
                error = PermissionError('simulated Windows sharing lock')
                error.winerror = 32
                raise error
        return original(path, target)

    monkeypatch.setattr(Path, 'replace', sharing_lock)
    monkeypatch.setattr('app.services.local_runtime.time.sleep', pauses.append)
    row.status = DeploymentStatus.HEALTHY
    if persistent:
        with pytest.raises(PermissionError):
            persist(row)
        assert len(calls) == 5 and len(pauses) == 4
        assert (directory / 'deployment.json').read_bytes() == previous
    else:
        persist(row)
        assert len(calls) == 3 and len(pauses) == 2
        assert json.loads((directory / 'deployment.json').read_text())['status'] == 'HEALTHY'
    assert not list(directory.glob('deployment-*.tmp'))
