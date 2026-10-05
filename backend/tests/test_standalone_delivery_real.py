from scripts.local_microservice_fixture import create_fixture
"""Standalone Windows build/start/reuse with prepared local Spring/H2 fixture."""
import json
import os
import socket
import subprocess
import uuid
from pathlib import Path
import pytest
import requests
from app.services.local_deployment_assets import builder_image
from app.services.runtime_lifecycle import owned_resources
from app.services.devops_service import generate_all_devops_assets
from app.services.asset_generation import TEMPLATE_VERSION

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1', reason='Docker real opt-in')


@pytest.mark.parametrize('seed', [False, True], ids=['basic', 'seeded'])
def test_standalone_build_start_occupied_port_reuse_data_and_cleanup(seed):
    identity = str(uuid.uuid4())
    ws = Path('.run/real-standalone-delivery', identity).resolve()
    ws.mkdir(parents=True)
    fixture = create_fixture(ws, identity=identity, seed=seed)
    assert json.loads((ws / 'ASSET_CONFIGURATION.json').read_text())['templateVersion'] == TEMPLATE_VERSION
    assert (ws / '.agentia-runtime/generated-assets.json').is_file()
    target = identity + '-probe-service:local'
    report = {'session': identity, 'result': 'RUNNING', 'builder': builder_image(ws)}
    def docker(*args):
        return subprocess.check_output(['docker', *args], cwd=ws, text=True, stderr=subprocess.STDOUT, timeout=40).strip()
    def script(name, *args):
        shell = r'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe'
        result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File', str(ws / name), *args],
                                cwd=ws, capture_output=True, text=True, timeout=300)
        (ws / (name + ('-reuse' if '-ReuseImage' in args else '') + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        assert result.returncode == 0, (result.stdout + result.stderr)[-5000:]
        return result.stdout
    occupied = socket.socket()
    try:
        report['builderId'] = docker('image', 'inspect', report['builder'], '--format', '{{.Id}}')
        occupied.bind(('127.0.0.1', 0)); port = occupied.getsockname()[1]; occupied.listen()
        if port > 65400: pytest.skip('Port too near upper limit')
        generate_all_devops_assets(str(ws), identity, 'probe-service', db_engine='H2', host_port=port)
        output = script('start-local.ps1')
        assert 'Readiness confirmada' in output and 'Puerto ocupado' in output
        apps = [c for c in owned_resources(identity) if c['Config']['Labels'].get('io.agentia.role') == 'application']
        assert len(apps) == 1 and apps[0]['State']['Running']
        assert apps[0]['Config']['User'] == '10001:10001'
        assert apps[0]['HostConfig']['PortBindings']['8080/tcp'][0]['HostIp'] == '127.0.0.1'
        actual_port = int(apps[0]['HostConfig']['PortBindings']['8080/tcp'][0]['HostPort'])
        assert actual_port != port
        assert requests.get(f'http://127.0.0.1:{actual_port}/actuator/health', timeout=5).json()['status'] == 'UP'
        payload = {'name': 'standalone-marker'}
        if seed:
            payload.update(amount=12.34, requestedAt='2026-10-04T12:00:00')
            rows = requests.get(f'http://127.0.0.1:{actual_port}/api/v1/items', timeout=5).json()
            assert len(rows) == 1 and rows[0]['name'] == 'Semilla'
        created = requests.post(f'http://127.0.0.1:{actual_port}/api/v1/items', json=payload, timeout=5)
        assert created.status_code == 201
        record_id = created.json()['id']
        if seed: assert record_id == 2
        base = f'http://127.0.0.1:{actual_port}'
        assert requests.post(base + '/api/v1/items', json={'name': ''}, timeout=5).status_code == 400
        updated = requests.put(base + f'/api/v1/items/{record_id}', json={**payload, 'name': 'updated-marker'}, timeout=5)
        assert updated.status_code == 200 and updated.json()['name'] == 'updated-marker'
        assert requests.put(base + f'/api/v1/items/{record_id}', json={'name': ''}, timeout=5).status_code == 400
        image_id = apps[0]['Image']
        script('stop-local.ps1')
        reused = script('start-local.ps1', '-Port', str(actual_port), '-ReuseImage')
        assert 'No se ejecutaron nuevas pruebas' in reused
        apps = [c for c in owned_resources(identity) if c['Config']['Labels'].get('io.agentia.role') == 'application']
        assert apps[0]['Image'] == image_id
        effective = int(apps[0]['HostConfig']['PortBindings']['8080/tcp'][0]['HostPort'])
        assert requests.get(f'http://127.0.0.1:{effective}/api/v1/items/{record_id}', timeout=5).json()['name'] == 'updated-marker'
        if seed:
            script('stop-local.ps1')
            script('start-local.ps1', '-Port', str(effective))
            apps = [c for c in owned_resources(identity) if c['Config']['Labels'].get('io.agentia.role') == 'application']
            effective = int(apps[0]['HostConfig']['PortBindings']['8080/tcp'][0]['HostPort'])
            rows = requests.get(f'http://127.0.0.1:{effective}/api/v1/items', timeout=5).json()
            assert len(rows) == 2 and sum(row['name'] == 'Semilla' for row in rows) == 1
            assert next(row for row in rows if row['id'] == record_id)['name'] == 'updated-marker'
            report.update(seedOnce=True, dataPreservedAfterRebuild=True, identityAdvanced=True)
        assert requests.delete(f'http://127.0.0.1:{effective}/api/v1/items/{record_id}', timeout=5).status_code == 204
        assert requests.get(f'http://127.0.0.1:{effective}/api/v1/items/{record_id}', timeout=5).status_code == 404
        assert docker('image', 'inspect', report['builder'], '--format', '{{.Id}}') == report['builderId']
        script('cleanup-local.ps1', '-DeleteData')
        assert all(not owned_resources(identity, kind) for kind in ('container', 'volume', 'network'))
        report.update(result='PASS', occupiedPortResolved=True, effectivePort=effective, offlineBuild=True,
                      readiness=True, reuseDidNotBuild=True, h2DataPreserved=True, builderUnchanged=True,
                      savedPortUsedWithoutParameter=True, fixtureCatalogVersion=fixture['catalogVersion'], crud=True, validation=True)
    except Exception as exc:
        report.update(result='FAILED', error=str(exc))
        raise
    finally:
        occupied.close()
        for kind in ('container', 'volume', 'network'):
            resources = owned_resources(identity, kind)
            if resources:
                ids = [r['Id'] if kind != 'volume' else r['Name'] for r in resources]
                docker(*(['rm', '-f'] if kind == 'container' else [kind, 'rm']), *ids)
            assert not owned_resources(identity, kind)
        # UUID tag is exclusive to this test; shared builder/runtime are preserved.
        subprocess.run(['docker', 'image', 'rm', target], capture_output=True, timeout=20, check=False)
        report['cleanup'] = 'CONFIRMED'
        (ws / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
