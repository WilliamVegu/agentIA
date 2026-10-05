"""Prove the native acceptance guard records prohibited calls rather than silently missing them."""
import json
import os
import subprocess
import sys
import pytest
from test_native_source_flow_real import probe


@pytest.mark.parametrize('expression,kind', [
    ('import shutil; shutil.which("docker")', 'docker-discovery'),
    ('import docker; docker.DockerClient()', 'docker-sdk'),
    ('import socket; socket.getaddrinfo("example.invalid",443)', 'external-network')])
def test_prohibited_operation_is_recorded_and_rejected(tmp_path, expression, kind):
    (tmp_path / 'sitecustomize.py').write_text(probe.INSTRUMENTATION)
    events, ready = tmp_path / 'events.jsonl', tmp_path / 'ready.json'
    environment = dict(os.environ, PYTHONPATH=str(tmp_path), NATIVE_FORBIDDEN_EVENTS=str(events), NATIVE_GUARD_READY=str(ready))
    result = subprocess.run([sys.executable, '-B', '-c', expression], env=environment, capture_output=True, text=True, timeout=20)
    assert result.returncode != 0 and json.loads(ready.read_text())['active']
    assert json.loads(events.read_text().splitlines()[0])['kind'] == kind
