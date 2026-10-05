import json
import os
import subprocess
import uuid
import zipfile
from pathlib import Path
import pytest
import yaml
from app.services.build_layout import build_layout
from app.services.devops_service import generate_all_devops_assets
from app.services.local_deployment_assets import dockerfile


@pytest.mark.parametrize('manifest,tool', [('pom.xml', 'maven'), ('build.gradle', 'gradle'), ('build.gradle.kts', 'gradle')])
@pytest.mark.parametrize('directory', ['.', 'bootstrap'])
def test_assets_agree_on_actual_build_entry(tmp_path, manifest, tool, directory):
    base = tmp_path / directory
    base.mkdir(exist_ok=True)
    (base / manifest).write_text('<project><dependencies></dependencies></project>' if tool == 'maven' else 'plugins {}')
    generate_all_devops_assets(str(tmp_path), 'layout', db_engine='H2')
    config = json.loads((tmp_path / 'ASSET_CONFIGURATION.json').read_text())
    delivery = json.loads((tmp_path / 'LOCAL_DELIVERY.json').read_text())
    assert config['buildTool'] == delivery['buildTool'] == tool
    assert config['buildDirectory'] == directory
    assert ('WORKDIR /workspace/bootstrap' in (tmp_path / 'Dockerfile').read_text()) == (directory == 'bootstrap')
    assert ('cd bootstrap &&' in (tmp_path / 'Dockerfile.prepare').read_text()) == (directory == 'bootstrap')
    assert 'liquibase-core' in (base / manifest).read_text()
    assert 'com.h2database' in (base / manifest).read_text()


def test_gradle_settings_at_root_keep_reactor_entry(tmp_path):
    (tmp_path / 'bootstrap').mkdir()
    (tmp_path / 'bootstrap/build.gradle.kts').write_text('plugins {}')
    (tmp_path / 'settings.gradle.kts').write_text('include("bootstrap")')
    tool, directory, manifest = build_layout(tmp_path)
    assert (tool, directory, manifest.name) == ('gradle', '.', 'build.gradle.kts')


def test_ambiguous_build_rejected_before_publishing(tmp_path):
    (tmp_path / 'pom.xml').write_text('<project/>')
    (tmp_path / 'build.gradle').write_text('plugins {}')
    with pytest.raises(ValueError, match='ambigua'):
        generate_all_devops_assets(str(tmp_path), 'ambiguous', db_engine='H2')
    assert not (tmp_path / 'Dockerfile').exists()


@pytest.mark.parametrize('database', ['POSTGRESQL', 'MYSQL', 'H2'])
def test_compose_effective_structure_has_local_isolated_data(tmp_path, database):
    generate_all_devops_assets(str(tmp_path), 'compose', 'probe-service', db_engine=database, host_port=18080)
    manifest = yaml.safe_load((tmp_path / 'docker-compose.yml').read_text())
    app = manifest['services']['probe-service']
    assert app['ports'] == ['127.0.0.1:${HOST_PORT:-18080}:8080']
    assert app['volumes'] == ['appdata:/app/data']
    assert app['environment']['SPRING_JPA_HIBERNATE_DDL_AUTO'] == 'validate'
    assert manifest['services']['data-init']['network_mode'] == 'none'
    assert app['depends_on']['data-init']['condition'] == 'service_completed_successfully'
    if database == 'H2':
        assert 'db' not in manifest['services'] and 'dbdata' not in manifest['volumes']
    else:
        db = manifest['services']['db']
        assert 'ports' not in db and 'container_name' not in db
        assert app['depends_on']['db']['condition'] == 'service_healthy'
        assert '${DB_PASSWORD:?' in db['environment'].get('POSTGRES_PASSWORD', db['environment'].get('MYSQL_PASSWORD'))


@pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1', reason='Docker real opt-in')
@pytest.mark.parametrize('tool', ['maven', 'gradle'])
@pytest.mark.parametrize('scenario', ['single-with-space', 'multiple', 'missing', 'not-executable', 'corrupt'])
def test_real_jar_selection_uses_contents_and_rejects_ambiguous_output(tool, scenario):
    identity = uuid.uuid4().hex
    ws = Path('.run/real-jar-selection', identity).resolve()
    directory = ws / ('module with space/target' if tool == 'maven' else 'module with space/build/libs')
    directory.mkdir(parents=True)
    def archive(name, executable=True):
        with zipfile.ZipFile(directory / name, 'w') as jar:
            jar.writestr('BOOT-INF/classes/Probe.class', b'fixture')
            jar.writestr('META-INF/MANIFEST.MF', 'Manifest-Version: 1.0\r\nMain-Class: ' + ('org.springframework.boot.loader.launch.JarLauncher' if executable else 'example.PlainMain') + '\r\n')
    if scenario in {'single-with-space', 'multiple'}: archive('app with space.jar')
    if scenario == 'multiple': archive('another-app.jar')
    if scenario == 'not-executable': archive('plain.jar', False)
    if scenario == 'corrupt': (directory / 'broken.jar').write_bytes(b'not a zip')
    # Execute the literal generated RUN shell, including Docker line continuation folding.
    command = dockerfile(tool).split('RUN --network=none ')[2].split('\n\nFROM')[0].replace('\\\n', '')
    name = 'agentia-jar-probe-' + identity
    result = subprocess.run(['docker', 'run', '--rm', '--name', name, '--label', 'io.agentia.test=' + identity,
        '--pull', 'never', '--network', 'none', '-v', str(ws) + ':/workspace:ro', '-w', '/workspace',
        'agentia-builder:f3a47171af85acdfddd092dd', 'sh', '-c', command], capture_output=True, text=True, timeout=40)
    (ws / 'result.json').write_text(json.dumps({'tool': tool, 'scenario': scenario, 'exitCode': result.returncode,
        'stdout': result.stdout, 'stderr': result.stderr}, indent=2))
    assert (result.returncode == 0) == (scenario == 'single-with-space'), result.stdout + result.stderr
    if scenario != 'single-with-space': assert 'Expected exactly one' in result.stderr


@pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1', reason='Docker real opt-in')
@pytest.mark.parametrize('tool', ['maven', 'gradle'])
@pytest.mark.parametrize('database', ['POSTGRESQL', 'MYSQL', 'H2'])
def test_real_compose_resolves_session_ports_volumes_and_credentials(tool, database):
    identity = uuid.uuid4().hex
    ws = Path('.run/real-compose-config', identity).resolve()
    ws.mkdir(parents=True)
    (ws / ('pom.xml' if tool == 'maven' else 'build.gradle')).write_text('<project><dependencies></dependencies></project>' if tool == 'maven' else 'plugins {}')
    generate_all_devops_assets(str(ws), identity, 'probe-service', db_engine=database, host_port=18080)
    env = dict(os.environ, DB_PASSWORD='fixture-only', DB_ROOT_PASSWORD='fixture-only')
    env.pop('HOST_PORT', None)
    result = subprocess.run(['docker', 'compose', '-p', identity, 'config', '--format', 'json'],
        cwd=ws, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    resolved = json.loads(result.stdout)
    app = resolved['services']['probe-service']
    assert app['image'] == identity + '-probe-service:local'
    assert app['ports'][0]['host_ip'] == '127.0.0.1'
    assert str(app['ports'][0]['published']) == '18080'
    assert resolved['volumes']['appdata']['name'] == identity + '_appdata'
    if database != 'H2':
        assert not resolved['services']['db'].get('ports')
        assert resolved['volumes']['dbdata']['name'] == identity + '_dbdata'
        assert app['environment']['SPRING_DATASOURCE_PASSWORD'] == 'fixture-only'
    else: assert 'db' not in resolved['services']
    (ws / 'result.json').write_text(json.dumps({'result': 'PASS', 'tool': tool, 'database': database,
        'localhostOnly': True, 'sessionVolumes': True, 'execution': 'COMPOSE_CONFIG_ONLY'}, indent=2))
