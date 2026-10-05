"""One bounded polling collector per session; durable cursors live with the log records."""
import hashlib
import json
import re
import subprocess
import threading
from app.services.execution_policy import execution_mode
from app.services.logged_process import run_logged

_lock = threading.RLock()
_collectors = {}
_stamp = re.compile(r'^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\.(\d{1,9})Z (.*)$')


def capture_once(session_id):
    if execution_mode(session_id).value != 'DOCKER':
        return False
    from app.services import docker_service as service
    from app.services.deployment_logs import redact, save, MAX_ENTRIES
    listing = subprocess.run(['docker', 'ps', '-a', '--filter',
        f'label=com.docker.compose.project={session_id}', '--format', '{{.ID}}'],
        capture_output=True, text=True, timeout=5, check=False)
    if listing.returncode:
        raise RuntimeError('No se pudo consultar contenedores para capturar logs.')
    ids = listing.stdout.split()
    if not ids:
        return False
    result = subprocess.run(['docker', 'inspect', *ids], capture_output=True, text=True, timeout=5, check=False)
    if result.returncode:
        raise RuntimeError('No se pudo verificar identidad de los contenedores de logs.')
    active = False
    for container in json.loads(result.stdout):
        labels = container.get('Config', {}).get('Labels') or {}
        role = labels.get('io.agentia.role')
        if labels.get('com.docker.compose.project') != session_id or role not in ('application', 'database'):
            continue
        identity = container['Id']
        active |= container.get('State', {}).get('Running') is True
        with service._operations_lock:
            history = service._deployment_log_snapshot(session_id)
            checkpoint = history.get('collectors', {}).get(identity, {})
        command = ['docker', 'logs', '--timestamps', '--tail', '1000']
        if checkpoint.get('timestamp'):
            command += ['--since', checkpoint['timestamp']]
        output = []
        run_logged(command + [identity], output.append, timeout=5)
        # Merged stdout/stderr may arrive with different timestamp order.
        lines = []
        for line in output:
            match = _stamp.match(line)
            if match:
                stamp = match[1] + '.' + match[2].ljust(9, '0') + 'Z'
                lines.append((stamp, redact(match[3])))
        lines.sort(key=lambda item: item[0])
        with service._operations_lock:
            history = service._deployment_log_snapshot(session_id)
            old = history.get('collectors', {}).get(identity, {})
            watermark = old.get('timestamp', '')
            seen = old.get('counts', {})
            counts = {}
            new = []
            latest = watermark
            latest_counts = dict(seen)
            for stamp, message in lines:
                if stamp < watermark:
                    continue
                key = hashlib.sha256(message.encode('utf-8')).hexdigest()
                pair = (stamp, key)
                counts[pair] = counts.get(pair, 0) + 1
                if stamp == watermark and counts[pair] <= seen.get(key, 0):
                    continue
                new.append({'id': history['nextId'] + len(new), 'message': message,
                            'source': role, 'timestamp': stamp})
                if stamp > latest:
                    latest, latest_counts = stamp, {}
                latest_counts[key] = latest_counts.get(key, 0) + 1
            if not new:
                continue
            updated = {**history, 'nextId': history['nextId'] + len(new),
                       'entries': (history['entries'] + new)[-MAX_ENTRIES:],
                       'collectors': {**history.get('collectors', {}),
                                      identity: {'timestamp': latest, 'counts': latest_counts}}}
            # Bound checkpoints across rebuilds as well as the visible history.
            updated['collectors'] = dict(list(updated['collectors'].items())[-8:])
            save(session_id, updated)
            service._raw_log_history[session_id] = updated
            if len(lines) >= 1000:
                service._log_message(session_id, '[LOG GAP] Se alcanzó el límite de lectura; puede haber mensajes anteriores omitidos.')
    return active


def ensure_capture(session_id):
    if execution_mode(session_id).value != 'DOCKER':
        return
    with _lock:
        if session_id in _collectors:
            return
        stop = threading.Event()
        _collectors[session_id] = stop
        def worker():
            from app.services import docker_service as service
            try:
                while not stop.is_set():
                    try:
                        if not capture_once(session_id):
                            break
                    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
                        service._log_message(session_id, '[LOG CAPTURE] Captura interrumpida; consulte estado y reintente.')
                        break
                    if stop.wait(2):
                        break
            finally:
                with _lock:
                    if _collectors.get(session_id) is stop:
                        del _collectors[session_id]
        try:
            threading.Thread(target=worker, daemon=True, name=f'logs-{session_id}').start()
        except Exception:
            del _collectors[session_id]
            raise


def stop_capture(session_id):
    with _lock:
        stop = _collectors.get(session_id)
        if stop:
            stop.set()
