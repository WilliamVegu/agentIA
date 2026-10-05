"""Prepare the verified PostgreSQL session without exposing its local credentials."""
import json
import subprocess
from pathlib import Path
import secrets
import hashlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/docker-flow-20261005-112428-ad8273'
WS = OUT / 'workspaces/4c849f7c-4240-4aa2-8dca-83ae9a4a837d'
delivery = json.loads((WS / 'LOCAL_DELIVERY.json').read_text())
project = delivery['composeProject']

def docker(*args):
    completed = subprocess.run(['docker', *args], capture_output=True, text=True, encoding='utf-8', timeout=60)
    if completed.returncode:
        raise RuntimeError('Docker command failed: ' + ' '.join(args[:3]))
    return completed.stdout

engine = json.loads(docker('info', '--format', '{{json .}}'))
if engine['OSType'] != 'linux':
    raise RuntimeError('Linux Docker Engine required')
required = delivery['requiredImages'] + [project + '-flow-inventory-service:local']
images = []
for reference in required:
    record = json.loads(docker('image', 'inspect', reference))[0]
    if record['Os'] != 'linux':
        raise RuntimeError('Incompatible image: ' + reference)
    images.append({'reference': reference, 'id': record['Id']})
for relative, expected in delivery['buildManifests'].items():
    if hashlib.sha256((WS / relative).read_bytes()).hexdigest() != expected:
        raise RuntimeError('Build dependencies changed; repeat explicit preparation')

env_file = WS / '.env'
mode = 'existing-local-file'
if not env_file.exists():
    # An initialized persistent database must retain its existing password.
    # Inspect only containers proven to belong to this project and database role.
    ids = docker('ps', '-a', '-q', '--filter', 'label=com.docker.compose.project=' + project,
                 '--filter', 'label=io.agentia.role=database').split()
    if len(ids) > 1:
        raise RuntimeError('Ambiguous database identity')
    if ids:
        record = json.loads(docker('inspect', ids[0]))[0]
        labels = record['Config']['Labels']
        if labels.get('com.docker.compose.project') != project or labels.get('io.agentia.role') != 'database':
            raise RuntimeError('Foreign database refused')
        env = dict(item.split('=', 1) for item in record['Config']['Env'] if '=' in item)
        password = env.get('POSTGRES_PASSWORD')
        if not password or any(c in password for c in '\r\n\x00'):
            raise RuntimeError('Cannot safely restore database credential')
        mode = 'restored-from-owned-database'
    else:
        volumes = docker('volume', 'ls', '-q', '--filter', 'label=com.docker.compose.project=' + project).split()
        if any(name.endswith('_dbdata') for name in volumes):
            raise RuntimeError('Initialized volume exists without credential source; do not overwrite its password')
        password = secrets.token_urlsafe(32)
        mode = 'new-random-local-credential'
    # Compose single quotes preserve literal dollars and other password characters.
    if "'" in password:
        raise RuntimeError('Credential requires manual dotenv quoting; nothing overwritten')
    with env_file.open('x', encoding='utf-8') as output:
        output.write("# Local PostgreSQL credential. Excluded from Git and source snapshots.\nDB_PASSWORD='" + password + "'\n")
    del password
report = {'result': 'READY', 'project': project, 'workspace': str(WS), 'database': 'POSTGRESQL',
          'images': images, 'credentialSource': mode, 'credentialFile': '.env', 'buildInputsUnchanged': True,
          'composeVersion': docker('compose', 'version').strip()}
(OUT / 'postgresql-preparation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
