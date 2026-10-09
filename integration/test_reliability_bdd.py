"""Spanish acceptance scenarios against real isolated HTTP backend processes."""
import http.cookiejar
import io
import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
import zipfile

import pytest
from pytest_bdd import given, when, then, parsers, scenarios
from integration.reliability_smoke import ROOT, environment, python_for
from integration.reliability_fixtures import ledger_draft

scenarios('features/dual_studio_reliability.feature')
PROMPT = 'Como contable, quiero registrar asientos con correo válido e importe positivo para conservar el libro.'


class StudioHTTP:
    def __init__(self, studio, root):
        backend = ROOT / ('systems/quarkus/backend' if studio == 'quarkus' else 'backend')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = environment(root, backend)
        env.update(STUDIO_AUTO_LOGIN='true', DOCKER_ENABLED='false')
        self.base = f'http://127.0.0.1:{port}'
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.log = (root / 'backend.log').open('w', encoding='utf-8')
        self.process = subprocess.Popen([python_for(studio), '-m', 'uvicorn', 'app.main:app',
                                         '--host', '127.0.0.1', '--port', str(port)],
                                        cwd=backend.parent, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise AssertionError('Backend exited: ' + (root / 'backend.log').read_text())
                try:
                    if self.request('GET', '/healthz')[0] == 200:
                        break
                except urllib.error.URLError:
                    pass
                time.sleep(0.1)
            else:
                raise AssertionError('Backend readiness timed out')
            code, _, _ = self.request('POST', '/api/v1/auth/mvp', {})
            assert code == 200 or (studio == 'quarkus' and code == 404)
        except BaseException:
            self.close()
            raise

    def request(self, method, path, data=None):
        body = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(self.base + path, data=body, method=method,
                                        headers={'Content-Type': 'application/json'})
        try:
            response = self.opener.open(request, timeout=60)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read()
            content = json.loads(raw) if 'json' in response.headers.get('Content-Type', '') else raw
            return response.status, content, response.headers

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=15)
        self.log.close()


@pytest.fixture(scope='module')
def studios(tmp_path_factory):
    handles = {}
    yield handles, tmp_path_factory
    for handle in handles.values():
        handle.close()


@given(parsers.parse('un estudio "{studio}" aislado'), target_fixture='journey')
def isolated_backend(studio, studios):
    handles, factory = studios
    if studio not in handles:
        handles[studio] = StudioHTTP(studio, factory.mktemp('bdd-' + studio))
    return {'api': handles[studio]}


@given('una sesión nueva con requisitos contables')
def new_session(journey):
    code, data, _ = journey['api'].request('POST', '/api/v1/sessions/quick-start', {
        'serviceName': 'bdd-ledger-' + uuid.uuid4().hex[:8], 'prompt': PROMPT,
        'databaseEngine': 'H2', 'executionMode': 'SOURCE_ONLY', 'autoRun': False})
    assert code == 201, data
    journey['sid'] = data['sessionId']


@when('recupero los requisitos dos veces')
def reload_requirements(journey):
    path = '/api/v1/requirements/sessions/' + journey['sid']
    journey['reloads'] = [journey['api'].request('GET', path)[:2] for _ in range(2)]


@then('conservo el texto original sin inventar una revisión')
def initial_prompt(journey):
    first, second = journey['reloads']
    assert first == second and first[0] == 200
    assert PROMPT in first[1]['rawPrompt']
    assert first[1]['hasDraft'] is False and first[1]['revisionId'] is None


@given('una revisión contable aprobada')
def approved_draft(journey):
    path = '/api/v1/requirements/sessions/' + journey['sid']
    code, revision, _ = journey['api'].request('POST', path + '/save', ledger_draft())
    assert code == 200, revision
    code, data, _ = journey['api'].request('POST', path + '/approve?revisionId=' + revision['revisionId'])
    assert code == 200 and data['approvalStatus'] == 'APPROVED', data
    journey['revision'] = revision


@when('guardo un cambio y vuelvo a guardar desde la revisión anterior')
def stale_writer(journey):
    path = '/api/v1/requirements/sessions/' + journey['sid'] + '/save?expectedRevisionId=' + journey['revision']['revisionId']
    changed = ledger_draft()
    changed['basePort'] = 18089
    code, saved, _ = journey['api'].request('POST', path, changed)
    assert code == 200, saved
    journey['changed'] = saved
    journey['conflict'] = journey['api'].request('POST', path, ledger_draft())


@then('recibo conflicto y conservo el cambio vigente')
def conflict_preserves_revision(journey):
    assert journey['conflict'][0] == 409
    code, data, _ = journey['api'].request('GET', '/api/v1/requirements/sessions/' + journey['sid'])
    assert code == 200 and data['revisionId'] == journey['changed']['revisionId']
    assert data['draft']['basePort'] == 18089 and data['approvalStatus'] == 'DRAFT'


@when(parsers.parse('ejecuto la entrada "{entry}" usando el proveedor diagnóstico explícito'))
def run_delivery(journey, entry):
    targets = ['ARCHITECTURE', 'DATA_MODEL', 'COMPLETED'] if entry == 'guiado' else ['COMPLETED']
    for target in targets:
        code, data, _ = journey['api'].request('POST', '/api/v1/orchestrator/pipeline/run', {
            'sessionId': journey['sid'], 'targetPhase': target, 'provider': 'mock',
            'autoDeploy': entry == 'autopilot'})
        assert code == 202, data
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            code, operation, _ = journey['api'].request('GET', '/api/v1/orchestrator/sessions/' + journey['sid'] + '/lifecycle')
            assert code == 200, operation
            if operation['pipelineStatus'] != 'RUNNING':
                break
            time.sleep(0.1)
        else:
            raise AssertionError('Pipeline timed out')
        assert operation['pipelineStatus'] == 'COMPLETED', operation


@then('la sesión termina con verificación omitida por elección')
def delivery_outcome(journey):
    code, data, _ = journey['api'].request('GET', '/api/v1/sessions/' + journey['sid'])
    assert code == 200 and data['status'] == 'COMPLETED', data
    assert data['verificationOutcome'] == 'SKIPPED_BY_CHOICE'


@then('la revisión y el dominio contable permanecen completos')
def unchanged_domain(journey):
    code, data, _ = journey['api'].request('GET', '/api/v1/requirements/sessions/' + journey['sid'])
    assert code == 200 and data['revisionId'] == journey['revision']['revisionId']
    assert data['draft'] == journey['revision']['draft']


@then('puedo descargar un ZIP de las fuentes')
def download_sources(journey):
    for path in ['/api/v1/sessions/' + journey['sid'] + '/export',
                 '/api/v1/orchestrator/sessions/' + journey['sid'] + '/export-bundle']:
        code, raw, headers = journey['api'].request('GET', path)
        assert code == 200 and 'application/zip' in headers['Content-Type'], (path, code, raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
            names = bundle.namelist()
            assert any(name.endswith('.java') and 'LedgerEntry' in name for name in names)
            assert not any(name.endswith('.env') for name in names)
