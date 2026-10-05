import os
from pathlib import Path
import subprocess
import sys
from app.services.session_operation_lock import SessionOperationLock
from scripts.verify_native_source_flow import stop_process_tree


def test_lock_excludes_other_process_and_releases_after_crash(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path))
    lock = SessionOperationLock('session')
    other = SessionOperationLock('session')
    assert lock.acquire(False)
    assert not other.acquire(False)
    assert other.locked()
    lock.release()
    code = '''
import sys
from app.config import settings
from app.services.session_operation_lock import SessionOperationLock
settings.WORKSPACE_DIR = sys.argv[1]
lock = SessionOperationLock('session')
assert lock.acquire(False)
print('ACQUIRED', flush=True)
sys.stdin.read()
'''
    environment = dict(os.environ, PYTHONPATH=str(Path('backend').resolve()))
    process = subprocess.Popen([sys.executable, '-c', code, str(tmp_path)],
        env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == 'ACQUIRED'
        assert not other.acquire(False)
        different = SessionOperationLock('different')
        assert different.acquire(False)
        different.release()
        # Windows venv launches a child interpreter; terminate the exact owned tree.
        stop_process_tree(process)
        assert other.acquire(timeout=3)
        other.release()
    finally:
        if process.poll() is None:
            stop_process_tree(process)
        process.wait(timeout=10)
        process.stdin.close(); process.stdout.close(); process.stderr.close()


def test_cancel_request_reaches_other_process_without_false_recovery(tmp_path, monkeypatch):
    from app.config import settings
    from app.models.execution import ExecutionMode
    from app.services.local_runtime import restore
    from app.services.local_operations import request_cancel
    from app.services import docker_service
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path))
    monkeypatch.setattr('app.services.execution_policy.execution_mode', lambda _: ExecutionMode.DOCKER)
    monkeypatch.setattr(docker_service, '_active_deployments', {})
    code = '''
import sys,time
from app.config import settings
settings.WORKSPACE_DIR = sys.argv[1]
from app.models.devops import LocalDeploymentSession, DeploymentStatus
from app.services.local_runtime import persist
from app.services.local_operations import register,finish
from app.services.session_operation_lock import SessionOperationLock
lock = SessionOperationLock('external-worker')
assert lock.acquire(False)
row = LocalDeploymentSession(sessionId='external-worker', operationId='external-operation', status=DeploymentStatus.BUILDING)
event = register(row,'DEPLOY')
persist(row)
print('ACTIVE',flush=True)
deadline=time.monotonic()+20
while not event.is_set() and time.monotonic()<deadline: time.sleep(.02)
assert event.is_set()
row.operationPhase='INTERRUPTED'
row.status=DeploymentStatus.FAILED
finish(row);persist(row);lock.release()
print('CANCELLED',flush=True)
'''
    environment = dict(os.environ, PYTHONPATH=str(Path('backend').resolve()))
    process = subprocess.Popen([sys.executable, '-c', code, str(tmp_path)], env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == 'ACTIVE'
        existing = restore('external-worker')
        assert existing.status.value == 'BUILDING' and existing.finishedAt is None
        requested = request_cancel('external-worker', 'external-operation')
        assert requested.cancelRequested
        assert process.stdout.readline().strip() == 'CANCELLED'
        process.wait(timeout=10)
        assert process.returncode == 0, process.stderr.read()
        completed = restore('external-worker')
        assert completed.finishedAt and completed.cancelRequested and completed.operationPhase == 'INTERRUPTED'
    finally:
        if process.poll() is None: stop_process_tree(process)
        process.wait(timeout=10)
        process.stdout.close(); process.stderr.close()
