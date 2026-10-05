"""One isolated real API flow. Credential arrives on stdin and is never saved."""
import os
import sys
import json
import time
import uuid
import threading
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports' / ('docker-flow-' + time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
OUT.mkdir(parents=True)
console = sys.stdout
console.write('READY_FOR_CREDENTIAL\n'); console.flush()
import getpass
key = getpass.getpass('Credential (hidden): ', stream=console).strip()
if not key:
    raise SystemExit('Credential required on stdin')

class RedactedLog:
    def __init__(self):
        self.file = (OUT / 'execution.log').open('w', encoding='utf-8')
        self.lock = threading.Lock()
    def write(self, value):
        with self.lock:
            self.file.write(str(value).replace(key, '[REDACTED]'))
            self.file.flush()
    def flush(self):
        self.file.flush()
    def isatty(self):
        return False

log = RedactedLog()
sys.stdout = sys.stderr = log
os.environ.update(PYTHONPATH=str(ROOT / 'backend'), DATABASE_URL='sqlite:///' + (OUT / 'studio.db').as_posix(),
    WORKSPACE_DIR=str(OUT / 'workspaces'), SPECIFICATION_DIR=str(OUT / 'specifications'),
    COST_STORE_PATH=str(OUT / 'cost.db'), DOCKER_ENABLED='true', ALLOW_HERMETIC_FALLBACK='false',
    ALLOW_OFFLINE_MOCK='false', STUDIO_AUTO_LOGIN='true', LANGCHAIN_TRACING_V2='false', MLFLOW_TRACKING_URI='')
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app

report = {'result': 'RUNNING', 'flowCount': 1, 'provider': 'deepseek', 'database': 'POSTGRESQL',
          'startedAt': time.strftime('%Y-%m-%d %H:%M:%S'), 'steps': [], 'output': str(OUT)}
sid = None
started = time.monotonic()

def clean(value):
    return json.loads(json.dumps(value, default=str).replace(key, '[REDACTED]'))

def save():
    (OUT / 'result.json').write_text(json.dumps(clean(report), indent=2, ensure_ascii=False), encoding='utf-8')

def note(name, value=None):
    report['steps'].append({'name': name, 'seconds': round(time.monotonic()-started, 2), 'data': clean(value)})
    save()
    console.write(name + '\n'); console.flush()

with TestClient(app, base_url='http://localhost', client=('127.0.0.1', 50000), raise_server_exceptions=False) as client:
    def call(path, method='GET', payload=None, raw=False):
        response = client.request(method, '/api/v1' + path, json=payload, timeout=1000)
        if response.status_code >= 400:
            raise RuntimeError(f'{method} {path}: HTTP {response.status_code}: {response.text[:3000]}')
        return response.content if raw else response.json()

    def detail():
        return call('/sessions/' + sid)

    def wait_runtime(target, timeout=1500):
        deadline = time.monotonic() + timeout
        previous = None
        while time.monotonic() < deadline:
            value = call(f'/devops/{sid}/status')
            signature = (value['status'], value.get('operationPhase'))
            if signature != previous:
                note('Runtime ' + str(signature), value); previous = signature
            if value['status'] in target:
                return value
            if value['status'] in {'FAILED', 'DOCKER_UNAVAILABLE', 'INTERRUPTED', 'CANCELLED'}:
                raise RuntimeError('Runtime operation failed: ' + json.dumps(value))
            time.sleep(5)
        raise TimeoutError('Runtime operation deadline exceeded')

    def proxy(method, path, body=None):
        return call(f'/devops/{sid}/playground', 'POST', {'method': method, 'path': path, 'body': body})

    try:
        call('/auth/mvp', 'POST')
        note('Autenticación local real')
        prompt = '''Build a small Java 21 Spring Boot 3 REST microservice using Maven and PostgreSQL.
Service name flow-inventory-service, package com.example.flowinventory. Use one entity Item:
id Long generated identity, name String required and nonblank, quantity Integer required and minimum 0.
Provide CRUD at /api/v1/items: POST returns 201 with the persisted object and id, GET list and GET by id,
PUT updates name and quantity, DELETE returns 204. Return 404 when item does not exist; invalid input returns 400.
Use Controller, Service, Repository and JPA Entity layers, Java record request/response DTOs,
Jakarta validation and RestControllerAdvice. PostgreSQL-compatible SQL and no sample seed data.
Include meaningful Mockito unit tests and web validation tests. No external integrations, authentication,
messaging, Lombok, MapStruct, extra entities or modules. Maven single module, no Gradle.
Acceptance: create an item, read it, update quantity, preserve it after restart, delete it and reject blank name.'''
        created = call('/sessions/quick-start', 'POST', {'serviceName': 'flow-inventory-service',
            'rawText': prompt, 'databaseEngine': 'POSTGRESQL', 'executionMode': 'DOCKER',
            'autoRun': True, 'autoDeploy': True, 'apiKey': key, 'llmProvider': 'deepseek',
            'inputInterface': {'buildTool': 'maven', 'architecturePreference': 'layered'}})
        sid = created['sessionId']; report['sessionId'] = sid
        note('Única sesión creada; Auto-Pilot iniciado', created)
        deadline = time.monotonic() + 1800
        previous = None
        while time.monotonic() < deadline:
            value = detail()
            overview = call(f'/orchestrator/sessions/{sid}/overview')
            signature = (value['status'], value['phase'], overview.get('pipelineStatus'), overview.get('lifecycle', {}).get('currentPhase'))
            if signature != previous:
                note('Generación ' + str(signature), value); previous = signature
            if value['status'] in {'BLOCKED', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED'}:
                break
            time.sleep(5)
        else:
            raise TimeoutError('Generation deadline exceeded')
        report['generationTerminal'] = value
        if value['status'] == 'PAUSED' and value['verificationOutcome'] == 'ENVIRONMENT_UNAVAILABLE':
            # Normal initial setup for newly generated dependencies, same session;
            # no second generation, no replacement of failed generated sources.
            note('Preparación explícita de dependencias para la misma sesión', call(f'/devops/{sid}/prepare', 'POST'))
            wait_runtime({'IDLE'})
            verified = call(f'/sessions/{sid}/verify', 'POST')
            note('Verificación Docker del código generado', verified)
            if verified['status'] != 'COMPLETED' or not verified['metrics'].get('allPassed'):
                raise RuntimeError('Generated sources did not pass real Docker verification')
            note('Despliegue de snapshot verificado', call(f'/devops/{sid}/deploy', 'POST', {}))
        elif value['status'] != 'COMPLETED' or value['verificationOutcome'] != 'PASSED':
            raise RuntimeError('Generation/verification stopped: ' + json.dumps(value))
        runtime = wait_runtime({'HEALTHY'})
        report['runtime'] = runtime
        audit = call(f'/sessions/{sid}/audit')
        note('Auditoría de fuentes', audit['qualityGate'])
        assert audit['qualityGate']['canExport'], audit['qualityGate']
        smoke = call(f'/devops/{sid}/smoke-test', 'POST')
        note('Smoke test real', smoke)
        assert smoke['passed'], smoke
        resources = call(f'/devops/{sid}/playground/resources')
        note('Rutas REST descubiertas', resources)
        resource = '/api/v1/items'
        assert resource in resources['resources'], resources
        created_item = proxy('POST', resource, {'name': 'Flow proof item', 'quantity': 7})
        note('CRUD: crear', created_item)
        assert created_item['statusCode'] == 201, created_item
        item = created_item['body']; item_id = item['id']
        fetched = proxy('GET', f'{resource}/{item_id}')
        assert fetched['statusCode'] == 200 and fetched['body']['name'] == 'Flow proof item', fetched
        changed = proxy('PUT', f'{resource}/{item_id}', {'name': 'Flow proof item updated', 'quantity': 12})
        assert changed['statusCode'] == 200 and changed['body']['quantity'] == 12, changed
        rejected = proxy('POST', resource, {'name': '', 'quantity': -1})
        assert rejected['statusCode'] == 400, rejected
        note('CRUD: lectura, actualización y validación', {'read': fetched, 'update': changed, 'invalid': rejected})
        note('Parada preservando datos', call(f'/devops/{sid}/stop', 'POST'))
        note('Reinicio misma sesión', call(f'/devops/{sid}/restart', 'POST'))
        wait_runtime({'HEALTHY'})
        persisted = proxy('GET', f'{resource}/{item_id}')
        assert persisted['statusCode'] == 200 and persisted['body']['quantity'] == 12, persisted
        note('Persistencia tras reinicio confirmada', persisted)
        deleted = proxy('DELETE', f'{resource}/{item_id}')
        absent = proxy('GET', f'{resource}/{item_id}')
        assert deleted['statusCode'] == 204 and absent['statusCode'] == 404, (deleted, absent)
        note('CRUD: eliminar y comprobar 404', {'delete': deleted, 'absent': absent})
        for route, filename in [('export', 'sources.zip'), ('export-executable', 'executable.zip')]:
            content = call(f'/sessions/{sid}/{route}', raw=True)
            (OUT / filename).write_bytes(content)
            note('Exportación ' + filename, {'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
        report['finalSession'] = detail()
        report['result'] = 'PASS'
    except Exception as exc:
        report['result'] = 'FAILED'; report['error'] = str(exc)
        note('Flujo finalizado con fallo', {'type': type(exc).__name__, 'error': str(exc)})
    finally:
        if sid:
            try:
                report['finalSession'] = detail()
                logs = call(f'/devops/{sid}/logs')
                (OUT / 'docker-logs.json').write_text(json.dumps(clean(logs), indent=2, ensure_ascii=False), encoding='utf-8')
                current = call(f'/devops/{sid}/status')
                if current['status'] == 'BUILDING' and current.get('operationId'):
                    call(f'/devops/{sid}/cancel', 'POST', {'operationId': current['operationId']})
                    time.sleep(3)
                report['stop'] = call(f'/devops/{sid}/stop', 'POST')
            except Exception as exc:
                report['cleanupError'] = str(exc)
        report['elapsedSeconds'] = round(time.monotonic()-started, 2)
        save()
console.write(json.dumps(clean(report), ensure_ascii=False) + '\n'); console.flush()
raise SystemExit(0 if report['result'] == 'PASS' else 1)
