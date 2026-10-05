"""Opt-in real Docker probe: generated service, versioned SQL, CRUD and persistence.

Run from the repository with PYTHONPATH=backend and the backend Python environment.
Initial preparation uses the network. Only this probe's containers are stopped;
its volumes and reports are retained under .run/real-docker.
"""
import argparse
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
import requests
from scripts.local_microservice_fixture import create_fixture

parser = argparse.ArgumentParser()
parser.add_argument('--build', choices=['maven', 'gradle'], default='maven')
parser.add_argument('--database', choices=['H2', 'POSTGRESQL', 'MYSQL'], default='H2')
parser.add_argument('--seed', action='store_true')
parser.add_argument('--report', type=Path, help='Independent result path for parallel test runners')
options = parser.parse_args()
root = Path(__file__).resolve().parents[1] / '.run/real-docker'
root.mkdir(parents=True, exist_ok=True)
identity = 'agentia-probe-' + uuid.uuid4().hex[:10]
ws = root / identity
ws.mkdir()
report = {'project': identity, 'workspace': str(ws), 'build': options.build, 'database': options.database, 'steps': [], 'offlineGlobalVerified': False}
(root / 'latest.json').write_text(json.dumps(report), encoding='utf-8')
fixture = create_fixture(ws, options.build, options.database, seed=options.seed, identity=identity, host_port=19080)
report['fixtureCatalogVersion'] = fixture['catalogVersion']
report['sourceHashes'] = fixture['files']
# Ephemeral test credentials, never saved to the source tree/report or printed.
os.environ['DB_PASSWORD'] = uuid.uuid4().hex
os.environ['DB_ROOT_PASSWORD'] = uuid.uuid4().hex

def run(label, command, timeout=900):
    print(label, flush=True)
    with (ws / (label + '.log')).open('w', encoding='utf-8') as out:
        proc = subprocess.run(command, cwd=ws, stdout=out, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    report['steps'].append({'name': label, 'exitCode': proc.returncode})
    (root / 'latest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (ws / 'probe-result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if options.report:
        options.report.parent.mkdir(parents=True, exist_ok=True)
        options.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    if proc.returncode:
        raise RuntimeError(label + ' failed; inspect ' + str(ws / (label + '.log')))

shell = r'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe'
start_attempted = False
try:
    run('prepare', [shell, '-NoProfile', '-NonInteractive', '-File', str(ws / 'prepare-local.ps1')])
    start_attempted = True
    run('start', [shell, '-NoProfile', '-NonInteractive', '-File', str(ws / 'start-local.ps1'), '-Port', '19080'])
    port = subprocess.check_output(['docker', 'compose', '-p', identity, 'port', 'probe-service', '8080'], cwd=ws, text=True).strip()
    assert port.startswith('127.0.0.1:')
    # PowerShell child env changes do not propagate to this parent process.
    # Preserve the effective alternate port when restarting Compose directly.
    os.environ['HOST_PORT'] = port.rsplit(':', 1)[-1]
    base = 'http://' + port
    health = requests.get(base + '/actuator/health', timeout=5)
    assert health.status_code == 200 and health.json()['status'] == 'UP'
    payload = {'name': 'Docker real'}
    if options.seed:
        payload.update(amount=12.34, requestedAt='2026-10-04T12:00:00')
        seeds = requests.get(base + '/api/v1/items', timeout=5).json()
        assert len(seeds) == 1 and seeds[0]['name'] == 'Semilla', seeds
    created = requests.post(base + '/api/v1/items', json=payload, timeout=5)
    assert created.status_code == 201, created.text
    item = created.json()
    if options.seed:
        assert item['id'] == 2, item  # Identity must advance after the seeded row.
        assert item['amount'] == 12.34 and item['requestedAt'] == payload['requestedAt'], item
    read = requests.get(base + '/api/v1/items/' + str(item['id']), timeout=5)
    assert read.status_code == 200 and read.json()['name'] == 'Docker real'
    updated_payload = {**payload, 'name': 'Updated fixture'}
    updated = requests.put(base + '/api/v1/items/' + str(item['id']), json=updated_payload, timeout=5)
    assert updated.status_code == 200 and updated.json()['name'] == 'Updated fixture', updated.text
    payload['name'] = 'Updated fixture'
    invalid = requests.post(base + '/api/v1/items', json={'name': ''}, timeout=5)
    assert invalid.status_code == 400, invalid.text
    run('stop-preserve', [shell, '-NoProfile', '-NonInteractive', '-File', str(ws / 'stop-local.ps1')])
    run('restart-preserve', ['docker', 'compose', '-p', identity, 'up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180'])
    read = requests.get(base + '/api/v1/items/' + str(item['id']), timeout=5)
    assert read.status_code == 200 and read.json()['name'] == 'Updated fixture', read.text
    if options.seed:
        rows = requests.get(base + '/api/v1/items', timeout=5).json()
        assert len(rows) == 2 and sum(row['name'] == 'Semilla' for row in rows) == 1, rows
        run('migration-runtime-logs', ['docker', 'compose', '-p', identity, 'logs', '--no-color', '--tail', '200'])
        report.update(migrations=True, seedOnce=True, schemaTable='inventory_records')
    deleted = requests.delete(base + '/api/v1/items/' + str(item['id']), timeout=5)
    assert deleted.status_code == 204, deleted.text
    assert requests.get(base + '/api/v1/items/' + str(item['id']), timeout=5).status_code == 404
    report.update(result='PASS', localhost=base, crud=True, update=True, validation=True, persistence=True)
except Exception as exc:
    report.update(result='FAILED', error=str(exc))
    print(str(exc), flush=True)
finally:
    # Own project's containers only; retain its data volume and all pre-existing resources.
    if start_attempted:
        try:
            run('final-stop-preserve', ['docker', 'compose', '-p', identity, 'down'], 90)
        except Exception as exc:
            report.update(result='FAILED', cleanupError=str(exc))
    (root / 'latest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)
    (ws / 'probe-result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if options.report:
        options.report.parent.mkdir(parents=True, exist_ok=True)
        options.report.write_text(json.dumps(report, indent=2), encoding='utf-8')

if report.get('result') != 'PASS':
    raise SystemExit(1)
