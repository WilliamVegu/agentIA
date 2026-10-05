"""Fresh disposable Docker daemon with no external interface; host daemon untouched."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from scripts.local_microservice_fixture import create_fixture

ENGINE_IMAGE = 'docker:29.0.2-dind@sha256:d003717ad7a27d359dd2f5f6aa6ca691f5f58671e8d1ff0277d07e5635bb8332'


def verify(build='maven', engine='H2'):
    token = uuid.uuid4().hex
    root = Path('.run/clean-offline-engine').resolve() / token
    ws = root / 'sources'
    root.mkdir(parents=True)
    create_fixture(ws, build, engine, identity=token)
    name = 'agentia-offline-' + token
    volume = name + '-data'
    report = {'result': 'RUNNING', 'token': token, 'build': build, 'database': engine,
              'hostDaemonPruned': False, 'hostContextChanged': False,
              'externalNetworkGloballyBlocked': False}
    created = False
    volume_created = False
    sequence = 0
    def save():
        (root / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    def run(args, label, timeout=900):
        nonlocal sequence
        sequence += 1
        result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
        (root / (str(sequence).zfill(2) + '-' + label + '.log')).write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(label + ' failed: ' + result.stderr[-2000:])
        return result.stdout.strip()
    def docker(*args, label='docker', timeout=900):
        return run(['docker', *args], label, timeout)
    def inner(*args, label='inner', timeout=900):
        return docker('exec', name, 'docker', *args, label=label, timeout=timeout)
    try:
        # Preparation must have happened explicitly; never pull from this acceptance.
        metadata = json.loads(docker('image', 'inspect', ENGINE_IMAGE, label='prepared-engine'))[0]
        report['engineImageId'] = metadata['Id']
        shell = str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
        kit = root / 'kit'
        run([shell, '-NoProfile', '-File', str(ws / 'export-offline-kit.ps1'), '-Path', str(kit)], 'export-kit')
        manifest = json.loads((kit / 'manifest.json').read_text(encoding='utf-8-sig'))
        archive = kit / 'images.tar'
        value = hashlib.sha256()
        with archive.open('rb') as stream:
            while chunk := stream.read(1024 * 1024): value.update(chunk)
        assert value.hexdigest() == manifest['archive']['sha256']
        docker('volume', 'create', '--label', 'io.agentia.offline=' + token, volume, label='create-volume')
        volume_created = True
        docker('run', '-d', '--name', name, '--privileged', '--network', 'none', '--pull', 'never',
               '--label', 'io.agentia.offline=' + token, '-e', 'DOCKER_TLS_CERTDIR=',
               '--mount', 'type=volume,source=' + volume + ',target=/var/lib/docker', ENGINE_IMAGE, label='start-engine')
        created = True
        actual = json.loads(docker('inspect', name, label='engine-isolation'))[0]
        assert actual['HostConfig']['NetworkMode'] == 'none' and actual['Config']['Labels']['io.agentia.offline'] == token
        assert not actual['HostConfig']['PortBindings']
        deadline = time.monotonic() + 60
        while True:
            ready = subprocess.run(['docker', 'exec', name, 'docker', 'info', '--format', '{{json .}}'],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            if ready.returncode == 0:
                info = json.loads(ready.stdout); break
            if time.monotonic() > deadline: raise RuntimeError('Fresh daemon did not become ready')
            time.sleep(1)
        assert info['Images'] == 0 and info['Containers'] == 0
        report.update(initialImages=0, initialContainers=0, isolatedEngineNetwork='none',
                      storageDriver=info['Driver'], engineVersion=info['ServerVersion'])
        save()
        docker('cp', str(archive), name + ':/images.tar', label='transfer-images')
        docker('cp', str(ws), name + ':/workspace', label='transfer-sources')
        inner('load', '-i', '/images.tar', label='import-kit')
        for record in manifest['images']:
            imported = json.loads(inner('image', 'inspect', record['reference'], label='verify-image'))[0]
            assert imported['Id'] == record['id'], 'Imported image identity changed: ' + record['reference']
        inner('compose', 'version', label='compose-version')
        inner('compose', '-p', token, '-f', '/workspace/docker-compose.yml', 'build', '--pull=false', '--no-cache', label='cold-build')
        # Fixture H2 uses no secrets. Other engines need explicit, ephemeral inputs.
        import secrets
        credentials = ['-e', 'DB_PASSWORD=' + secrets.token_hex(20), '-e', 'DB_ROOT_PASSWORD=' + secrets.token_hex(20)] if engine != 'H2' else []
        def compose(*args, label):
            return docker('exec', *credentials, name, 'docker', 'compose', '-p', token,
                '-f', '/workspace/docker-compose.yml', *args, label=label)
        compose('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180', label='start-application')
        def wget(path, payload=None):
            args = ['exec', name, 'wget', '-q', '-O', '-', '--timeout=10']
            if payload is not None:
                args += ['--header=Content-Type: application/json', '--post-data=' + json.dumps(payload)]
            args += ['http://127.0.0.1:19080' + path]
            return json.loads(docker(*args, label='localhost-http'))
        assert wget('/actuator/health')['status'] == 'UP'
        item = wget('/api/v1/items', {'name': 'offline-cold'})
        assert item['name'] == 'offline-cold'
        compose('stop', label='stop-preserve')
        compose('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180', label='restart-offline')
        assert wget('/api/v1/items/' + str(item['id']))['name'] == 'offline-cold'
        build_log = next(root.glob('*-cold-build.log')).read_text(encoding='utf-8')
        assert ('BUILD SUCCESS' in build_log or 'BUILD SUCCESSFUL' in build_log), build_log[-2000:]
        report.update(result='PASS', importedKit=True, exactImageIds=True, coldBuildPassed=True,
                      health=True, createRead=True, persistence=True, noExternalInterface=True,
                      applicationImageRef=token + '-probe-service:local')
    except BaseException as exc:
        report.update(result='FAILED', cause=str(exc))
        raise
    finally:
        try:
            if created:
                actual = json.loads(docker('inspect', name, label='cleanup-ownership'))[0]
                if actual['Config']['Labels'].get('io.agentia.offline') != token:
                    raise ValueError('Foreign engine; cleanup refused')
                docker('logs', name, label='engine-logs')
                docker('rm', '-f', '-v', name, label='remove-engine')
            if volume_created:
                actual = json.loads(docker('volume', 'inspect', volume, label='volume-ownership'))[0]
                if actual['Labels'].get('io.agentia.offline') != token:
                    raise ValueError('Foreign volume; cleanup refused')
                docker('volume', 'rm', volume, label='remove-volume')
            report['cleanup'] = 'CONFIRMED'
        except Exception as exc:
            report.update(result='FAILED', cleanup='FAILED: ' + str(exc))
            raise
        finally: save()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', choices=['maven', 'gradle'], default='maven')
    parser.add_argument('--engine', choices=['H2', 'MYSQL', 'POSTGRESQL'], default='H2')
    args = parser.parse_args()
    print(json.dumps(verify(args.build, args.engine), indent=2))
