import json
import subprocess
import sys
import yaml
import pytest
from app.services.local_kubernetes import manifests, validate_catalogue
from app.services.local_ci_assets import AUDIT_SCRIPT, github, gitlab


@pytest.mark.parametrize('engine', ['H2', 'MYSQL', 'POSTGRESQL'])
def test_topology_is_offline_and_persistent(engine):
    docs = manifests('orders', engine, 'agentia-session-orders:local')
    report = validate_catalogue(docs, engine)
    assert report['runtime'] == 'NOT_EXECUTED'
    app = yaml.safe_load(docs['deployment.yaml'])['spec']['template']['spec']
    assert app['containers'][0]['imagePullPolicy'] == 'Never'
    assert app['containers'][0]['startupProbe']
    assert app['volumes'][0]['persistentVolumeClaim']
    config = yaml.safe_load(docs['configmap.yaml'])['data']
    assert config['SPRING_JPA_HIBERNATE_DDL_AUTO'] == 'validate'
    assert 'SPRING_DATASOURCE_PASSWORD' not in config
    assert ('database.yaml' in docs) == (engine != 'H2')
    assert '.local' not in ''.join(docs.values())
    if engine != 'H2':
        assert '//orders-db:' in config['SPRING_DATASOURCE_URL']
        assert 'secretKeyRef' in docs['database.yaml']
        assert yaml.safe_load(docs['database-service.yaml'])['spec']['type'] == 'ClusterIP'


@pytest.mark.parametrize('mutation', ['wrong-pvc', 'wrong-probe', 'secret', 'pull', 'port'])
def test_invalid_catalogue_rejected(mutation):
    docs = manifests('orders', 'H2')
    value = yaml.safe_load(docs['deployment.yaml'])
    spec = value['spec']['template']['spec']
    if mutation == 'wrong-pvc':
        spec['volumes'][0]['persistentVolumeClaim']['claimName'] = 'foreign'
    elif mutation == 'wrong-probe':
        spec['containers'][0]['readinessProbe']['httpGet']['path'] = '/fake'
    elif mutation == 'secret':
        spec['containers'][0]['env'] = [{'name': 'DB_PASSWORD', 'value': 'actual-secret'}]
    elif mutation == 'pull':
        spec['containers'][0]['imagePullPolicy'] = 'Always'
    else:
        spec['containers'][0]['ports'][0]['containerPort'] = 9000
    docs['deployment.yaml'] = yaml.safe_dump(value)
    with pytest.raises(ValueError, match='Catalogo incompatible'):
        validate_catalogue(docs, 'H2')


def test_source_audit_runs_without_docker_and_fails_on_real_findings(tmp_path):
    script = tmp_path / 'local-ci.py'
    script.write_text(AUDIT_SCRIPT, encoding='utf-8')
    # If source mode accidentally invokes Docker, this executable causes the test to fail.
    env = {'PATH': '', 'SYSTEMROOT': __import__('os').environ.get('SYSTEMROOT', '')}
    result = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    output = tmp_path / '.agentia-runtime/local-ci-result.json'
    report = json.loads(output.read_text())
    assert report['tests'] == 'NOT_EXECUTED'
    assert report['staticAudit'] == 'PASSED'
    (tmp_path / 'Unsafe.java').write_text('new ProcessBuilder("cmd");', encoding='utf-8')
    result = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads(output.read_text())
    assert report['staticAudit'] == 'FAILED'
    assert report['findings'][0]['rule'] == 'PROCESS_EXECUTION'
    assert report['tests'] == 'NOT_EXECUTED'


def test_ci_yaml_manual_windows_no_remote_install():
    # BaseLoader keeps the YAML 1.2 workflow key 'on' as a string.
    gh = yaml.load(github('orders'), Loader=yaml.BaseLoader)
    gl = yaml.safe_load(gitlab('orders'))
    assert gh['on']['workflow_dispatch']['inputs']['docker']['default'] == 'false'
    assert gl['local-verification']['rules'][-1]['when'] == 'never'
    assert 'curl' not in github('orders') + gitlab('orders')
    assert 'actions/setup-java' not in github('orders')


def test_source_kubernetes_acceptance_never_uses_tools_or_docker(tmp_path, monkeypatch):
    from scripts.verify_local_kubernetes import verify
    monkeypatch.setattr('scripts.verify_local_kubernetes.subprocess.run',
        lambda *a, **kw: pytest.fail('SOURCE_ONLY invoked an external command'))
    result = verify(tmp_path, tmp_path / 'missing-tools', 'H2', sources_only=True)
    assert result['result'] == 'PASS' and result['runtime'] == 'NOT_EXECUTED'
    assert result['static']['status'] == 'PASSED'
