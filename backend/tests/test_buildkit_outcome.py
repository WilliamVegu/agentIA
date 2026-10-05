import json
import subprocess
import pytest
from app.services.buildkit_outcome import confirm_finished, run_build
from app.services.logged_process import CommandCancelled


def test_foreign_completed_record_cannot_confirm_our_cancel(monkeypatch):
    def command(args, **kwargs):
        content = json.dumps({'ref': 'builder/node/ref'}) if 'ls' in args else json.dumps({
            'Labels': [{'Name': 'io.agentia.operation', 'Value': 'foreign'}],
            'CompletedAt': 'now', 'Status': 'completed'})
        return subprocess.CompletedProcess(args, 0, content, '')
    monkeypatch.setattr('app.services.buildkit_outcome.subprocess.run', command)
    assert confirm_finished('own', timeout=.01)['confirmed'] is False


def test_exact_terminal_record_confirms_only_that_build(monkeypatch):
    def command(args, **kwargs):
        content = json.dumps({'ref': 'builder/node/ref'}) if 'ls' in args else json.dumps({
            'Labels': [{'Name': 'io.agentia.operation', 'Value': 'own'}],
            'CompletedAt': 'now', 'Status': 'canceled'})
        return subprocess.CompletedProcess(args, 0, content, '')
    monkeypatch.setattr('app.services.buildkit_outcome.subprocess.run', command)
    assert confirm_finished('own')['confirmed'] is True


def test_history_unavailable_does_not_fabricate_confirmation(monkeypatch):
    monkeypatch.setattr('app.services.buildkit_outcome.subprocess.run',
        lambda args, **kw: subprocess.CompletedProcess(args, 1, '', 'unsupported'))
    assert confirm_finished('own')['confirmed'] is False


def test_timeout_remains_interruption_with_observed_daemon_outcome(monkeypatch):
    monkeypatch.setattr('app.services.buildkit_outcome.confirm_finished', lambda _: {'confirmed': False})
    def runner(*args, **kwargs):
        raise subprocess.TimeoutExpired('build', 1)
    with pytest.raises(CommandCancelled, match='no se confirma'):
        run_build([], lambda _: None, operation_id='own', runner=runner)
