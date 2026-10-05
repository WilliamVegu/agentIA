"""Resume the existing generated session without another LLM call."""
import json
import os
from pathlib import Path
import sys
import time
import secrets

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/docker-flow-20261005-112428-ad8273'
SID = '4c849f7c-4240-4aa2-8dca-83ae9a4a837d'
os.environ.update(DATABASE_URL='sqlite:///' + (OUT / 'studio.db').as_posix(), WORKSPACE_DIR=str(OUT / 'workspaces'),
    SPECIFICATION_DIR=str(OUT / 'specifications'), COST_STORE_PATH=str(OUT / 'cost.db'),
    DOCKER_ENABLED='true', ALLOW_HERMETIC_FALLBACK='false', STUDIO_AUTO_LOGIN='true', MLFLOW_TRACKING_URI='')
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app

report = {'result': 'RUNNING', 'sessionId': SID, 'newGenerations': 0, 'steps': []}
credential_file = OUT / 'workspaces' / SID / '.env'
credential_created = False
start = time.monotonic()
def note(name, data):
    report['steps'].append({'name': name, 'data': data, 'seconds': round(time.monotonic()-start, 2)})
    (OUT / 'recovery-result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(name, flush=True)

with TestClient(app, base_url='http://localhost', client=('127.0.0.1', 50000), raise_server_exceptions=False) as client:
    def call(path, method='GET', body=None, raw=False):
        response = client.request(method, '/api/v1' + path, json=body)
        if response.status_code >= 400:
            raise RuntimeError(f'{path}: {response.status_code} {response.text[:2000]}')
        return response.content if raw else response.json()
    def wait(target):
        deadline = time.monotonic()+1500
        previous = None
        while time.monotonic() < deadline:
            row = call(f'/devops/{SID}/status')
            signature = (row['status'], row.get('operationPhase'))
            if signature != previous:
                note(str(signature), row); previous = signature
            if row['status'] in target:
                return row
            if row['status'] in {'FAILED', 'DOCKER_UNAVAILABLE', 'INTERRUPTED'}:
                raise RuntimeError(row.get('errorMessage') or str(row))
            time.sleep(5)
        raise TimeoutError('Operation deadline')
    def proxy(method, path, body=None):
        return call(f'/devops/{SID}/playground', 'POST', {'method': method, 'path': path, 'body': body})
    try:
        call('/auth/mvp', 'POST')
        existing = call('/sessions/' + SID)
        if existing['verificationOutcome'] != 'PASSED':
            note('Preparación de las fuentes originales normalizadas', call(f'/devops/{SID}/prepare', 'POST'))
            wait({'IDLE'})
            verified = call(f'/sessions/{SID}/verify', 'POST')
            note('Verificación real y sellado del snapshot', verified)
            assert verified['status'] == 'COMPLETED' and verified['metrics']['allPassed'], verified
            assert verified['metrics']['sourceSnapshotId'], verified
        else:
            note('Reutilización de verificación vigente; sin repetir tests', existing)
        if not credential_file.exists():
            with credential_file.open('x', encoding='utf-8') as output:
                output.write('DB_PASSWORD=' + secrets.token_urlsafe(32) + '\n')
            credential_created = True
            note('Credencial aleatoria de BD de prueba, fuera del snapshot', {'temporary': True})
        note('Despliegue del mismo snapshot', call(f'/devops/{SID}/deploy', 'POST', {}))
        wait({'HEALTHY'})
        smoke = call(f'/devops/{SID}/smoke-test', 'POST'); assert smoke['passed'], smoke
        note('Salud confirmada', smoke)
        resource='/api/v1/items'
        item=proxy('POST', resource, {'name':'Recovery item', 'quantity':7})
        assert item['statusCode']==201, item
        identifier=item['body']['id']
        fetched=proxy('GET', f'{resource}/{identifier}'); assert fetched['statusCode']==200, fetched
        updated=proxy('PUT', f'{resource}/{identifier}', {'name':'Recovery item updated', 'quantity':12})
        assert updated['statusCode']==200 and updated['body']['quantity']==12, updated
        invalid=proxy('POST', resource, {'name':'', 'quantity':-1}); assert invalid['statusCode']==400, invalid
        note('CRUD y validación', {'create':item,'read':fetched,'update':updated,'invalid':invalid})
        stopped=call(f'/devops/{SID}/stop','POST'); assert stopped['status']=='STOPPED', stopped
        call(f'/devops/{SID}/restart','POST'); wait({'HEALTHY'})
        persisted=proxy('GET',f'{resource}/{identifier}')
        assert persisted['statusCode']==200 and persisted['body']['quantity']==12, persisted
        note('Persistencia tras parada y reinicio', persisted)
        deleted=proxy('DELETE',f'{resource}/{identifier}'); assert deleted['statusCode']==204, deleted
        absent=proxy('GET',f'{resource}/{identifier}'); assert absent['statusCode']==404, absent
        note('Eliminación y 404', {'delete':deleted,'absent':absent})
        for endpoint, filename in [('export','recovered-sources.zip'),('export-executable','recovered-executable.zip')]:
            data=call(f'/sessions/{SID}/{endpoint}',raw=True)
            (OUT/filename).write_bytes(data); note('Exportación '+filename, {'bytes':len(data)})
        report['result']='PASS'
    except Exception as exc:
        report['result']='FAILED'; report['error']=str(exc)
        note('Fallo de recuperación',str(exc))
    finally:
        report['session']=call('/sessions/'+SID)
        report['stop']=call(f'/devops/{SID}/stop','POST')
        if credential_created:
            credential_file.unlink()
        report['elapsedSeconds']=round(time.monotonic()-start,2)
        (OUT/'recovery-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({'result':report['result'],'error':report.get('error'),'elapsedSeconds':report['elapsedSeconds']}),flush=True)
raise SystemExit(0 if report['result']=='PASS' else 1)
