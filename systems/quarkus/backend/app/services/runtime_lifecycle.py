"""Conservative operations on inspected resources belonging to this studio/session."""
import hashlib
import json
import re
import subprocess
from app.services.secret_redaction import redact


def compose_project(session_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', session_id or ''):
        raise ValueError('Invalid session identity')
    return 'agentia-quarkus-' + hashlib.sha256(session_id.encode()).hexdigest()[:24]


def command(arguments, **kwargs):
    control=kwargs.pop('cancel_event',None)
    timeout=kwargs.pop('timeout',30)
    if control is not None:
        from app.services.logged_process import run_logged
        from collections import deque
        lines=deque(maxlen=1000)
        run_logged(arguments,lines.append,timeout=timeout,cancel_event=control,**kwargs)
        return subprocess.CompletedProcess(arguments,0,stdout='\n'.join(lines),stderr='')
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout, check=False, **kwargs)
    if result.returncode:
        raise RuntimeError(redact(result.stderr or result.stdout or 'Docker operation failed'))
    return result


def owned_resources(session_id, kind='container'):
    project = compose_project(session_id)
    query = ['docker', 'ps', '-a', '--format', '{{.ID}}'] if kind == 'container' else ['docker', kind, 'ls', '-q']
    ids = command(query + ['--filter', 'label=com.docker.compose.project=' + project]).stdout.split()
    if not ids:
        return []
    if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', item) for item in ids):
        raise RuntimeError('Invalid Docker resource identity')
    inspect = ['docker', 'inspect', *ids] if kind == 'container' else ['docker', kind, 'inspect', *ids]
    records = json.loads(command(inspect).stdout)
    if len(records) != len(ids):
        raise RuntimeError('Resource ownership is incomplete')
    for record in records:
        labels = record.get('Config', {}).get('Labels') if kind == 'container' else record.get('Labels')
        labels = labels or {}
        if labels.get('com.docker.compose.project') != project or labels.get('io.agentia.owner') != project or labels.get('io.agentia.studio') != 'quarkus':
            raise RuntimeError('Legacy/unowned resource: operation rejected')
    return records


def stop_owned(session_id):
    records = owned_resources(session_id)
    if not records:
        raise RuntimeError('No identified runtime; cannot certify STOPPED')
    running = [item['Id'] for item in records if item.get('State', {}).get('Running')]
    if running:
        command(['docker', 'stop', '--time', '10', *running], timeout=60)
    if any(item.get('State', {}).get('Running') for item in owned_resources(session_id)):
        raise RuntimeError('Owned containers remain running')
    return records


def cleanup_preview(session_id):
    records = {kind: owned_resources(session_id, kind) for kind in ('container', 'volume', 'network')}
    identities = {kind: sorted(item['Name'] if kind == 'volume' else item['Id'] for item in items) for kind, items in records.items()}
    digest = hashlib.sha256(json.dumps([session_id, identities], sort_keys=True).encode()).hexdigest()
    return {'sessionId': session_id, 'resources': identities, 'confirmationToken': digest}


def cleanup_owned(session_id, *, delete_data=False, confirmation=None):
    if not delete_data:
        raise ValueError('Explicit deleteData confirmation required')
    preview = cleanup_preview(session_id)
    if not confirmation or confirmation != preview['confirmationToken']:
        raise ValueError('Resource preview changed or confirmation is missing')
    # Ownership of every resource is verified before any mutation.
    resources = preview['resources']
    if resources['container']:
        command(['docker', 'rm', '-f', *resources['container']])
    if resources['volume']:
        command(['docker', 'volume', 'rm', *resources['volume']])
    if resources['network']:
        command(['docker', 'network', 'rm', *resources['network']])
    if any(cleanup_preview(session_id)['resources'].values()):
        raise RuntimeError('Cleanup incomplete')
    return preview
