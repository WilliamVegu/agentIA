"""Remove only the temporary verification container identified by exact operation labels."""
import json
import subprocess


def cleanup_sandbox(name, session_id, operation_id):
    def command(args):
        result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=10, check=False)
        if result.returncode:
            raise RuntimeError('No se pudo comprobar/retirar el contenedor temporal de verificación.')
        return result.stdout.strip()
    def listing():
        return command(['ps', '-a', '--filter', f'name=^/{name}$', '--format', '{{.ID}}']).split()
    ids = listing()
    if not ids:
        return True
    containers = json.loads(command(['inspect', *ids]))
    if len(containers) != len(ids):
        raise RuntimeError('Identidad incompleta; limpieza de sandbox rechazada.')
    for item in containers:
        labels = item.get('Config', {}).get('Labels') or {}
        if (item.get('Name') != '/' + name or labels.get('io.agentia.operation') != operation_id
            or labels.get('io.agentia.role') != 'verification'
            or labels.get('com.docker.compose.project') != session_id):
            raise RuntimeError('Identidad ajena; limpieza de sandbox rechazada.')
    # No volumes or other session containers are touched.
    result = subprocess.run(['docker', 'rm', '-f', *[item['Id'] for item in containers]],
                            capture_output=True, text=True, timeout=15, check=False)
    if listing():
        raise RuntimeError('El contenedor temporal sigue presente; limpieza no confirmada.')
    return True  # Includes the harmless race with docker run --rm removing it first.
