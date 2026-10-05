import json
import subprocess
import sys
import threading
from types import SimpleNamespace
import pytest
from app.config import settings
from app.services import docker_service as service, runtime_log_capture as capture
from app.services.logged_process import run_logged


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path))
    monkeypatch.setattr(service, '_raw_log_history', {})
    monkeypatch.setattr(capture, 'execution_mode', lambda _: SimpleNamespace(value='DOCKER'))
    containers = [{'Id': 'app-id', 'Config': {'Labels': {'com.docker.compose.project': 'session',
        'io.agentia.role': 'application'}}, 'State': {'Running': True}},
        {'Id': 'db-id', 'Config': {'Labels': {'com.docker.compose.project': 'session',
        'io.agentia.role': 'database'}}, 'State': {'Running': True}},
        {'Id': 'foreign', 'Config': {'Labels': {'com.docker.compose.project': 'other',
        'io.agentia.role': 'application'}}, 'State': {'Running': True}}]
    data = SimpleNamespace(containers=containers, lines={'app-id': '', 'db-id': ''}, commands=[])
    def run(command, **kwargs):
        data.commands.append(command)
        output = 'app-id db-id foreign' if command[1] == 'ps' else (
            json.dumps(containers) if command[1] == 'inspect' else data.lines[command[-1]])
        return SimpleNamespace(returncode=0, stdout=output, stderr='')
    monkeypatch.setattr(capture.subprocess, 'run', run)
    def logged(command, on_line, **kwargs):
        result = run(command, **kwargs)
        for line in result.stdout.splitlines(): on_line(line)
    monkeypatch.setattr(capture, 'run_logged', logged)
    return data


def test_capture_is_owned_redacted_atomic_and_restart_deduplicated(fixture):
    stamp = '2026-10-04T22:00:00.000000001Z'
    fixture.lines['app-id'] = f'{stamp} token=private-value\n{stamp} repeated\n{stamp} repeated\n'
    fixture.lines['db-id'] = f'{stamp} password=database-secret\n'
    assert capture.capture_once('session')
    snapshot = service._deployment_log_snapshot('session')
    assert len(snapshot['entries']) == 4
    assert {e['source'] for e in snapshot['entries']} == {'application', 'database'}
    assert all(e['timestamp'] == stamp for e in snapshot['entries'])
    assert 'private-value' not in json.dumps(snapshot) and 'database-secret' not in json.dumps(snapshot)
    assert all(command[-1] != 'foreign' for command in fixture.commands if command[1] == 'logs')
    service._raw_log_history.clear()
    capture.capture_once('session')
    assert service._deployment_log_snapshot('session')['nextId'] == 5
    fixture.lines['app-id'] += f'{stamp} repeated\n'
    capture.capture_once('session')
    assert service._deployment_log_snapshot('session')['nextId'] == 6
    assert '--since' in fixture.commands[-2]


def test_stopped_containers_capture_final_logs_and_return_false(fixture):
    for container in fixture.containers: container['State']['Running'] = False
    fixture.lines['db-id'] = '2026-10-04T22:00:00.1Z shutdown\n'
    assert not capture.capture_once('session')
    assert service.get_deployment_logs('session') == ['[2026-10-04T22:00:00.100000000Z] [database] shutdown']


def test_failed_atomic_commit_keeps_checkpoint_and_retries_messages(fixture, monkeypatch):
    from pathlib import Path
    fixture.lines['app-id'] = '2026-10-04T22:00:00.1Z pending\n'
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'replace', lambda *_: (_ for _ in ()).throw(PermissionError('locked')))
        with pytest.raises(PermissionError): capture.capture_once('session')
    assert service._deployment_log_snapshot('session')['nextId'] == 1
    capture.capture_once('session')
    assert service._deployment_log_snapshot('session')['nextId'] == 2


def test_retention_does_not_reset_checkpoint_or_sequence(fixture, monkeypatch):
    monkeypatch.setattr('app.services.deployment_logs.MAX_ENTRIES', 2)
    fixture.lines['app-id'] = ''.join(f'2026-10-04T22:00:0{i}.1Z line-{i}\n' for i in range(5))
    capture.capture_once('session')
    history = service._deployment_log_snapshot('session')
    assert [e['id'] for e in history['entries']] == [4, 5] and history['nextId'] == 6
    service._raw_log_history.clear()
    capture.capture_once('session')
    assert service._deployment_log_snapshot('session')['nextId'] == 6


def test_corrupt_checkpoint_is_rejected_without_overwrite(fixture):
    from app.services.local_runtime import record_directory
    path = record_directory('session') / 'logs.json'
    path.parent.mkdir(parents=True)
    original = json.dumps({'version': 1, 'nextId': 1, 'entries': [],
                          'collectors': {'app-id': {'timestamp': 'x', 'counts': []}}})
    path.write_text(original, encoding='utf-8')
    with pytest.raises(ValueError, match='Cursores'):
        capture.capture_once('session')
    assert path.read_text(encoding='utf-8') == original


def test_source_only_never_invokes_docker_or_starts_collector(fixture, monkeypatch):
    monkeypatch.setattr(capture, 'execution_mode', lambda _: SimpleNamespace(value='SOURCE_ONLY'))
    assert not capture.capture_once('session')
    capture.ensure_capture('session')
    assert not fixture.commands and 'session' not in capture._collectors


def test_one_collector_for_multiple_consumers_and_bounded_stop(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls = []
    monkeypatch.setattr(capture, 'execution_mode', lambda _: SimpleNamespace(value='DOCKER'))
    def once(identity):
        calls.append(identity); entered.set(); release.wait(3); return True
    monkeypatch.setattr(capture, 'capture_once', once)
    try:
        capture.ensure_capture('unique')
        assert entered.wait(2)
        capture.ensure_capture('unique')
        assert calls == ['unique']
        capture.stop_capture('unique')
    finally:
        release.set()
    # Wait for the worker to observe stop without an arbitrary sleep.
    with capture._lock:
        event = capture._collectors.get('unique')
        assert event is None or event.is_set()


def test_build_output_is_delivered_before_command_exit(tmp_path):
    observed = threading.Event()
    marker = tmp_path / 'release'
    errors = []
    def command():
        try:
            run_logged([sys.executable, '-u', '-c',
                'import time,pathlib;print("token=hidden",flush=True);'
                f'p=pathlib.Path({str(marker)!r});'
                '\nwhile not p.exists(): time.sleep(0.02)'],
                lambda line: observed.set(), timeout=5)
        except Exception as exc: errors.append(exc)
    worker = threading.Thread(target=command)
    worker.start()
    try:
        assert observed.wait(3)
        assert worker.is_alive(), 'Output must arrive while command is still running'
    finally:
        marker.touch(); worker.join(6)
    assert not worker.is_alive() and not errors


def test_logged_command_timeout_and_failure_are_bounded_and_secret_free():
    with pytest.raises(subprocess.TimeoutExpired):
        run_logged([sys.executable, '-c', 'import time;time.sleep(30)'], lambda _: None, timeout=0.1)
    with pytest.raises(RuntimeError) as failure:
        run_logged([sys.executable, '-c', 'print("password=secret-value");exit(2)'], lambda _: None)
    assert 'secret-value' not in str(failure.value) and '[REDACTED]' in str(failure.value)


def test_long_line_is_one_bounded_record_without_leaking_tail():
    lines = []
    run_logged([sys.executable, '-c', 'print("x"*50000);print("next")'], lines.append)
    assert len(lines) == 2 and len(lines[0]) < 8300 and lines[1] == 'next'
