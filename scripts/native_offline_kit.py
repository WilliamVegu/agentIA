"""Explicit Windows preparation and offline installation, independent of Docker.

prepare uses the network; install reads a verified kit and never uses a registry.
Install into a new folder, then use the printed native Python/Node commands.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

BUILD_FILES = ('backend/requirements.txt', 'frontend/package.json', 'frontend/package-lock.json')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def files(root):
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'Enlace no permitido en el kit: {path}')
        if path.is_file() and path != root / 'manifest.json':
            yield path


def run(command, cwd, label, offline=False):
    temporary = (cwd / 'temporary').resolve()
    temporary.mkdir(exist_ok=True)
    user_config, global_config = temporary / 'user.npmrc', temporary / 'global.npmrc'
    user_config.write_text('', encoding='utf-8')
    global_config.write_text('', encoding='utf-8')
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PIP_DISABLE_PIP_VERSION_CHECK='1',
                       PIP_CONFIG_FILE=os.devnull, npm_config_audit='false', npm_config_fund='false',
                       npm_config_userconfig=str(user_config), npm_config_globalconfig=str(global_config),
                       TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary))
    if offline:
        environment.update(PIP_NO_INDEX='1', npm_config_offline='true',
                           HTTP_PROXY='http://127.0.0.1:9', HTTPS_PROXY='http://127.0.0.1:9')
    with (cwd / (label + '.log')).open('w', encoding='utf-8') as output:
        result = subprocess.run([str(arg) for arg in command], cwd=cwd, env=environment,
                                stdout=output, stderr=subprocess.STDOUT, timeout=1200)
    if result.returncode:
        raise RuntimeError(f'{label}: exit {result.returncode}. Consulte {cwd / (label + ".log")}')


def new_directory(path):
    path = path.resolve()
    if path.exists():
        raise ValueError(f'Use una carpeta nueva; no se sobrescribe: {path}')
    path.mkdir(parents=True)
    return path


def project_hashes(project):
    return {name: digest(project / name) for name in BUILD_FILES}


def prepare(project, destination, reuse=None):
    if sys.platform != 'win32':
        raise ValueError('Este kit se prepara para Windows.')
    node = Path(shutil.which('node') or '')
    npm = node.parent / 'node_modules/npm/bin/npm-cli.js'
    if not node.is_file() or not npm.is_file():
        raise ValueError('Se requieren Node y npm instalados para la preparación inicial.')
    # Validate declared dependencies before creating a potentially large kit.
    from packaging.requirements import Requirement
    for line in (project / 'backend/requirements.txt').read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        installed = importlib.metadata.version(requirement.name)
        if installed not in requirement.specifier:
            raise ValueError(f'{requirement.name}: versión instalada incompatible {installed}')
    source_hashes = project_hashes(project)
    if reuse:
        verify(project, reuse)
    kit = new_directory(destination)
    (kit / 'wheels').mkdir()
    shutil.copytree(Path(sys.base_prefix).resolve(), kit / 'python',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'site-packages'))
    (kit / 'node').mkdir()
    shutil.copy2(node, kit / 'node/node.exe')
    shutil.copytree(npm.parents[1], kit / 'node/npm')
    lock = sorted({f'{dist.metadata["Name"]}=={dist.version}' for dist in importlib.metadata.distributions()
                   if dist.metadata['Name'].lower() not in {'pip', 'setuptools', 'wheel'}})
    (kit / 'requirements.lock').write_text('\n'.join(lock) + '\n', encoding='utf-8')
    warm = kit / 'preparation'
    warm.mkdir()
    python = kit / 'python/python.exe'
    run([python, '-B', '-m', 'venv', warm / 'venv'], warm, 'bootstrap-pip')
    if reuse:
        if (reuse / 'requirements.lock').read_text() != (kit / 'requirements.lock').read_text():
            raise ValueError('Cambió el lock Python; prepare un kit nuevo sin reutilizar descargas.')
        shutil.copytree(reuse / 'wheels', kit / 'wheels', dirs_exist_ok=True)
        shutil.copytree(reuse / 'npm-cache', kit / 'npm-cache')
    else:
        run([warm / 'venv/Scripts/python.exe', '-B', '-m', 'pip', 'download', '--only-binary=:all:',
             '--no-cache-dir', '-r', kit / 'requirements.lock', '--dest', kit / 'wheels'], warm, 'download-wheels')
    shutil.copy2(project / 'frontend/package.json', warm / 'package.json')
    shutil.copy2(project / 'frontend/package-lock.json', warm / 'package-lock.json')
    run([kit / 'node/node.exe', kit / 'node/npm/bin/npm-cli.js', 'ci', '--ignore-scripts',
         '--cache', kit / 'npm-cache', '--no-audit', '--no-fund', *(['--offline'] if reuse else [])], warm, 'download-npm', offline=bool(reuse))
    # Warmup stays outside the transferable catalog. No sources or credentials are bundled.
    shutil.copy2(__file__, kit / 'native_offline_kit.py')
    catalog = {path.relative_to(kit).as_posix(): {'bytes': path.stat().st_size, 'sha256': digest(path)}
               for path in files(kit) if 'preparation' not in path.relative_to(kit).parts}
    manifest = {'formatVersion': 1, 'platform': sys.platform, 'machine': platform.machine(),
                'pythonVersion': platform.python_version(),
                'nodeVersion': subprocess.check_output([node, '--version'], text=True).strip(),
                'projectFiles': source_hashes, 'files': catalog, 'offlineVerified': False}
    (kit / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Kit preparado: {kit}. La preparación online no acredita instalación offline.')


def verify(project, kit):
    manifest = json.loads((kit / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('formatVersion') != 1 or manifest.get('platform') != sys.platform or manifest.get('machine') != platform.machine():
        raise ValueError('Kit incompatible con la plataforma/arquitectura.')
    if manifest['projectFiles'] != project_hashes(project):
        raise ValueError('Dependencias del proyecto modificadas: repita la preparación.')
    actual = {path.relative_to(kit).as_posix() for path in files(kit)
              if 'preparation' not in path.relative_to(kit).parts}
    if actual != set(manifest['files']):
        raise ValueError('Catálogo del kit modificado.')
    for name, expected in manifest['files'].items():
        path = kit / name
        if path.stat().st_size != expected['bytes'] or digest(path) != expected['sha256']:
            raise ValueError(f'Integridad incorrecta: {name}')
    return manifest


def install(project, kit, destination):
    manifest = verify(project, kit)  # All integrity checks precede writes/subprocesses.
    target = new_directory(destination)
    # Relocated runtimes and writable caches belong only to this installation.
    shutil.copytree(kit / 'python', target / 'python')
    shutil.copytree(kit / 'node', target / 'node')
    python = target / 'python/python.exe'
    run([python, '-B', '-m', 'venv', target / 'venv'], target, 'create-environment', offline=True)
    run([target / 'venv/Scripts/python.exe', '-B', '-m', 'pip', 'install', '--no-index', '--no-cache-dir',
         '--find-links', kit / 'wheels', '-r', kit / 'requirements.lock'], target, 'install-wheels', offline=True)
    shutil.copytree(project / 'frontend', target / 'frontend',
                    ignore=shutil.ignore_patterns('node_modules', 'dist', '.npm-cache', '.vite', '.env', '.env.*'))
    shutil.copytree(kit / 'npm-cache', target / 'npm-cache')
    node, npm = target / 'node/node.exe', target / 'node/npm/bin/npm-cli.js'
    run([node, npm, 'ci', '--offline', '--ignore-scripts', '--no-audit', '--no-fund',
         '--cache', target / 'npm-cache'], target / 'frontend', 'install-npm', offline=True)
    # Invoke tools through the bundled Node: no PATH/global installation is required.
    run([node, target / 'frontend/node_modules/typescript/bin/tsc'], target / 'frontend', 'typescript', offline=True)
    run([node, target / 'frontend/node_modules/vite/bin/vite.js', 'build'], target / 'frontend', 'build', offline=True)
    # Each command stays in its user's shell; no global PATH or policy changes.
    (target / 'start-backend.ps1').write_text(
        "param([Parameter(Mandatory=$true)][string]$Project)\n$ErrorActionPreference='Stop'\n"
        "$env:PYTHONDONTWRITEBYTECODE='1'\nSet-Location -LiteralPath (Join-Path $Project 'backend')\n"
        "& (Join-Path $PSScriptRoot 'venv/Scripts/python.exe') -B -m uvicorn app.main:app --host 127.0.0.1 --port 8000\n"
        "if ($LASTEXITCODE -ne 0) { throw 'El backend terminó con error.' }\n", encoding='utf-8')
    (target / 'start-frontend.ps1').write_text(
        "$ErrorActionPreference='Stop'\nSet-Location -LiteralPath (Join-Path $PSScriptRoot 'frontend')\n"
        "& (Join-Path $PSScriptRoot 'node/node.exe') ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port 3000 --strictPort\n"
        "if ($LASTEXITCODE -ne 0) { throw 'El frontend terminó con error.' }\n", encoding='utf-8')
    (target / 'installation-result.json').write_text(json.dumps({'result': 'PASS', 'offlinePackageInstall': True,
        'externalNetworkGloballyBlocked': False, 'dockerRequired': False, 'projectFiles': manifest['projectFiles'],
        'pythonVersion': manifest['pythonVersion'], 'nodeVersion': manifest['nodeVersion']}, indent=2), encoding='utf-8')
    print(f'Instalación offline completada: {target}. Docker no se invocó ni se requiere.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'install', 'verify'))
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--reuse-downloads', type=Path, help='Reutilizar solo un kit íntegro con el mismo lock')
    options = parser.parse_args()
    project, kit = options.project.resolve(), options.kit.resolve()
    if options.action == 'prepare':
        prepare(project, kit, options.reuse_downloads.resolve() if options.reuse_downloads else None)
    elif options.action == 'verify':
        verify(project, kit)
        print('Integridad del kit aprobada.')
    else:
        if options.destination is None:
            parser.error('install requiere --destination en una carpeta nueva')
        install(project, kit, options.destination)


if __name__ == '__main__':
    main()
