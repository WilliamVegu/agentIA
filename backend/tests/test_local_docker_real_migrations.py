"""Explicit Windows/Docker acceptance; default test runs never execute the CLI.

Online preparation is allowed. This does not certify globally offline operation.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_SQL') != '1',
                                reason='Migraciones Docker reales opt-in; no necesarias en laboratorio')


@pytest.mark.parametrize('build', ['maven', 'gradle'])
@pytest.mark.parametrize('database', ['H2', 'POSTGRESQL', 'MYSQL'])
def test_generated_schema_seed_and_persistence(build, database, tmp_path):
    root = Path(__file__).resolve().parents[2]
    result = tmp_path / 'result.json'
    environment = dict(os.environ, PYTHONPATH=str(root / 'backend'), DATABASE_URL='sqlite://')
    completed = subprocess.run([sys.executable, str(root / 'scripts/verify_local_database.py'),
                                '--build', build, '--database', database, '--seed', '--report', str(result)],
                               cwd=root, env=environment, capture_output=True, text=True, timeout=1800)
    assert completed.returncode == 0, completed.stderr[-4000:]
    assert result.is_file(), completed.stdout[-4000:]
    report = json.loads(result.read_text(encoding='utf-8'))
    assert report['result'] == 'PASS', report
    assert report['migrations'] and report['seedOnce'] and report['persistence'] and report['crud']
    assert report['schemaTable'] == 'inventory_records'
    assert all(step['exitCode'] == 0 for step in report['steps'])
    assert report['steps'][-1]['name'] == 'final-stop-preserve'
