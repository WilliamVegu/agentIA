"""Evidence belongs to the inputs tested, not to files read after execution."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.devops import DeploymentStatus
from app.models.execution import VerificationOutcome
from app.models.session import GenerationSessionDB, SessionLocal, SessionStatus, SessionPhase
from app.sandbox.docker_runner import DockerExecutionResult
from app.services import workspace_verification as verification, docker_service
from app.services.verification_policy import workspace_fingerprint, verification_outcome, tests_really_passed as real_pass
from test_local_docker_runtime import runtime


def test_input_changed_during_verification_cannot_be_passed(runtime, monkeypatch):
    before = workspace_fingerprint(runtime.ws)
    def run(*args):
        (runtime.ws / 'src/main/java/Changed.java').write_text('class Changed {}')
        return DockerExecutionResult(exit_code=0, stdout='Tests run: 3, Failures: 0, Errors: 0, Skipped: 0')
    monkeypatch.setattr(verification, '_run_sandbox_blocking', run)
    outcome = verification.run_workspace_verification(str(runtime.ws))
    assert outcome.source_changed and not outcome.result.is_success
    assert outcome.workspace_fingerprint == before
    assert 'OUTDATED' in outcome.result.stderr
    metrics = {'totalTests': 3, 'passedTests': 3, 'failedTests': 0, 'allPassed': True,
               'fallback_used': False, 'verificationOutdated': True, 'workspaceFingerprint': before}
    assert not real_pass(metrics)
    row = SimpleNamespace(id=runtime.id, verification_metrics_json=json.dumps(metrics))
    assert verification_outcome(row) == VerificationOutcome.OUTDATED
    # Even restoring the previous files doesn't erase an observed mixed-input run.
    (runtime.ws / 'src/main/java/Changed.java').unlink()
    assert verification_outcome(row) == VerificationOutcome.OUTDATED


def test_output_reports_do_not_invalidate_input_evidence(runtime, monkeypatch):
    before = workspace_fingerprint(runtime.ws)
    def run(*args):
        reports = runtime.ws / 'target/surefire-reports'; reports.mkdir(parents=True)
        (reports / 'suite.xml').write_text('<testsuite tests="3" failures="0" errors="0" skipped="0"/>')
        return DockerExecutionResult(exit_code=0)
    monkeypatch.setattr(verification, '_run_sandbox_blocking', run)
    outcome = verification.run_workspace_verification(str(runtime.ws))
    assert outcome.result.is_success and not outcome.source_changed
    assert outcome.workspace_fingerprint == before


@pytest.mark.parametrize('when', ['queued', 'build'])
def test_deployment_never_starts_changed_inputs(runtime, monkeypatch, when):
    original = docker_service.run_logged
    def run(command, *args, **kwargs):
        result = original(command, *args, **kwargs)
        if 'build' in command:
            (runtime.ws / 'src/main/java/Late.java').write_text('class Late {}')
        return result
    if when == 'build':
        monkeypatch.setattr(docker_service, 'run_logged', run)
    row = docker_service.deploy_local(runtime.id, str(runtime.ws))
    if when == 'queued':
        (runtime.ws / 'src/main/java/Late.java').write_text('class Late {}')
    runtime.workers[0]()
    assert row.status == DeploymentStatus.FAILED
    assert 'fuentes/manifiestos cambiaron' in row.errorMessage
    assert not any('up' in command for command in runtime.commands)
    if when == 'queued':
        assert not any('build' in command for command in runtime.commands)
    assert not docker_service._operation_locks[runtime.id].locked()


def test_api_rechecks_evidence_after_late_asset_generation(runtime, monkeypatch):
    from app.api import routes_devops
    (runtime.ws / 'docker-compose.yml').unlink()
    metrics = {'totalTests': 3, 'passedTests': 3, 'failedTests': 0, 'allPassed': True,
               'fallback_used': False, 'workspaceFingerprint': workspace_fingerprint(runtime.ws)}
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, runtime.id)
        row.status, row.phase = SessionStatus.COMPLETED, SessionPhase.VERIFIED
        row.verification_metrics_json = json.dumps(metrics); db.commit()
    monkeypatch.setattr(routes_devops, 'audit_workspace', lambda *a: SimpleNamespace(qualityGate=SimpleNamespace(canExport=True)))
    def regenerate(*args):
        (runtime.ws / 'docker-compose.yml').write_text('services: {}')
    monkeypatch.setattr(routes_devops, 'generate_all_devops_assets', regenerate)
    with pytest.raises(HTTPException) as refused:
        asyncio.run(routes_devops.deploy_container(runtime.id))
    assert refused.value.status_code == 403
    assert not runtime.workers and not runtime.commands


def test_manual_verification_records_original_fingerprint(runtime, monkeypatch):
    from app.services import session_execution, security_service
    (runtime.ws / 'src/main/java/Example.java').write_text('class Example {}')
    monkeypatch.setattr(security_service, 'audit_workspace', lambda *a: SimpleNamespace(qualityGate=SimpleNamespace(canExport=True)))
    def run(*args):
        (runtime.ws / 'src/main/java/Example.java').write_text('class Example { int changed; }')
        return DockerExecutionResult(exit_code=0, stdout='Tests run: 3, Failures: 0, Errors: 0, Skipped: 0')
    monkeypatch.setattr(verification, '_run_sandbox_blocking', run)
    response = session_execution.verify_existing_sources(runtime.id)
    assert response['status'] == 'BLOCKED'
    metrics = response['metrics']
    assert metrics['verificationOutdated'] and not metrics['allPassed']
    assert metrics['workspaceFingerprint'] != workspace_fingerprint(runtime.ws)
    with SessionLocal() as db:
        assert verification_outcome(db.get(GenerationSessionDB, runtime.id)) == VerificationOutcome.OUTDATED
    assert not docker_service._operation_locks[runtime.id].locked()
