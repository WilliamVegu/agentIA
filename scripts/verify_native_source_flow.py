"""Opt-in native API acceptance: source generation/export without Docker or AI."""
import argparse
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
import uuid
import zipfile


def stop_process_tree(process):
    """Stop only the tree rooted at the Popen handle created by this probe."""
    if process.poll() is None:
        if os.name == 'nt':
            taskkill = Path(os.environ['SystemRoot']) / 'System32/taskkill.exe'
            result = subprocess.run([str(taskkill), '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=20)
            if result.returncode and process.poll() is None:
                raise RuntimeError('No se pudo detener el árbol propio del backend')
        else:
            process.terminate()
        try: process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)

INSTRUMENTATION = r'''
import json, os, pathlib, shutil, socket, subprocess
def forbidden(kind, value):
    with open(os.environ['NATIVE_FORBIDDEN_EVENTS'], 'a', encoding='utf-8') as output:
        output.write(json.dumps({'kind': kind, 'value': str(value)}) + '\n')
    raise RuntimeError('Forbidden native acceptance operation: ' + kind)
original_which = shutil.which
def which(command, *args, **kwargs):
    if pathlib.Path(str(command)).name.lower() in {'docker', 'docker.exe'}: forbidden('docker-discovery', command)
    return original_which(command, *args, **kwargs)
shutil.which = which
original_popen = subprocess.Popen
class GuardedPopen(original_popen):
    def __init__(self, args, *rest, **kwargs):
        executable = args[0] if isinstance(args, (list, tuple)) else str(args).split()[0]
        if pathlib.Path(str(executable)).name.lower() in {'docker', 'docker.exe'}: forbidden('docker-command', executable)
        super().__init__(args, *rest, **kwargs)
subprocess.Popen = GuardedPopen
import docker
def client(self, *args, **kwargs): forbidden('docker-sdk', 'DockerClient')
docker.DockerClient.__init__ = client
docker.APIClient.__init__ = client
original_resolve = socket.getaddrinfo
def resolve(host, *args, **kwargs):
    if host not in {None, '', 'localhost', '127.0.0.1', '::1', b'localhost', b'127.0.0.1', b'::1'}:
        forbidden('external-network', host)
    return original_resolve(host, *args, **kwargs)
socket.getaddrinfo = resolve
original_connect = socket.socket.connect
def connect(self, address):
    if isinstance(address, tuple) and address[0] not in {'localhost', '127.0.0.1', '::1'}:
        forbidden('external-network', address[0])
    return original_connect(self, address)
socket.socket.connect = connect
pathlib.Path(os.environ['NATIVE_GUARD_READY']).write_text(json.dumps({'pid': os.getpid(), 'parentPid': os.getppid(), 'active': True}), encoding='utf-8')
'''


def run(project, installation, destination, docker_enabled=True):
    project, installation, destination = project.resolve(), installation.resolve(), destination.resolve()
    if json.loads((installation / 'installation-result.json').read_text())['result'] != 'PASS':
        raise ValueError('Se requiere instalación nativa aprobada')
    if destination.exists():
        raise ValueError('Use una carpeta nueva para la aceptación')
    destination.mkdir(parents=True)
    instrumentation = destination / 'instrumentation'; instrumentation.mkdir()
    (instrumentation / 'sitecustomize.py').write_text(INSTRUMENTATION, encoding='utf-8')
    events = destination / 'forbidden-events.jsonl'
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
    environment = dict(os.environ, PATH='', PYTHONDONTWRITEBYTECODE='1', GIT_PYTHON_REFRESH='quiet',
        PYTHONPATH=os.pathsep.join([str(instrumentation), str(project / 'backend')]),
        DATABASE_URL='sqlite:///' + (destination / 'studio.sqlite').as_posix(),
        WORKSPACE_DIR=str(destination / 'workspaces'), SPECIFICATION_DIR=str(destination / 'specifications'),
        COST_STORE_PATH=str(destination / 'cost.sqlite'), DOCKER_ENABLED=str(docker_enabled).lower(),
        STUDIO_AUTO_LOGIN='true', LANGCHAIN_TRACING_V2='false', MLFLOW_TRACKING_URI='',
        NATIVE_FORBIDDEN_EVENTS=str(events), NATIVE_GUARD_READY=str(destination / 'guard-ready.json'),
        HTTP_PROXY='http://127.0.0.1:9', HTTPS_PROXY='http://127.0.0.1:9',
        GEMINI_API_KEY='', GOOGLE_API_KEY='', OPENAI_API_KEY='', GROQ_API_KEY='', ANTHROPIC_API_KEY='', DEEPSEEK_API_KEY='')
    import http.cookiejar
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    base = f'http://127.0.0.1:{port}/api/v1'
    def request(path, method='GET', payload=None, raw=False):
        headers = {'Content-Type': 'application/json', 'X-LLM-Provider': 'mock'}
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
        try:
            with opener.open(req, timeout=30) as response:
                body = response.read()
                return body if raw else json.loads(body)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'{method} {path}: {exc.code} {exc.read().decode()}') from exc
    processes, streams = [], []
    report = {'result': 'RUNNING', 'pathEmpty': True, 'dockerGloballyEnabled': docker_enabled,
              'externalNetworkGloballyBlocked': False, 'providerMode': 'DETERMINISTIC', 'backendPort': port}
    def start():
        output = (destination / f'backend-{len(processes)}.log').open('w', encoding='utf-8'); streams.append(output)
        process = subprocess.Popen([str(installation / 'venv/Scripts/python.exe'), '-B', '-m', 'uvicorn',
            'app.main:app', '--host', '127.0.0.1', '--port', str(port)], cwd=destination, env=environment,
            stdout=output, stderr=subprocess.STDOUT)
        processes.append(process)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if process.poll() is not None: raise RuntimeError('Backend terminó; consulte log')
            try:
                request('/auth/mvp', 'POST')
                guard = json.loads((destination / 'guard-ready.json').read_text())
                assert guard['active'] and process.pid in {guard['pid'], guard['parentPid']}, guard
                return process
            except OSError: time.sleep(.25)
        raise RuntimeError('Readiness agotado')
    def stop(process):
        stop_process_tree(process)
    try:
        process = start()
        spec = request('/specifications', 'POST', {'serviceName': 'native-lab-service', 'packageName': 'com.example.lab',
            'basePort': 8080, 'entities': [{'name': 'Item', 'tableName': 'items', 'attributes': [
                {'name': 'id', 'type': 'Long', 'isPrimaryKey': True}, {'name': 'name', 'type': 'String', 'nullable': False}]}],
            'userStories': [{'id': 'US-1', 'role': 'Operator', 'intent': 'create and read items',
                'benefit': 'maintain an inventory', 'scenarios': [{'scenarioId': 'AC-1',
                    'given': 'a valid item name', 'when': 'creating the item', 'then': 'return the persisted item'}]}]})
        created = request('/sessions', 'POST', {'specId': spec['specId'], 'executionMode': 'SOURCE_ONLY'})
        identity = created['sessionId']; report['sessionId'] = identity
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            detail = request('/sessions/' + identity)
            if detail['status'] in {'COMPLETED', 'BLOCKED', 'FAILED', 'CANCELLED', 'PAUSED'}: break
            time.sleep(.25)
        assert detail['status'] == 'COMPLETED', detail
        assert detail['executionMode'] == 'SOURCE_ONLY' and detail['verificationOutcome'] == 'SKIPPED_BY_CHOICE', detail
        assert detail['phase'] != 'VERIFIED'
        verified = request(f'/sessions/{identity}/verify', 'POST')
        assert verified['status'] == 'COMPLETED' and not verified['metrics']['allPassed'], verified
        request(f'/devops/{identity}/generate', 'POST', {})
        diagnostics = request(f'/devops/{identity}/diagnostics')
        assert not diagnostics['offlineVerified'] and diagnostics['checks'][0]['status'] == 'SKIPPED_BY_CHOICE'
        archive = request(f'/sessions/{identity}/export', raw=True)
        (destination / 'sources.zip').write_bytes(archive)
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            names = bundle.namelist(); delivery = json.loads(bundle.read('DELIVERY_STATUS.json'))
            assert delivery['verificationOutcome'] == 'SKIPPED_BY_CHOICE' and not delivery['includesImages']
            assert any('/src/test/' in '/' + name for name in names) and 'pom.xml' in names
        stop(process); start()
        recovered = request(f'/sessions/{identity}')
        assert recovered['executionMode'] == 'SOURCE_ONLY' and recovered['status'] == 'COMPLETED'
        assert recovered['verificationOutcome'] == 'SKIPPED_BY_CHOICE' and recovered['phase'] != 'VERIFIED'
        assert not events.exists() or not events.read_text().strip(), events.read_text() if events.exists() else ''
        report.update(result='PASS', generatedTests=True, executionSkipped=True, staticAuditAndExport=True,
            restartRecovered=True, guardActiveForBothStarts=True, forbiddenAttempts=0, localhost=base)
    except Exception as exc:
        report.update(result='FAILED', error=str(exc))
    finally:
        for process in processes: stop(process)
        for stream in streams: stream.close()
        report['processesStopped'] = all(p.poll() is not None for p in processes)
        report['forbiddenAttempts'] = len(events.read_text().splitlines()) if events.exists() else 0
        (destination / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--docker-disabled', action='store_true')
    args = parser.parse_args()
    result = run(args.project, args.installation, args.destination, not args.docker_disabled)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['result'] == 'PASS' else 1)
