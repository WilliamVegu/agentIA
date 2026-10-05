import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.models.devops import DeploymentStatus
from app.models.session import SessionLocal, GenerationSessionDB
from app.models.execution import VerificationOutcome, ExecutionMode
from app.sandbox.docker_runner import DockerExecutionResult, run_docker_sandbox
from app.services import docker_service, local_operations, workspace_verification, sandbox_resources
from app.services.verification_policy import tests_really_passed as real_tests_passed, verification_outcome
from test_local_docker_runtime import runtime


def test_verification_claims_lock_and_cancel_prevents_pass_and_releases(runtime, monkeypatch):
    def verify(path, callback):
        row = docker_service._active_deployments[runtime.id]
        assert row.operationKind == 'VERIFY' and row.operationPhase == 'VERIFY'
        assert docker_service._operation_locks[runtime.id].locked()
        local_operations.request_cancel(runtime.id, row.operationId)
        return DockerExecutionResult(exit_code=0, stdout='Tests run: 3, Failures: 0, Errors: 0, Skipped: 0')
    monkeypatch.setattr(workspace_verification, '_run_sandbox_blocking', verify)
    result = workspace_verification.run_workspace_verification(str(runtime.ws)).result
    assert not result.is_success and result.verification_interrupted and result.fallback_used
    row = docker_service._active_deployments[runtime.id]
    assert row.finishedAt and row.cancelRequested and row.operationPhase == 'INTERRUPTED'
    assert not docker_service._operation_locks[runtime.id].locked()


def test_busy_verification_does_not_touch_sources_or_reports(runtime, monkeypatch):
    lock = threading.Lock(); lock.acquire()
    docker_service._operation_locks[runtime.id] = lock
    reports = runtime.ws / 'target/surefire-reports'; reports.mkdir(parents=True)
    evidence = reports / 'old.xml'; evidence.write_text('<testsuite tests="3"/>')
    helper = Mock(side_effect=AssertionError('modified busy workspace'))
    monkeypatch.setattr(workspace_verification, '_verify_workspace', helper)
    try:
        result = workspace_verification.run_workspace_verification(str(runtime.ws)).result
        assert result.fallback_used and 'otra operación' in result.fallback_reason
        assert evidence.exists()
    finally: lock.release()


def test_borrowed_manual_verification_lock_is_not_reacquired_or_released(runtime, monkeypatch):
    lock = threading.Lock(); lock.acquire()
    docker_service._operation_locks[runtime.id] = lock
    monkeypatch.setattr(workspace_verification, '_run_sandbox_blocking', lambda *args: DockerExecutionResult(exit_code=0))
    try:
        with local_operations.borrowed_lock(runtime.id):
            assert workspace_verification.run_workspace_verification(str(runtime.ws)).result.is_success
        assert lock.locked()
    finally: lock.release()


def test_interruption_is_not_a_failure_or_pass_even_with_counts(runtime):
    metrics = {'totalTests': 3, 'passedTests': 3, 'failedTests': 0, 'allPassed': True,
               'fallback_used': False, 'verificationInterrupted': True}
    assert not real_tests_passed(metrics)
    session = SimpleNamespace(id=runtime.id, verification_metrics_json=json.dumps(metrics))
    assert verification_outcome(session) == VerificationOutcome.INTERRUPTED


def test_cleanup_rejects_foreign_operation_before_any_removal(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        output = 'owned-id' if command[1] == 'ps' else json.dumps([{'Id': 'owned-id', 'Name': '/agentia-verify-probe',
            'Config': {'Labels': {'com.docker.compose.project': 's', 'io.agentia.role': 'verification', 'io.agentia.operation': 'other'}}}])
        return SimpleNamespace(returncode=0, stdout=output)
    monkeypatch.setattr(sandbox_resources.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='ajena'):
        sandbox_resources.cleanup_sandbox('agentia-verify-probe', 's', 'expected')
    assert not any(command[1] == 'rm' for command in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize('interruption', ['cancel', 'timeout', 'cleanup_failure'])
async def test_runner_interrupts_reaps_and_checks_temporary_container(runtime, monkeypatch, interruption):
    event = threading.Event()
    argv = []
    class Stream:
        async def readline(self):
            await asyncio.sleep(10)
            return b''
    class Process:
        returncode = None
        stdout = Stream(); stderr = Stream()
        def __init__(self): self.done = asyncio.Event(); self.killed = False
        async def wait(self): await self.done.wait(); return self.returncode
        def kill(self): self.killed = True; self.returncode = 137; self.done.set()
    process = Process()
    async def spawn(*command, **kwargs):
        argv.extend(command)
        if interruption != 'timeout': event.set()
        return process
    cleanup = Mock(return_value=True)
    if interruption == 'cleanup_failure':
        cleanup.side_effect = RuntimeError('daemon unreachable')
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawn)
    monkeypatch.setattr(sandbox_resources, 'cleanup_sandbox', cleanup)
    result = await run_docker_sandbox(str(runtime.ws), cancel_event=event, operation_id='specific-operation',
        session_id=runtime.id, timeout_seconds=0.05, mode=ExecutionMode.DOCKER)
    assert result.verification_interrupted and not result.is_success
    assert result.cleanup_confirmed is (interruption != 'cleanup_failure')
    if interruption == 'cleanup_failure':
        assert 'Limpieza no confirmada' in result.stderr
    assert process.killed and process.done.is_set()
    assert '--name' in argv and 'io.agentia.operation=specific-operation' in argv
    assert 'com.docker.compose.project=' + runtime.id in argv
    cleanup.assert_called_once_with(argv[argv.index('--name') + 1], runtime.id, 'specific-operation')


@pytest.mark.asyncio
async def test_direct_sandbox_source_only_never_checks_daemon_or_spawns(runtime, monkeypatch):
    check = Mock(side_effect=AssertionError('Docker in sources'))
    monkeypatch.setattr(docker_service, 'check_docker_daemon', check)
    result = await run_docker_sandbox(str(runtime.ws), mode=ExecutionMode.SOURCE_ONLY)
    assert result.verification_skipped and result.fallback_used
    check.assert_not_called()


def test_manual_verification_records_interruption_and_releases_outer_lock(runtime, monkeypatch):
    from app.services import session_execution, security_service
    (runtime.ws / 'src').mkdir(exist_ok=True)
    (runtime.ws / 'src/Example.java').write_text('class Example {}')
    monkeypatch.setattr(security_service, 'audit_workspace', lambda *args:
        SimpleNamespace(qualityGate=SimpleNamespace(canExport=True)))
    def cancel(path, callback):
        row = docker_service._active_deployments[runtime.id]
        local_operations.request_cancel(runtime.id, row.operationId)
        return DockerExecutionResult(exit_code=-1, fallback_used=True, verification_interrupted=True,
            fallback_reason='Cancelada', stderr='Cancelada. Limpieza no confirmada: daemon unreachable')
    monkeypatch.setattr(workspace_verification, '_run_sandbox_blocking', cancel)
    response = session_execution.verify_existing_sources(runtime.id)
    assert response['status'] == 'PAUSED' and response['metrics']['verificationInterrupted']
    assert not real_tests_passed(response['metrics'])
    assert not docker_service._operation_locks[runtime.id].locked()
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, runtime.id)
        assert 'Limpieza no confirmada' in row.error_message
