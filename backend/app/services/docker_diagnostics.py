"""Explicit, read-only Docker capability checks; sources never probe the engine."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from app.config import settings
from app.services.execution_policy import execution_mode
from app.services.local_deployment_assets import builder_image


def diagnose(session_id, workspace):
    report = {'sessionId': session_id, 'executionMode': execution_mode(session_id).value,
              'readyForPreparation': False, 'preparedImagesAvailable': False,
              'offlineVerified': False, 'checks': [], 'availableActions': []}
    def check(name, status, detail, **extra):
        report['checks'].append({'name': name, 'status': status, 'detail': detail, **extra})
    if report['executionMode'] == 'SOURCE_ONLY':
        check('execution', 'SKIPPED_BY_CHOICE', 'Entrega de fuentes elegida; no se consulta Docker.')
        return report
    report['availableActions'] = ['RETRY', 'CONTINUE_WITHOUT_DOCKER']
    if not settings.DOCKER_ENABLED:
        check('policy', 'UNAVAILABLE', 'Docker está prohibido por la configuración administrativa.')
        return report
    if not shutil.which('docker'):
        check('cli', 'UNAVAILABLE', 'Docker CLI no está en PATH.')
        return report
    check('cli', 'AVAILABLE', 'Docker CLI encontrada.')
    def run(args):
        try:
            proc = subprocess.run(['docker', *args], capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=4, check=False)
            return proc.returncode, proc.stdout or '', proc.stderr or ''
        except (OSError, subprocess.SubprocessError) as exc:
            return -1, '', type(exc).__name__
    def text_check(name, args):
        code, output, error = run(args)
        check(name, 'AVAILABLE' if not code else 'UNAVAILABLE', output.strip()[:500] if not code else f'Consulta falló (exit code {code}): {error[-500:]}')
        return code, output
    text_check('context', ['context', 'show'])
    compose_code, _ = text_check('compose', ['compose', 'version'])
    buildx_code, _ = text_check('buildx', ['buildx', 'version'])
    code, output, error = run(['info', '--format', '{{json .}}'])
    info = {}
    if not code:
        try:
            info = json.loads(output)
            if not isinstance(info, dict): raise ValueError('invalid object')
        except ValueError:
            code, error = -1, 'Respuesta Docker info inválida.'
    linux = not code and info.get('OSType') == 'linux'
    check('engine', 'AVAILABLE' if linux else 'UNAVAILABLE',
          f"Motor Linux {info.get('ServerVersion', '')}; arquitectura {info.get('Architecture', '')}." if linux else ('Seleccione un motor Linux.' if not code else f'Motor inaccesible (exit code {code}): {error[-500:]}'))
    ws = Path(workspace).resolve()
    writable = False
    try:
        with tempfile.TemporaryFile(dir=ws) as probe:
            probe.write(b'AgentIA path probe')
            probe.flush()
        writable = True
        check('workspace', 'AVAILABLE', 'Escritura comprobada en el workspace; archivo temporal eliminado.')
    except OSError as exc:
        check('workspace', 'UNAVAILABLE', f'No se puede escribir en el workspace: {type(exc).__name__}.')
    try:
        free = shutil.disk_usage(ws).free
        check('disk', 'AVAILABLE', f'Espacio libre: {free // (1024*1024)} MiB. No estima el espacio total requerido por imágenes/builds.', freeBytes=free)
    except OSError as exc:
        check('disk', 'UNKNOWN', type(exc).__name__)
    report['readyForPreparation'] = bool(linux and writable and not compose_code and not buildx_code)
    if not linux: return report
    import yaml
    try:
        manifest = yaml.safe_load((ws / 'docker-compose.yml').read_text(encoding='utf-8'))
        images = {builder_image(ws), 'agentia-runtime:21-v1'}
        images.update(s['image'] for s in manifest['services'].values() if 'build' not in s)
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError):
        check('manifests', 'UNAVAILABLE', 'Genere primero los manifiestos del proyecto.')
        return report
    images_available = True
    for image in sorted(images):
        image_code, output, _ = run(['image', 'inspect', image])
        detail, identity, digests = 'Imagen ausente: prepare el proyecto con conexión.', None, []
        if not image_code:
            try:
                metadata = json.loads(output)[0]
                identity, digests = metadata['Id'], metadata.get('RepoDigests') or []
                if metadata.get('Os') != 'linux' or not identity: raise ValueError('invalid image')
                detail = 'Imagen local Linux identificada; no acredita dependencias offline completas.'
            except (ValueError, KeyError, IndexError, TypeError):
                image_code = -1
                detail = 'No se pudo verificar la identidad Linux de la imagen.'
        images_available &= not image_code
        check('image', 'AVAILABLE' if not image_code else 'UNAVAILABLE', detail, image=image, imageId=identity, repoDigests=digests)
    report['preparedImagesAvailable'] = bool(images_available)
    return report
