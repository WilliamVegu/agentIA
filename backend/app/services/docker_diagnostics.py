"""Explicit diagnostics; sources never probe Docker. Cache uses a temporary read-only container."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from app.config import settings
from app.services.execution_policy import execution_mode
from app.services.local_deployment_assets import builder_image
from app.services.build_layout import build_layout
from app.services.deployment_logs import redact


def _architecture(value):
    return {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(value, value)


def _probe_prepared_cache(run, image, build_tool):
    """No mounts/writes/pulls/network; cleanup only after matching our UUID label."""
    token = uuid.uuid4().hex
    name = 'agentia-diagnostic-' + token
    code, _, _ = run(['run', '--rm', '--name', name, '--label', 'io.agentia.diagnostic=' + token,
        '--pull', 'never', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--memory', '64m', '--cpus', '0.5', '--pids-limit', '32',
        '--entrypoint', 'sh', image, '-c',
        'test -d /opt/agentia-cache && test -r /opt/agentia-cache && '
        'test -n "$(find /opt/agentia-cache -type f -name \'*.jar\' -print -quit)"'],
        timeout=settings.LOCAL_DIAGNOSTIC_CACHE_TIMEOUT)
    inspected, output, error = run(['container', 'inspect', name])
    cleaned = inspected == 1 and 'no such' in error.lower()
    if inspected == 0:
        try:
            metadata = json.loads(output)[0]
            if metadata['Config']['Labels'].get('io.agentia.diagnostic') == token:
                removed, _, _ = run(['rm', '-f', metadata['Id']])
                cleaned = removed == 0
        except (ValueError, KeyError, IndexError, TypeError):
            pass
    if not cleaned:
        return 'UNKNOWN', 'Fin/limpieza del contenedor temporal no confirmado; no se certifica la caché.'
    if code:
        return 'UNAVAILABLE', 'Caché preparada ausente, ilegible o consulta interrumpida. Repita preparación explícita.'
    return 'AVAILABLE', f'Caché {build_tool} legible con artefactos JAR. No demuestra todas las dependencias/plugins offline.'


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
    def run(args, timeout=4):
        try:
            proc = subprocess.run(['docker', *args], capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=timeout, check=False)
            return proc.returncode, proc.stdout or '', proc.stderr or ''
        except (OSError, subprocess.SubprocessError) as exc:
            return -1, '', type(exc).__name__
    def text_check(name, args):
        code, output, error = run(args)
        check(name, 'AVAILABLE' if not code else 'UNAVAILABLE', redact(output.strip())[:500] if not code else f'Consulta falló (exit code {code}): {redact(error)[-500:]}')
        return code, output
    context_code, _ = text_check('context', ['context', 'show'])
    compose_code, _ = text_check('compose', ['compose', 'version'])
    buildx_code, _ = text_check('buildx', ['buildx', 'version'])
    kit_code, kit_output, _ = run(['buildx', 'inspect']) if not buildx_code else (-1, '', '')
    node_statuses = re.findall(r'^\s*Status:\s*(\S+)\s*$', kit_output, re.MULTILINE)
    buildkit = not kit_code and bool(node_statuses) and all(s == 'running' for s in node_statuses)
    check('buildkit', 'AVAILABLE' if buildkit else 'UNAVAILABLE',
          'Builder seleccionado operativo, sin bootstrap.' if buildkit else 'Builder no operativo o estado no verificable; no se arrancó automáticamente.')
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
          f"Motor Linux {info.get('ServerVersion', '')}; arquitectura {info.get('Architecture', '')}." if linux else ('Seleccione un motor Linux.' if not code else f'Motor inaccesible (exit code {code}): {redact(error)[-500:]}'))
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
    enough_space = False
    try:
        free = shutil.disk_usage(ws).free
        enough_space = free >= settings.LOCAL_MIN_FREE_BYTES
        check('disk', 'AVAILABLE' if enough_space else 'UNAVAILABLE', f'Espacio libre: {free // (1024*1024)} MiB; mínimo configurado: {settings.LOCAL_MIN_FREE_BYTES // (1024*1024)} MiB. No estima almacenamiento interno Docker ni espacio total de builds.', freeBytes=free)
    except OSError as exc:
        check('disk', 'UNKNOWN', type(exc).__name__)
    report['readyForPreparation'] = bool(linux and writable and enough_space and buildkit and not context_code and not compose_code and not buildx_code)
    if not linux: return report
    import yaml
    try:
        tool, _, _ = build_layout(ws)
        manifest = yaml.safe_load((ws / 'docker-compose.yml').read_text(encoding='utf-8'))
        images = {builder_image(ws), 'agentia-runtime:21-v1'}
        images.update(s['image'] for s in manifest['services'].values() if 'build' not in s)
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError):
        check('manifests', 'UNAVAILABLE', 'Genere primero los manifiestos del proyecto.')
        return report
    host_cache = Path(os.environ.get('GRADLE_CACHE_DIR', str(Path.home() / '.gradle')) if tool == 'gradle' else settings.MAVEN_CACHE_DIR)
    try:
        with os.scandir(host_cache) as entries:
            nonempty = next(entries, None) is not None
        check('host-cache', 'AVAILABLE' if nonempty else 'UNAVAILABLE',
              f'Directorio de caché host {tool} legible' + (' y no vacío.' if nonempty else ' pero vacío.') +
              ' Camino alternativo; no demuestra dependencias completas ni es requisito del builder preparado.')
    except OSError as exc:
        check('host-cache', 'UNAVAILABLE', f'Caché host {tool} ausente/ilegible ({type(exc).__name__}); no impide usar builder preparado.')
    architecture = _architecture(info.get('Architecture', ''))
    images_available = True
    builder_available = False
    for image in sorted(images):
        image_code, output, _ = run(['image', 'inspect', image])
        detail, identity, digests = 'Imagen ausente: prepare el proyecto con conexión.', None, []
        if not image_code:
            try:
                metadata = json.loads(output)[0]
                identity, digests = metadata['Id'], metadata.get('RepoDigests') or []
                if metadata.get('Os') != 'linux' or not isinstance(identity, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', identity) or not architecture or _architecture(metadata.get('Architecture')) != architecture:
                    raise ValueError('invalid image')
                detail = 'Imagen local Linux de arquitectura compatible identificada; no acredita dependencias offline completas.'
            except (ValueError, KeyError, IndexError, TypeError):
                image_code = -1
                detail = 'No se pudo verificar identidad Linux/arquitectura compatible de la imagen.'
        images_available &= not image_code
        check('image', 'AVAILABLE' if not image_code else 'UNAVAILABLE', detail, image=image, imageId=identity, repoDigests=digests)
        if image == builder_image(ws): builder_available = not image_code
    report['preparedImagesAvailable'] = bool(images_available)
    if builder_available:
        status, detail = _probe_prepared_cache(run, builder_image(ws), tool)
        check('prepared-cache', status, detail)
    else:
        check('prepared-cache', 'UNAVAILABLE', 'Builder preparado ausente/incompatible; no se ejecutó contenedor de diagnóstico.')
    return report
