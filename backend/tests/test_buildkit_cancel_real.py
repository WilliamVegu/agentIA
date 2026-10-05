"""Prove daemon outcome for the exact build; never stop/prune a shared builder."""
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid
import pytest
from app.services.logged_process import run_logged, CommandCancelled
from app.services.buildkit_outcome import run_build

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1', reason='BuildKit real opt-in')


def test_cli_cancel_finishes_exact_daemon_build():
    token = uuid.uuid4().hex
    root = Path('.run/real-buildkit-cancel').resolve() / token
    root.mkdir(parents=True)
    (root / 'Dockerfile').write_text('FROM agentia-runtime:21-v1\nRUN --network=none echo AGENTIA_BEGIN && sleep 120 && echo AGENTIA_END\n', encoding='utf-8')
    cancel = threading.Event()
    log = []
    report = {'token': token, 'result': 'RUNNING', 'globalBuilderStopped': False, 'globalCachePruned': False}
    def line(text):
        log.append(text)
        if 'AGENTIA_BEGIN' in text and ('0.' in text or '1.' in text) and not 'RUN ' in text:
            cancel.set()
    try:
        with pytest.raises(CommandCancelled, match='BuildKit: el build exacto termino'):
            run_build(['docker', 'build', '--pull=false', '--network=none', '--no-cache',
                        '--label', 'io.agentia.operation=' + token, '-t', 'agentia-cancel:' + token, str(root)],
                       line, operation_id=token, runner=run_logged, timeout=180, cancel_event=cancel)
        deadline = time.monotonic() + 30
        record = None
        while time.monotonic() < deadline:
            result = subprocess.check_output(['docker', 'buildx', 'history', 'ls', '--format', 'json'], text=True, encoding='utf-8', timeout=10)
            candidates = [json.loads(v) for v in result.splitlines() if v.strip()]
            candidates = [v for v in candidates if token in v['name']]
            for candidate in candidates:
                builder, _, ref = candidate['ref'].split('/', 2)
                info = json.loads(subprocess.check_output(['docker', 'buildx', 'history', 'inspect', '--builder', builder,
                    ref, '--format', 'json'], text=True, encoding='utf-8', timeout=10))
                if {'Name': 'io.agentia.operation', 'Value': token} in info.get('Labels', []):
                    record = info
            if record and record.get('CompletedAt'):
                break
            time.sleep(.5)
        assert record and record.get('CompletedAt'), 'Exact daemon record did not finish'
        assert record['Status'] in {'canceled', 'cancelled', 'error'}, record
        assert not any('AGENTIA_END' in v and 'RUN ' not in v for v in log), log
        report.update(result='PASS', exactBuildRecord=record, cliCancelled=True, daemonBuildFinished=True)
    except BaseException as exc:
        report.update(result='FAILED', cause=str(exc))
        raise
    finally:
        (root / 'build.log').write_text('\n'.join(log), encoding='utf-8')
        (root / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
