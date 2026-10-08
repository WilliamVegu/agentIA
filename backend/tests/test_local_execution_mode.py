"""Local lab acceptance: session choice, honest evidence and no Docker calls."""
import asyncio
import json
import uuid
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.config import settings
from app.models.execution import ExecutionMode
from app.models.session import GenerationSessionDB, SessionLocal, SessionStatus, SessionPhase
from app.api import routes_session
from app.services.execution_policy import execution_mode
from app.services.workspace_verification import run_workspace_verification
from app.services.verification_policy import session_allows_source_delivery, verification_outcome, workspace_fingerprint
from app.orchestrator.nodes.sandbox_node import sandbox_node
from app.services import docker_service


@pytest.fixture
def session_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "DOCKER_ENABLED", True)
    identity = str(uuid.uuid4())
    ws = tmp_path / identity
    (ws / "src/main/java").mkdir(parents=True)
    (ws / "pom.xml").write_text('<project><dependencies></dependencies></project>')
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id=identity, spec_id="fixture", spec_name="lab-service", status=SessionStatus.PAUSED))
        db.commit()
    yield identity, ws
    with SessionLocal() as db:
        db.query(GenerationSessionDB).filter_by(id=identity).delete()
        db.commit()


def forbid_docker(monkeypatch):
    forbidden = Mock(side_effect=AssertionError("SOURCE_ONLY called Docker"))
    monkeypatch.setattr("app.services.workspace_verification._run_sandbox_blocking", forbidden)
    monkeypatch.setattr(docker_service.subprocess, "run", forbidden)
    monkeypatch.setattr(docker_service.subprocess, "Popen", forbidden)
    return forbidden


def test_source_choice_survives_global_enablement_and_does_not_probe(session_workspace, monkeypatch):
    identity, ws = session_workspace
    forbidden = forbid_docker(monkeypatch)
    result = run_workspace_verification(str(ws)).result
    assert result.verification_skipped and not result.is_success
    assert execution_mode(identity) == ExecutionMode.SOURCE_ONLY
    assert docker_service.get_deployment_status(identity).status.value == "SKIPPED_BY_CHOICE"
    assert docker_service.deploy_local(identity, str(ws)).status.value == "SKIPPED_BY_CHOICE"
    assert docker_service.stop_deployment(identity, str(ws)).status.value == "SKIPPED_BY_CHOICE"
    assert not docker_service.run_smoke_test(identity).passed
    forbidden.assert_not_called()


def test_native_backend_health_does_not_require_docker_on_path(session_workspace, monkeypatch):
    from app.main import app
    forbidden = forbid_docker(monkeypatch)
    monkeypatch.setenv('PATH', '')
    with TestClient(app) as client:
        response = client.get('/healthz')
        assert response.status_code == 200
        assert response.json()['status'] == 'UP'
        assert response.json()['dockerEnabled'] is True
    forbidden.assert_not_called()


def test_diagnostics_endpoint_keeps_sources_optional_and_rejects_unknown_sessions(session_workspace, monkeypatch):
    from app.api import routes_devops
    identity, ws = session_workspace
    forbidden = forbid_docker(monkeypatch)
    app = FastAPI()
    app.include_router(routes_devops.router)
    with TestClient(app) as client:
        response = client.get(f'/devops/{identity}/diagnostics')
        assert response.status_code == 200
        assert response.json()['checks'][0]['status'] == 'SKIPPED_BY_CHOICE'
        assert not response.json()['offlineVerified']
        assert client.get('/devops/unknown-session/diagnostics').status_code == 404
    forbidden.assert_not_called()


def test_source_delivery_keeps_previous_execution_reports(session_workspace, monkeypatch):
    identity, ws = session_workspace
    forbidden = forbid_docker(monkeypatch)
    report = ws / 'target/surefire-reports/TEST-failed.xml'
    report.parent.mkdir(parents=True)
    report.write_text('<testsuite tests="3" failures="1" errors="0" skipped="0"/>')
    assert run_workspace_verification(str(ws)).result.verification_skipped
    assert report.is_file() and 'failures="1"' in report.read_text()
    forbidden.assert_not_called()


@pytest.mark.parametrize('relative', ['target/surefire-reports', 'model/target/surefire-reports', 'bootstrap/build/test-results/test'])
def test_cold_build_reads_newly_created_test_reports(session_workspace, monkeypatch, relative):
    from app.sandbox.docker_runner import DockerExecutionResult, parse_test_counts
    identity, ws = session_workspace
    def execute(path, callback):
        reports = Path(path) / relative
        reports.mkdir(parents=True)
        (reports / 'TEST-results.xml').write_text('<testsuite tests="3" failures="1" errors="0" skipped="0"/>')
        return DockerExecutionResult(exit_code=1, stdout='build completed with test failure')
    monkeypatch.setattr('app.services.workspace_verification._run_sandbox_blocking', execute)
    result = run_workspace_verification(str(ws), mode=ExecutionMode.DOCKER).result
    counts = parse_test_counts(result.stdout)
    assert counts.total == 3 and counts.passed == 2 and counts.failures == 1
    assert not result.is_success and not result.verification_skipped and not result.fallback_used


def test_docker_disabled_is_a_decision_not_a_source_fallback(session_workspace, monkeypatch):
    identity, ws = session_workspace
    monkeypatch.setattr(settings, "DOCKER_ENABLED", False)
    with SessionLocal() as db:
        db.get(GenerationSessionDB, identity).execution_mode = "DOCKER"
        db.commit()
    result = sandbox_node({"session_id": identity, "workspace_path": str(ws), "execution_mode": "DOCKER", "blueprint": {"serviceName": "lab-service"}})
    assert result["status"] == "PAUSED"
    assert not result["test_metrics"]["verificationSkipped"]
    assert result["test_metrics"]["verificationOutcome"] == "ENVIRONMENT_UNAVAILABLE"
    assert "Reintentar" in result["error"]


def test_mode_and_actions_are_persisted_and_api_validates_choice(session_workspace):
    identity, ws = session_workspace
    app = FastAPI()
    app.include_router(routes_session.router)
    with TestClient(app) as client:
        assert client.patch(f"/sessions/{identity}/execution-mode", json={"executionMode": "invalid"}).status_code == 422
        assert client.patch(f"/sessions/{identity}/execution-mode", json={"executionMode": "DOCKER"}).status_code == 200
        with SessionLocal() as db:
            row = db.get(GenerationSessionDB, identity)
            assert row.execution_mode == "DOCKER"
            row.verification_metrics_json = json.dumps({"allPassed": False, "fallback_used": True})
            db.commit()
        detail = client.get(f"/sessions/{identity}").json()
        assert detail["executionMode"] == "DOCKER"
        assert detail["availableActions"] == ["RETRY", "CONTINUE_WITHOUT_DOCKER"]


def test_source_delivery_requires_current_evidence(session_workspace):
    identity, ws = session_workspace
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, identity)
        row.status = SessionStatus.COMPLETED
        row.verification_metrics_json = json.dumps({"verificationSkipped": True, "allPassed": False, "fallback_used": True, "workspaceFingerprint": workspace_fingerprint(ws)})
        db.commit()
        assert session_allows_source_delivery(row)
        assert verification_outcome(row).value == "SKIPPED_BY_CHOICE"
        (ws / "src/main/java/App.java").write_text("class App {}")
        assert not session_allows_source_delivery(row)
        assert verification_outcome(row).value == "OUTDATED"


@pytest.mark.parametrize('relative', ['model/src/main/java/Product.java', 'bootstrap/src/main/resources/application.yml', 'docker-compose.yml'])
def test_nested_module_and_deployment_changes_invalidate_evidence(session_workspace, relative):
    from app.services.verification_policy import session_is_verified
    identity, ws = session_workspace
    file = ws / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text('original', encoding='utf-8')
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, identity)
        row.status, row.phase = SessionStatus.COMPLETED, SessionPhase.VERIFIED
        row.verification_metrics_json = json.dumps({'totalTests': 1, 'passedTests': 1, 'failedTests': 0, 'allPassed': True, 'fallback_used': False, 'workspaceFingerprint': workspace_fingerprint(ws)})
        db.commit()
        assert session_is_verified(row)
        file.write_text('modified', encoding='utf-8')
        assert not session_is_verified(row)
        assert verification_outcome(row).value == 'OUTDATED'


def test_explicit_source_delivery_keeps_actual_failures(session_workspace, monkeypatch):
    from app.services.session_execution import verify_existing_sources
    identity, ws = session_workspace
    (ws / 'src/main/java/App.java').write_text('class App {}')
    (ws / 'src/main/java/GlobalExceptionHandler.java').write_text('import org.springframework.web.bind.annotation.RestControllerAdvice;\n@RestControllerAdvice class GlobalExceptionHandler {}')
    previous = {'totalTests': 2, 'passedTests': 1, 'failedTests': 1, 'allPassed': False, 'fallback_used': False, 'workspaceFingerprint': workspace_fingerprint(ws)}
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, identity)
        row.status, row.phase = SessionStatus.BLOCKED, SessionPhase.FAILED
        row.verification_metrics_json = json.dumps(previous)
        row.error_message = 'A real assertion failed'
        db.commit()
    forbidden = forbid_docker(monkeypatch)
    assert verify_existing_sources(identity)['status'] == 'COMPLETED'
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, identity)
        metrics = json.loads(row.verification_metrics_json)
        assert metrics['failedTests'] == 1 and not metrics.get('verificationSkipped')
        assert metrics['previousError'] == 'A real assertion failed'
        assert verification_outcome(row).value == 'FAILED'
        assert session_allows_source_delivery(row)
        assert row.phase != SessionPhase.VERIFIED
    forbidden.assert_not_called()


@pytest.mark.parametrize("build_tool", ["maven", "gradle"])
@pytest.mark.parametrize("database", ["POSTGRESQL", "MYSQL", "H2"])
def test_generation_graph_finishes_without_docker_for_all_combinations(session_workspace, monkeypatch, build_tool, database):
    from app.orchestrator.graph import generation_graph
    identity, ws = session_workspace
    # The fixture's Maven POM is not generator output. Start with the same clean
    # build entry point as the AutoPilot cases below.
    (ws / 'pom.xml').unlink()
    forbidden = forbid_docker(monkeypatch)
    blueprint = {
        "serviceName": "lab-service", "packageName": "com.example.lab", "basePort": 8080,
        "databaseMode": database,
        "inputInterface": {"requestVolume": "low", "buildToolPreference": build_tool},
        "entities": [{"name": "Item", "tableName": "items", "attributes": [
            {"name": "id", "type": "Long", "isPrimaryKey": True, "nullable": False, "validationRules": []},
            {"name": "name", "type": "String", "nullable": False, "validationRules": ["@NotBlank"]},
        ]}], "userStories": [],
    }
    state = generation_graph.invoke({"session_id": identity, "blueprint": blueprint, "workspace_path": str(ws), "execution_mode": "SOURCE_ONLY", "generation_mode": "DETERMINISTIC", "logs": [], "generated_files": {}})
    assert state["status"] == "COMPLETED"
    assert state["test_metrics"]["verificationSkipped"]
    assert not state["test_metrics"]["allPassed"]
    assert state["test_metrics"]["totalTests"] == 0
    assert (ws / "docker-compose.yml").exists()
    assert (ws / ("build.gradle" if build_tool == "gradle" else "pom.xml")).exists()
    assert ("gradle --no-daemon --offline" if build_tool == "gradle" else "mvn -B -o") in (ws / "Dockerfile").read_text()
    assert any((ws / "src/test").rglob("*.java"))
    forbidden.assert_not_called()


@pytest.mark.parametrize('build_tool', ['maven', 'gradle'])
@pytest.mark.parametrize('database', ['POSTGRESQL', 'MYSQL', 'H2'])
def test_autopilot_and_export_finish_without_docker(session_workspace, monkeypatch, build_tool, database):
    import io
    import threading
    import zipfile
    from app.services import pipeline_runner as pipeline
    from app.models.orchestrator import LifecyclePhase, PipelineRunStatus
    from app.services.verification_policy import require_source_delivery
    from app.services.export_service import export_full_bundle
    identity, ws = session_workspace
    # Let the actual generator create the build; avoid mistaking a fixture pom for output.
    (ws / 'pom.xml').unlink()
    (ws / 'spec.md').write_text('# Feature Specification: lab-service\n\nGestionar productos de inventario de una tienda mediante una API REST con operaciones CRUD y validación de datos.', encoding='utf-8')
    with SessionLocal() as db:
        db.get(GenerationSessionDB, identity).database_engine = database
        db.commit()
    forbidden = forbid_docker(monkeypatch)
    pipeline._pause_events[identity] = threading.Event()
    pipeline._stop_events[identity] = threading.Event()
    monkeypatch.setattr(pipeline.time, 'sleep', lambda *args: None)
    pipeline._execute_pipeline_steps(identity, LifecyclePhase.DEVOPS_DEPLOY, stop_on_gate=True, auto_deploy=True, provider='mock', input_interface={'requestVolume': 'low', 'buildToolPreference': build_tool})
    assert pipeline.get_pipeline_status(identity) == PipelineRunStatus.COMPLETED
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, identity)
        assert row.status == SessionStatus.COMPLETED
        assert row.phase != SessionPhase.VERIFIED
        require_source_delivery(row)
        assert verification_outcome(row).value == 'SKIPPED_BY_CHOICE'
    (ws / '.env').write_text('DB_PASSWORD=private-test-value')
    (ws / '.agentia-runtime').mkdir(exist_ok=True)
    (ws / '.agentia-runtime/private.json').write_text('{}')
    archive = zipfile.ZipFile(io.BytesIO(export_full_bundle(str(ws))))
    assert '.env' not in archive.namelist()
    assert not any('.agentia-runtime/' in path for path in archive.namelist())
    assert 'start-local.ps1' in archive.namelist()
    assert 'VERIFICATION_STATUS.md' in archive.namelist()
    assert not any(path.endswith('.jar') for path in archive.namelist())
    assert (ws / ('build.gradle' if build_tool == 'gradle' else 'pom.xml')).is_file()
    forbidden.assert_not_called()
