"""Real offline tests completed, then input mutation must invalidate approval."""
import json
import os
from pathlib import Path
import subprocess
import uuid

import pytest

from app.config import settings
from app.models.session import GenerationSessionDB, SessionLocal, SessionStatus
from app.services.workspace_verification import run_workspace_verification
from app.services.verification_policy import workspace_fingerprint
from app.sandbox.docker_runner import parse_test_counts
from scripts.local_microservice_fixture import create_fixture

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1', reason='Docker real opt-in')


def test_real_build_success_with_late_source_change_is_outdated(monkeypatch):
    identity = str(uuid.uuid4())
    root = Path('.run/real-input-integrity').resolve()
    ws = root / identity
    create_fixture(ws, identity=identity)
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(root))
    monkeypatch.setattr(settings, 'DOCKER_ENABLED', True)
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id=identity, spec_id='test', spec_name='probe-service',
            execution_mode='DOCKER', status=SessionStatus.PAUSED)); db.commit()
    lines, changed = [], []
    def log(line):
        lines.append(line)
        if 'BUILD SUCCESS' in line and not changed:
            (ws / 'src/main/java/com/example/probe/Late.java').write_text(
                'package com.example.probe; public class Late {}', encoding='utf-8')
            changed.append(True)
    outcome = run_workspace_verification(str(ws), log_callback=log)
    counts = parse_test_counts(outcome.result.stdout)
    (ws / 'sandbox.log').write_text('\n'.join(lines) + '\n' + outcome.result.stderr, encoding='utf-8')
    report = {'sourceChanged': outcome.source_changed, 'inputFingerprint': outcome.workspace_fingerprint,
              'currentFingerprint': workspace_fingerprint(ws), 'result': outcome.result.model_dump(),
              'tests': counts.total if counts else 0, 'offlineGlobalVerified': False}
    (ws / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    assert changed and counts and counts.total > 0 and counts.failures == counts.errors == 0, report
    assert outcome.source_changed and not outcome.result.is_success and not outcome.result.fallback_used, report
    assert outcome.workspace_fingerprint != workspace_fingerprint(ws)
    assert 'OUTDATED' in outcome.result.stderr
    containers = subprocess.check_output(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + identity],
                                         text=True, timeout=15).strip()
    assert not containers
