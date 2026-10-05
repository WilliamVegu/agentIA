"""Opt-in kind acceptance, private kubeconfig/network and strict own-resource cleanup."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import uuid
import requests
from scripts.prepare_local_tools import validate, NODE_IMAGE
from scripts.local_microservice_fixture import create_fixture
from app.services.local_kubernetes import validate_catalogue
from app.services.local_deployment_assets import DATABASE_IMAGES


def verify(root, tools, engine='POSTGRESQL', build='maven', sources_only=False):
    token = uuid.uuid4().hex
    name = 'agentia-kube-' + token[:16]
    root = Path(root).resolve() / token
    ws = root / 'sources'
    root.mkdir(parents=True)
    create_fixture(ws, build, engine, identity=token)
    catalogue = {p.name: p.read_text(encoding='utf-8') for p in (ws / 'k8s').glob('*.yaml')}
    report = {'session': token, 'result': 'RUNNING', 'engine': engine, 'build': build,
              'static': validate_catalogue(catalogue, engine), 'runtime': 'NOT_EXECUTED',
              'externalNetworkGloballyBlocked': False}
    result_file = root / 'result.json'
    def save():
        result_file.write_text(json.dumps(report, indent=2), encoding='utf-8')
    save()
    if sources_only:
        report.update(result='PASS', cause='SOURCE_ONLY; no Docker, tools or cluster invoked')
        save()
        return report
    tools = Path(tools).resolve()
    manifest = validate(tools)
    if not manifest['kindNodeImageId']:
        raise ValueError('Prepared node image required')
    kind = str(tools / 'kind.exe')
    kubectl = str(tools / 'kubectl.exe')
    kubeconfig = root / 'kubeconfig.private'
    image = token + '-probe-service:local'
    net_created = False
    cluster_attempted = False
    image_id = None
    forward = None
    environment = dict(os.environ, KUBECONFIG=str(kubeconfig), KIND_EXPERIMENTAL_DOCKER_NETWORK=name)
    def run(command, label, *, input=None, timeout=300):
        result = subprocess.run(command, env=environment, input=input, text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=timeout)
        # Commands with credentials use stdin and their input is never logged.
        (root / (label + '.log')).write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(label + ' failed: ' + result.stderr[-1500:])
        return result.stdout
    def kube(*args, label='kubectl', input=None, timeout=300):
        return run([kubectl, '--kubeconfig', str(kubeconfig), *args], label, input=input, timeout=timeout)
    try:
        actual = json.loads(run(['docker', 'image', 'inspect', NODE_IMAGE], 'node-image'))[0]['Id']
        if actual != manifest['kindNodeImageId']:
            raise ValueError('Prepared kind image changed; refused before cluster creation')
        # kind's node entrypoint needs a default gateway for its iptables rules.
        # This own bridge isolates resource identities, but is not a network air gap.
        run(['docker', 'network', 'create', '--label', 'io.agentia.kube=' + token, name], 'create-network')
        net_created = True
        run(['docker', 'build', '--network=none', '--pull=false', '--label', 'io.agentia.kube=' + token,
             '-t', image, str(ws)], 'build-application', timeout=900)
        metadata = json.loads(run(['docker', 'image', 'inspect', image], 'app-image'))[0]
        image_id = metadata['Id']
        config = root / 'kind.yaml'
        config.write_text('kind: Cluster\napiVersion: kind.x-k8s.io/v1alpha4\nnetworking:\n  apiServerAddress: "127.0.0.1"\nnodes:\n  - role: control-plane\n', encoding='utf-8')
        cluster_attempted = True
        run([kind, 'create', 'cluster', '--name', name, '--image', NODE_IMAGE,
             '--config', str(config), '--kubeconfig', str(kubeconfig), '--wait', '180s', '--retain'], 'create-cluster', timeout=300)
        for index, tag in enumerate([image] + ([DATABASE_IMAGES[engine]] if engine != 'H2' else [])):
            image_archive = root / ('image-' + str(index) + '.tar')
            # Docker Desktop's containerd store may keep an incomplete multiarch index.
            # Export the exact Windows/WSL Linux architecture, rather than asking ctr
            # to load foreign-platform descriptors which were never downloaded.
            run(['docker', 'save', '--platform', 'linux/amd64', '-o', str(image_archive), tag],
                'export-image-' + str(index), timeout=300)
            run([kind, 'load', 'image-archive', '--name', name, str(image_archive)], 'load-image-' + str(index), timeout=300)
        if engine != 'H2':
            secret = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'probe-service-credentials'},
                      'type': 'Opaque', 'stringData': {'DB_PASSWORD': secrets.token_hex(20)}}
            if engine == 'MYSQL':
                secret['stringData']['DB_ROOT_PASSWORD'] = secrets.token_hex(20)
            kube('apply', '-f', '-', label='create-secret', input=json.dumps(secret))
        kube('apply', '-f', str(ws / 'k8s'), label='apply-manifests')
        if engine != 'H2':
            kube('rollout', 'status', 'statefulset/probe-service-db', '--timeout=240s', label='database-ready', timeout=270)
        kube('rollout', 'status', 'deployment/probe-service', '--timeout=240s', label='application-ready', timeout=270)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        forward_log = (root / 'port-forward.log').open('w', encoding='utf-8')
        forward = subprocess.Popen([kubectl, '--kubeconfig', str(kubeconfig), 'port-forward',
            '--address=127.0.0.1', 'service/probe-service-service', str(port) + ':8080'],
            env=environment, stdout=forward_log, stderr=subprocess.STDOUT)
        def wait_health():
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    response = requests.get(f'http://127.0.0.1:{port}/actuator/health', timeout=3)
                    if response.status_code == 200 and response.json()['status'] == 'UP':
                        return
                except requests.RequestException:
                    pass
                time.sleep(1)
            raise RuntimeError('localhost health did not become UP')
        wait_health()
        base = f'http://127.0.0.1:{port}/api/v1/items'
        created = requests.post(base, json={'name': 'kube-persistent'}, timeout=5)
        assert created.status_code == 201, created.text
        identifier = created.json()['id']
        updated = requests.put(base + '/' + str(identifier), json={'name': 'kube-updated'}, timeout=5)
        assert updated.status_code == 200, updated.text
        invalid = requests.post(base, json={'name': ''}, timeout=5)
        assert invalid.status_code == 400, invalid.text
        forward.terminate(); forward.wait(timeout=10); forward_log.close(); forward = None
        kube('delete', 'pods', '-l', 'app=probe-service', '--wait=true', label='restart-application')
        if engine != 'H2':
            kube('delete', 'pods', '-l', 'app=probe-service-db', '--wait=true', label='restart-database')
            kube('rollout', 'status', 'statefulset/probe-service-db', '--timeout=240s', label='database-recovered', timeout=270)
        kube('rollout', 'status', 'deployment/probe-service', '--timeout=240s', label='application-recovered', timeout=270)
        forward_log = (root / 'port-forward-recovered.log').open('w', encoding='utf-8')
        forward = subprocess.Popen([kubectl, '--kubeconfig', str(kubeconfig), 'port-forward',
            '--address=127.0.0.1', 'service/probe-service-service', str(port) + ':8080'],
            env=environment, stdout=forward_log, stderr=subprocess.STDOUT)
        wait_health()
        read = requests.get(base + '/' + str(identifier), timeout=5)
        assert read.status_code == 200 and read.json()['name'] == 'kube-updated', read.text
        deleted = requests.delete(base + '/' + str(identifier), timeout=5)
        assert deleted.status_code == 204, deleted.text
        report.update(result='PASS', runtime='PASSED', health=True, crud=True, persistence=True,
                      cluster=name, imageId=image_id, localhost=f'http://localhost:{port}',
                      nodeNetworkInternal=False, globalKubeconfigModified=False)
    except BaseException as exc:
        report.update(result='FAILED', runtime='FAILED', cause=str(exc))
        raise
    finally:
        try:
            if forward:
                forward.terminate(); forward.wait(timeout=10); forward_log.close()
            if cluster_attempted:
                nodes = run(['docker', 'ps', '-a', '-q', '--filter', 'label=io.x-k8s.kind.cluster=' + name], 'own-nodes').split()
                if nodes:
                    node_metadata = json.loads(run(['docker', 'inspect', *nodes], 'node-ownership'))
                    if any(n['Config']['Labels'].get('io.x-k8s.kind.cluster') != name for n in node_metadata):
                        raise ValueError('Foreign cluster identity; cleanup refused')
                    for index, node in enumerate(nodes):
                        run(['docker', 'logs', node], 'node-logs-' + str(index))
                    run([kind, 'delete', 'cluster', '--name', name, '--kubeconfig', str(kubeconfig)], 'delete-cluster')
                assert not run(['docker', 'ps', '-a', '-q', '--filter', 'label=io.x-k8s.kind.cluster=' + name], 'confirm-cluster').strip()
            if net_created:
                network = json.loads(run(['docker', 'network', 'inspect', name], 'network-ownership'))[0]
                if network['Labels'].get('io.agentia.kube') != token:
                    raise ValueError('Foreign network; cleanup refused')
                run(['docker', 'network', 'rm', name], 'delete-network')
            if image_id:
                metadata = json.loads(run(['docker', 'image', 'inspect', image_id], 'image-ownership'))[0]
                if metadata['Config']['Labels'].get('io.agentia.kube') != token:
                    raise ValueError('Foreign image; cleanup refused')
                run(['docker', 'image', 'rm', image_id], 'delete-image')
            report['cleanup'] = 'CONFIRMED'
        except Exception as exc:
            report['cleanup'] = 'FAILED: ' + str(exc)
            report['result'] = 'FAILED'
            raise
        finally:
            save()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tools', type=Path, default=Path('.run/local-tools-v3'))
    parser.add_argument('--engine', choices=['H2', 'POSTGRESQL', 'MYSQL'], default='POSTGRESQL')
    parser.add_argument('--build', choices=['maven', 'gradle'], default='maven')
    parser.add_argument('--sources-only', action='store_true')
    options = parser.parse_args()
    print(json.dumps(verify('.run/real-kubernetes', options.tools, options.engine, options.build, options.sources_only), indent=2))
