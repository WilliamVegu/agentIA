"""Opt-in Windows/Docker test: same service name, separate images, ports and data.

Requires the prepared Maven/H2 builder for this fixture and agentia-runtime:21-v1.
Set AGENTIA_RUN_REAL_DOCKER=1 explicitly; normal/laboratory test runs never probe Docker.
"""
import json
import os
import subprocess
import uuid
from pathlib import Path
import pytest
import requests
from app.orchestrator.stages.deterministic import scaffolder, domain, service, controller, test_synthesis
from app.services.devops_service import generate_all_devops_assets
from app.services.local_deployment_assets import builder_image

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1',
                                reason='Docker real opt-in; no necesario en laboratorio')


def test_same_service_name_keeps_images_ports_data_and_stop_isolated():
    root = Path('.run/real-isolation').resolve() / uuid.uuid4().hex[:10]
    root.mkdir(parents=True)
    shell = r'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe'
    report = {'result': 'RUNNING', 'projects': [], 'checks': [], 'offlineGlobalVerified': False}
    attempted = []

    def run(ws, label, command, environment=None):
        with (ws / (label + '.log')).open('w', encoding='utf-8') as output:
            completed = subprocess.run(command, cwd=ws, env=environment, stdout=output, stderr=subprocess.STDOUT,
                                       timeout=600, check=False)
        assert completed.returncode == 0, f'{label} failed: {ws / (label + ".log")}'

    def query(ws, *args):
        return subprocess.check_output(['docker', *args], cwd=ws, text=True, timeout=15).strip()

    def inspect(ws, identity):
        container = query(ws, 'compose', '-p', identity, 'ps', '-q', 'probe-service')
        metadata = json.loads(query(ws, 'inspect', container))[0]
        assert metadata['Config']['Labels']['com.docker.compose.project'] == identity
        assert metadata['Config']['User'] == '10001:10001'
        ports = metadata['HostConfig']['PortBindings']['8080/tcp']
        assert len(ports) == 1 and ports[0]['HostIp'] == '127.0.0.1'
        return metadata, 'http://127.0.0.1:' + ports[0]['HostPort']

    try:
        for suffix in ('a', 'b'):
            identity = 'agentia-isolation-' + root.name + '-' + suffix
            ws = root / identity
            ws.mkdir()
            blueprint = {'serviceName': 'probe-service', 'packageName': 'com.example.probe', 'basePort': 8080,
                         'databaseMode': 'H2', 'inputInterface': {'buildToolPreference': 'maven'},
                         'entities': [{'name': 'Item', 'tableName': 'items', 'attributes': [
                             {'name': 'id', 'type': 'Long', 'isPrimaryKey': True, 'nullable': False},
                             {'name': 'name', 'type': 'String', 'nullable': False}]}], 'userStories': []}
            state = {'blueprint': blueprint, 'workspace_path': str(ws), 'generated_files': {}, 'logs': []}
            for stage in (scaffolder, domain, service, controller, test_synthesis):
                state.update(stage.emit(state))
            marker = ws / 'src/main/resources/static/identity.txt'
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(identity, encoding='utf-8')
            generate_all_devops_assets(str(ws), identity, 'probe-service', db_engine='H2', host_port=19100)
            # Deliberately require preparation rather than pulling or warming implicitly.
            query(ws, 'image', 'inspect', builder_image(ws))
            query(ws, 'image', 'inspect', 'agentia-runtime:21-v1')
            resolved = json.loads(query(ws, 'compose', '-p', identity, 'config', '--format', 'json'))
            image = resolved['services']['probe-service']['image']
            assert image == identity + '-probe-service:local'
            attempted.append((ws, identity))
            run(ws, 'start', [shell, '-NoProfile', '-NonInteractive', '-File', str(ws / 'start-local.ps1'), '-Port', '19100'])
            metadata, base = inspect(ws, identity)
            assert requests.get(base + '/identity.txt', timeout=5).text == identity
            created = requests.post(base + '/api/v1/items', json={'name': suffix}, timeout=5)
            assert created.status_code == 201
            row = {'project': identity, 'workspace': str(ws), 'imageTag': image, 'imageId': metadata['Image'],
                   'containerId': metadata['Id'], 'localhost': base, 'recordId': created.json()['id']}
            report['projects'].append(row)
            if suffix == 'a':
                first = row
            else:
                assert base != first['localhost']
                assert 'ocupado; se usar' in (ws / 'start.log').read_text(encoding='utf-8', errors='replace')
                assert row['imageId'] != first['imageId']
                assert query(ws, 'image', 'inspect', first['imageTag'], '--format', '{{.Id}}') == first['imageId']
                assert requests.get(first['localhost'] + '/identity.txt', timeout=5).text == first['project']
                # Build B again with different contents; A's tag and running app must stay unchanged.
                marker.write_text(identity + '-rebuilt', encoding='utf-8')
                run(ws, 'rebuild', ['docker', 'compose', '-p', identity, 'build', '--pull=false', '--no-cache'])
                updated = query(ws, 'image', 'inspect', image, '--format', '{{.Id}}')
                assert updated != row['imageId']
                assert query(ws, 'image', 'inspect', first['imageTag'], '--format', '{{.Id}}') == first['imageId']
                row['rebuiltImageId'] = updated
        report['checks'].extend(['same_name_distinct_images', 'occupied_port_informed', 'rebuild_other_tag_unchanged'])
        second = report['projects'][1]
        ws_b, id_b = attempted[1]
        run(ws_b, 'stop-b', [shell, '-NoProfile', '-NonInteractive', '-File', str(ws_b / 'stop-local.ps1')])
        assert requests.get(first['localhost'] + '/identity.txt', timeout=5).text == first['project']
        assert requests.get(first['localhost'] + '/api/v1/items/' + str(first['recordId']), timeout=5).json()['name'] == 'a'
        run(ws_b, 'restart-b', ['docker', 'compose', '-p', id_b, 'up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180'],
            environment={**os.environ, 'HOST_PORT': second['localhost'].rsplit(':', 1)[1]})
        assert requests.get(second['localhost'] + '/identity.txt', timeout=5).text == id_b + '-rebuilt'
        assert requests.get(second['localhost'] + '/api/v1/items/' + str(second['recordId']), timeout=5).json()['name'] == 'b'
        assert len(requests.get(first['localhost'] + '/api/v1/items', timeout=5).json()) == 1
        assert len(requests.get(second['localhost'] + '/api/v1/items', timeout=5).json()) == 1
        report['checks'].extend(['stop_other_service_unchanged', 'restart_rebuilt_image', 'distinct_persistent_data'])
        report['result'] = 'PASS'
    except Exception as exc:
        report.update(result='FAILED', error=str(exc))
        raise
    finally:
        cleanup_failures = []
        for ws, identity in attempted:
            try:
                run(ws, 'final-stop', ['docker', 'compose', '-p', identity, 'down'])
            except Exception as exc:
                cleanup_failures.append(str(exc))
        report['cleanupErrors'] = cleanup_failures
        if cleanup_failures:
            report['result'] = 'FAILED'
        (root / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        assert not cleanup_failures, cleanup_failures
