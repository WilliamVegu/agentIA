"""Compile and exercise an actual generated Quarkus service with portable tools."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
tools = json.loads((ROOT / '.run/tools/paths.json').read_text())
workspace = ROOT / 'systems/quarkus/.run/java-validation/native-inventory'
workspace.mkdir(parents=True, exist_ok=True)
from app.orchestrator.stages.deterministic import scaffolder, domain, service, controller, test_synthesis
state = {'blueprint': {'serviceName': 'native-inventory', 'packageName': 'com.example.inventory',
    'basePort': 18123, 'databaseMode': 'H2', 'entities': [{'name': 'Item', 'tableName': 'items',
    'attributes': [{'name': 'id', 'type': 'UUID', 'isPrimaryKey': True},
                   {'name': 'sku', 'type': 'String', 'nullable': False, 'validationRules': ['@NotBlank']}]}],
    'userStories': []}, 'workspace_path': str(workspace), 'generated_files': {}, 'logs': []}
for stage in (scaffolder, domain, service, controller, test_synthesis):
    state.update(stage.emit(state))
env = os.environ.copy()
env['JAVA_HOME'] = tools['java_home']
env['PATH'] = str(Path(tools['java_home']) / 'bin') + os.pathsep + env['PATH']
env['MAVEN_OPTS'] = '-Djavax.net.ssl.trustStoreType=Windows-ROOT -Dfile.encoding=UTF-8'
out = ROOT / 'integration/validation'
with (out / 'quarkus-maven.log').open('w', encoding='utf-8') as log:
    result = subprocess.run([str(Path(tools['maven_home']) / 'bin/mvn.cmd'), '-B', '-ntp',
        '-Dmaven.repo.local=' + str(ROOT / '.run/m2'), 'verify'], cwd=workspace, env=env,
        stdout=log, stderr=subprocess.STDOUT)
print('Maven exit:', result.returncode, flush=True)
if result.returncode:
    raise SystemExit(result.returncode)
with socket.socket() as probe:
    probe.bind(('127.0.0.1', 18123))
checks = []
def request(path, method='GET', payload=None, expected=200):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request('http://127.0.0.1:18123' + path, data=data, method=method,
        headers={'Content-Type': 'application/json'})
    try:
        response = urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = response.read()
        checks.append({'method': method, 'path': path, 'status': response.status, 'expected': expected})
        assert response.status == expected, (path, response.status, body)
        return json.loads(body) if body and 'json' in response.headers.get('Content-Type', '') else body
with (out / 'quarkus-java-runtime.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen([str(Path(tools['java_home']) / 'bin/java.exe'),
        '-Dquarkus.http.host=127.0.0.1', '-jar', 'target/quarkus-app/quarkus-run.jar'], cwd=workspace, env=env,
        stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic() + 90
        while True:
            try:
                with socket.create_connection(('127.0.0.1', 18123), timeout=1):
                    break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Generated service did not start')
                time.sleep(.5)
        assert request('/q/health')['status'] == 'UP'
        created = request('/api/v1/items', 'POST', {'sku': 'AUDIT-001'}, 201)
        item_id = created['id']
        assert len(item_id) == 36
        assert request('/api/v1/items/' + item_id)['sku'] == 'AUDIT-001'
        request('/api/v1/items', 'POST', {'sku': ''}, 400)
        request('/api/v1/items/00000000-0000-0000-0000-000000000099', expected=404)
        request('/api/v1/items/' + item_id, 'DELETE', expected=204)
        request('/api/v1/items/' + item_id, expected=404)
        request('/q/openapi')
    finally:
        process.terminate()
        process.wait(timeout=15)
        (out / 'quarkus-java-smoke.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
print('Java runtime checks:', len(checks), flush=True)
