"""Explicit follow-up probe on a stopped H2 project created by verify_local_database.

Exercises checksum rejection and a new version while retaining existing data.
Only accepts this repository's generated probe workspaces. Requires prepared images.
The added migration and its data remain available for inspection after the test.
"""
import argparse, json, os, subprocess
from pathlib import Path
import requests
from app.services.local_database_migrations import write_migrations

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--port', type=int, default=19200)
options = parser.parse_args()
ws = options.workspace.resolve()
probe_root = Path(__file__).resolve().parents[1] / '.run/real-docker'
if ws.parent != probe_root.resolve() or not ws.name.startswith('agentia-probe-'):
    parser.error('Use un proyecto aislado generado por verify_local_database.py.')
previous = json.loads((ws / 'probe-result.json').read_text(encoding='utf-8'))
if previous.get('database') != 'H2' or previous.get('result') != 'PASS' or not previous.get('seedOnce'):
    parser.error('Se requiere una prueba H2 con semillas completada correctamente.')
if not 1024 <= options.port <= 65535:
    parser.error('Puerto fuera de rango.')
project = ws.name
root = ws / 'src/main/resources/db/changelog'
initial = root / '001-schema.sql'
master = root / 'db.changelog-master.xml'
original_sql = initial.read_bytes()
original_master = master.read_bytes()
os.environ['HOST_PORT'] = str(options.port)
report = {'project': project, 'checks': [], 'result': 'RUNNING'}
active = subprocess.check_output(['docker', 'compose', '-p', project, 'ps', '-q'], cwd=ws, text=True).strip()
if active:
    parser.error('Detenga primero el proyecto de prueba; no se modifica un despliegue activo.')
if (root / '003-extra.sql').exists():
    parser.error('Este proyecto ya contiene la versión de prueba; use otro probe H2.')

def run(label, *args):
    with (ws / (label + '.log')).open('w', encoding='utf-8') as out:
        completed = subprocess.run(['docker', 'compose', '-p', project, *args], cwd=ws, stdout=out, stderr=subprocess.STDOUT, timeout=600)
    return completed.returncode

try:
    initial.write_text(original_sql.decode() + '\nCREATE TABLE changed_initial (id BIGINT);\n', encoding='utf-8')
    assert run('checksum-build', 'build', '--pull=false', '--no-cache') == 0
    assert run('checksum-start', 'up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '60') != 0
    logs = subprocess.check_output(['docker', 'compose', '-p', project, 'logs', '--no-color'], cwd=ws, text=True)
    (ws / 'checksum-runtime.log').write_text(logs, encoding='utf-8')
    assert 'ValidationFailedException' in logs and 'check sum' in logs.lower(), logs[-3000:]
    report['checks'].append('modified_initial_checksum_rejected')
    assert run('checksum-stop', 'down') == 0
    initial.write_bytes(original_sql)
    extra = root / '003-extra.sql'
    extra.write_text("INSERT INTO inventory_records(name,amount,requested_at) VALUES ('Nueva version',10.20,'2026-10-04 10:00:00');\n", encoding='utf-8')
    extension = '  <changeSet id="003-extra" author="user"><sqlFile path="003-extra.sql" relativeToChangelogFile="true"/></changeSet>\n'
    master.write_text(original_master.decode().replace('</databaseChangeLog>', extension + '</databaseChangeLog>'), encoding='utf-8')
    write_migrations(ws, 'H2')
    assert '003-extra' in master.read_text()
    assert run('version-build', 'build', '--pull=false', '--no-cache') == 0
    assert run('version-start', 'up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '120') == 0
    rows = requests.get(f'http://127.0.0.1:{options.port}/api/v1/items', timeout=5).json()
    assert sorted(row['name'] for row in rows) == ['Nueva version', 'Semilla'], rows
    assert run('version-stop', 'down') == 0
    assert run('version-restart', 'up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '120') == 0
    rows = requests.get(f'http://127.0.0.1:{options.port}/api/v1/items', timeout=5).json()
    assert sorted(row['name'] for row in rows) == ['Nueva version', 'Semilla'], rows
    report['checks'] += ['appended_version_applied', 'existing_data_preserved', 'both_seeds_once_after_restart']
    report['result'] = 'PASS'
except Exception as exc:
    report.update(result='FAILED', error=str(exc))
finally:
    initial.write_bytes(original_sql)
    report['cleanupExitCode'] = run('evolution-final-stop', 'down')
    if report['cleanupExitCode'] != 0:
        report['result'] = 'FAILED'
    (ws / 'evolution-result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
