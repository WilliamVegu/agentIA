"""Exercise the real offline Quarkus API, lifecycle and ZIP without deploying."""
import io
import json
from pathlib import Path
import time
from urllib.request import Request, build_opener, ProxyHandler
import zipfile

BASE = 'http://127.0.0.1:8001/api/v1'
HTTP = build_opener(ProxyHandler({}))
OUT = Path(__file__).resolve().parent / 'validation'
checks = []
def call(path, payload=None, expected=200):
    req = Request(BASE + path, data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Content-Type': 'application/json'})
    with HTTP.open(req, timeout=60) as response:
        assert response.status == expected, (path, response.status)
        body = response.read()
        return json.loads(body) if 'json' in response.headers.get('Content-Type', '') else body

session = call('/sessions/quick-start', {'serviceName': 'audit-inventory',
    'prompt': 'Inventory service for Item with id and sku, CRUD operations',
    'databaseEngine': 'H2', 'autoRun': False}, 201)['sessionId']
call('/orchestrator/pipeline/run', {'sessionId': session, 'autoDeploy': False}, 202)
deadline = time.monotonic() + 120
while True:
    detail = call('/sessions/' + session)
    if detail['status'] in ('COMPLETED', 'BLOCKED', 'CANCELLED'):
        break
    if time.monotonic() > deadline:
        raise RuntimeError('Pipeline timeout')
    time.sleep(.5)
assert detail['status'] == 'COMPLETED', detail
assert detail['phase'] != 'VERIFIED', detail
checks.append('Lifecycle completed without pretending Maven ran')
artifacts = call('/sessions/' + session + '/artifacts')
assert len(artifacts) >= 14
checks.append('Generated source and delivery artifacts listed')
archive = call('/orchestrator/sessions/' + session + '/export-bundle')
with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
    pom_name = next(name for name in bundle.namelist() if name.endswith('pom.xml'))
    pom = bundle.read(pom_name).decode()
    assert 'quarkus-bom' in pom and 'org.springframework' not in pom
    assert 'quarkus-jdbc-h2' in pom
    java = [bundle.read(name).decode() for name in bundle.namelist() if name.endswith('.java')]
    assert java and not any('org.springframework' in text for text in java)
    assert any('@QuarkusTest' in text for text in java)
checks.append('Downloaded ZIP contains native Quarkus and test sources')
metrics = call('/sessions/' + session + '/metrics')
assert metrics['totalTests'] == 0 and not metrics['allPassed'] and metrics['fallback_used']
checks.append('Unexecuted Java tests are reported as unverified')
result = {'sessionId': session, 'checks': checks, 'artifactCount': len(artifacts),
    'phase': detail['phase'], 'verification': metrics}
(OUT / 'quarkus-api-smoke.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2), flush=True)
