"""Two concurrent containers have independent writable cache copies and a stable image base."""
import json
import os
from pathlib import Path
import subprocess
import uuid
import pytest
from scripts.local_microservice_fixture import create_fixture
from app.services.local_deployment_assets import builder_image
from app.services.gradle_compatibility import installed_gradle_guard

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1', reason='Docker real opt-in')


@pytest.mark.parametrize('tool', ['maven', 'gradle'])
def test_concurrent_private_caches_preserve_prepared_base(tool):
    identity = uuid.uuid4().hex
    ws = Path('.run/real-cache-isolation', identity).resolve()
    create_fixture(ws, build=tool)
    image = builder_image(ws)
    def docker(*args):
        return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.STDOUT, timeout=30).strip()
    names = ['agentia-cache-' + identity + '-a', 'agentia-cache-' + identity + '-b']
    processes = []
    report = {'result': 'RUNNING', 'buildTool': tool, 'image': image, 'scope': 'cache-copy isolation, no application build'}
    try:
        image_id = docker('image', 'inspect', image, '--format', '{{.Id}}')
        for index, name in enumerate(names):
            command = ("mkdir -p /tmp/private-cache && cp -R /opt/agentia-cache/. /tmp/private-cache/ && "
                f"echo {index} > /tmp/private-cache/own-marker && sleep 2 && "
                f"test $(cat /tmp/private-cache/own-marker) = {index} && "
                "test ! -e /opt/agentia-cache/own-marker && find /tmp/private-cache -name '*.jar' | grep -q . && " +
                ("export GRADLE_USER_HOME=/tmp/private-cache && " + installed_gradle_guard() if tool == 'gradle'
                 else "mvn -version | grep 'Apache Maven 3.9.9'") + " && echo ISOLATED_CACHE_PASS")
            processes.append(subprocess.Popen(['docker', 'run', '--rm', '--pull', 'never', '--network', 'none',
                '--name', name, '--label', 'io.agentia.cache-probe=' + identity, image_id, 'sh', '-c', command],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
        for index, process in enumerate(processes):
            output, _ = process.communicate(timeout=90)
            (ws / f'cache-{index}.log').write_text(output, encoding='utf-8')
            assert process.returncode == 0 and 'ISOLATED_CACHE_PASS' in output, output
        assert docker('image', 'inspect', image, '--format', '{{.Id}}') == image_id
        report.update(result='PASS', imageId=image_id, privateCopies=2, networkNone=True, versionConfirmed=True, baseUnchanged=True)
    except Exception as exc:
        report.update(result='FAILED', error=str(exc)); raise
    finally:
        for name in names:
            result = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                record = json.loads(result.stdout)[0]
                assert record['Config']['Labels']['io.agentia.cache-probe'] == identity
                docker('rm', '-f', record['Id'])
        for process in processes:
            if process.poll() is None: process.communicate(timeout=15)
        remaining = docker('ps', '-aq', '--filter', 'label=io.agentia.cache-probe=' + identity)
        assert not remaining
        report['cleanup'] = 'CONFIRMED'
        (ws / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
