"""Observe the exact build's terminal record without stopping a shared builder."""
import json
import subprocess
import time


def confirm_finished(operation_id, timeout=5):
    deadline = time.monotonic() + timeout
    while True:
        try:
            listed = subprocess.run(['docker', 'buildx', 'history', 'ls', '--format', 'json'],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5, check=False)
            if listed.returncode:
                return {'confirmed': False, 'cause': 'BuildKit history unavailable'}
            records = [json.loads(v) for v in listed.stdout.splitlines() if v.strip()]
            # Inspect only the recent build records; exact label must then match.
            for record in records[:20]:
                if time.monotonic() >= deadline:
                    break
                builder, _, reference = record['ref'].split('/', 2)
                inspected = subprocess.run(['docker', 'buildx', 'history', 'inspect', '--builder', builder,
                    reference, '--format', 'json'], capture_output=True, text=True,
                    encoding='utf-8', errors='replace', timeout=5, check=False)
                if inspected.returncode:
                    continue
                info = json.loads(inspected.stdout)
                if {'Name': 'io.agentia.operation', 'Value': operation_id} not in info.get('Labels', []):
                    continue
                if info.get('CompletedAt') and info.get('Status') in {'canceled', 'cancelled', 'error', 'completed'}:
                    return {'confirmed': True, 'ref': record['ref'], 'status': info['Status'], 'finishedAt': info['CompletedAt']}
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            return {'confirmed': False, 'cause': 'Exact BuildKit outcome cannot be read'}
        if time.monotonic() >= deadline:
            return {'confirmed': False, 'cause': 'Exact build has no confirmed terminal record'}
        time.sleep(.2)


def run_build(command, on_line, *, operation_id, runner, **kwargs):
    from app.services.logged_process import CommandCancelled
    try:
        return runner(command, on_line, **kwargs)
    except (CommandCancelled, subprocess.TimeoutExpired) as exc:
        evidence = confirm_finished(operation_id)
        suffix = (' BuildKit: el build exacto termino (' + evidence['status'] + ').' if evidence['confirmed']
                  else ' BuildKit: no se confirma detencion del build en el daemon.')
        # Preserve the interruption class used to prevent later deployment phases.
        if isinstance(exc, CommandCancelled):
            raise CommandCancelled(str(exc) + suffix) from exc
        raise CommandCancelled('Timeout de construccion.' + suffix) from exc
