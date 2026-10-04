"""Exercise actual persistence, rotation and independent SSE reconnect cursors."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.config import settings
from app.services import docker_service as service
from app.services import deployment_logs as logs
from app.api import routes_devops as routes


@pytest.fixture
def history(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path))
    monkeypatch.setattr(service, '_raw_log_history', {})
    def forbidden(*args, **kwargs):
        raise AssertionError('Log history must not invoke Docker or another process')
    monkeypatch.setattr(service.subprocess, 'run', forbidden)
    monkeypatch.setattr(service.time, 'sleep', lambda _: None)
    return tmp_path / 'session' / '.agentia-runtime'


def test_live_subscriber_continues_after_history_rotation(history, monkeypatch):
    monkeypatch.setattr(logs, 'MAX_ENTRIES', 3)
    for i in range(1, 4):
        service._log_message('session', str(i))
    stream = service.stream_logs('session')
    assert [next(stream).splitlines()[0] for _ in range(3)] == ['id: 1', 'id: 2', 'id: 3']
    assert next(stream) == ': keep-alive\n\n'
    service._log_message('session', 'four')
    assert next(stream) == 'id: 4\ndata: "four"\n\n'
    stream.close()
    assert service.get_deployment_logs('session') == ['2', '3', 'four']


def test_restart_keeps_ids_and_reconnect_does_not_duplicate(history):
    service._log_message('session', 'first')
    service._log_message('session', 'second')
    service._raw_log_history.clear()
    service._log_message('session', 'third')
    a, b = service.stream_logs('session', 2), service.stream_logs('session', 1)
    assert next(a) == 'id: 3\ndata: "third"\n\n'
    assert next(b) == 'id: 2\ndata: "second"\n\n'
    assert next(b) == 'id: 3\ndata: "third"\n\n'
    assert next(a) == ': keep-alive\n\n'
    a.close()
    b.close()


@pytest.mark.parametrize('cursor,reason', [(1, 'history_truncated'), (99, 'cursor_ahead')])
def test_unavailable_cursor_signals_reset_and_replays_retained_history(history, monkeypatch, cursor, reason):
    monkeypatch.setattr(logs, 'MAX_ENTRIES', 2)
    for i in range(1, 6):
        service._log_message('session', str(i))
    stream = service.stream_logs('session', cursor)
    reset = next(stream)
    assert reset.startswith('id: 3\nevent: log-reset\n') and reason in reset
    assert next(stream) == 'id: 4\ndata: "4"\n\n'
    assert next(stream) == 'id: 5\ndata: "5"\n\n'
    stream.close()


def test_concurrent_writes_commit_unique_ids_and_survive_reload(history):
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: service._log_message('session', f'line-{i}'), range(40)))
    service._raw_log_history.clear()
    snapshot = service._deployment_log_snapshot('session')
    assert [e['id'] for e in snapshot['entries']] == list(range(1, 41))
    assert len({e['message'] for e in snapshot['entries']}) == 40
    assert snapshot['nextId'] == 41


def test_failed_atomic_commit_does_not_replace_durable_history_or_advance_id(history, monkeypatch):
    service._log_message('session', 'committed')
    saved = (history / 'logs.json').read_bytes()
    original = Path.replace
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'replace', lambda *_: (_ for _ in ()).throw(PermissionError('locked file')))
        with pytest.raises(PermissionError):
            service._log_message('session', 'uncommitted')
    assert Path.replace is original
    assert (history / 'logs.json').read_bytes() == saved
    service._log_message('session', 'retry')
    assert service._deployment_log_snapshot('session')['entries'][-1] == {'id': 2, 'message': 'retry'}


def test_legacy_history_redacts_before_replay_and_converts_on_append(history):
    history.mkdir(parents=True)
    (history / 'logs.json').write_text(json.dumps(['password="two words" Bearer abc', 'jdbc:mysql://user:password@host/db']), encoding='utf-8')
    result = service.get_deployment_logs('session')
    assert result == ['password=[REDACTED] Bearer [REDACTED]', 'jdbc:mysql://[REDACTED]@host/db']
    service._log_message('session', 'new')
    assert json.loads((history / 'logs.json').read_text())['nextId'] == 4


def test_corrupt_history_is_not_silently_reset_or_overwritten(history):
    history.mkdir(parents=True)
    path = history / 'logs.json'
    path.write_text('{broken', encoding='utf-8')
    with pytest.raises(ValueError):
        service._log_message('session', 'new')
    assert path.read_text() == '{broken'


def test_new_messages_are_redacted_bounded_and_sse_escaped(history):
    service._log_message('session', '{"password": "two words", "token": "sensitive"}\nline')
    service._log_message('session', 'x' * 5000)
    disk = (history / 'logs.json').read_text()
    assert 'two words' not in disk and 'sensitive' not in disk
    assert len(service.get_deployment_logs('session')[1]) == 4000
    stream = service.stream_logs('session')
    frame = next(stream)
    assert frame.count('\n') == 3 and '\\nline' in frame
    stream.close()


def test_routes_validate_session_and_last_event_id_before_streaming(history, monkeypatch):
    def resolve(identity):
        if identity != 'session':
            raise HTTPException(404, 'Session not found')
        return history.parent, 'app'
    monkeypatch.setattr(routes, '_resolve_session_context', resolve)
    service._log_message('session', 'first')
    service._log_message('session', 'second')
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        response = client.get('/devops/session/logs/stream', headers={'Last-Event-ID': '1'})
        assert response.status_code == 200
        assert 'id: 1\n' not in response.text and 'id: 2\ndata: "second"' in response.text
        for cursor in ('-1', 'abc', '1.2', '9' * 21):
            assert client.get('/devops/session/logs/stream', headers={'Last-Event-ID': cursor}).status_code == 400
        assert client.get('/devops/missing/logs').status_code == 404
        assert client.get('/devops/missing/logs/stream').status_code == 404
