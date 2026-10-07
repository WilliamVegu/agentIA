"""Run two unchanged studios and a static selector, in separate processes."""
from __future__ import annotations

import argparse
import functools
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
SYSTEMS = {
    'springboot': {'root': ROOT, 'host': '127.0.0.1', 'frontend': 3000, 'backend': 8000},
    # Cookies ignore ports. A distinct hostname prevents cross-studio login/logout.
    'quarkus': {'root': ROOT / 'systems/quarkus', 'host': 'localhost', 'frontend': 3001, 'backend': 8001},
}
PORTAL_PORT = 3100
HTTP = build_opener(ProxyHandler({}))


def python_for(root: Path) -> str:
    relative = 'Scripts/python.exe' if os.name == 'nt' else 'bin/python'
    executable = root / '.venv' / relative
    if not executable.is_file():
        raise RuntimeError(f'Falta {executable}. Ejecuta python integration/launch.py --install primero.')
    return str(executable)


def install() -> None:
    node = shutil.which('node')
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not node or not npm:
        raise RuntimeError('Instala Node.js y npm antes de preparar ambos sistemas.')
    # Invoke the npm JavaScript entry point without a shell, including on Windows.
    npm_cli = Path(npm).resolve().parent / 'node_modules/npm/bin/npm-cli.js'
    if not npm_cli.is_file():
        npm_cli = Path(npm).resolve()
    for name, system in SYSTEMS.items():
        root = system['root']
        print(f'Preparando dependencias independientes: {name}', flush=True)
        if not (root / '.venv').exists():
            subprocess.run([sys.executable, '-m', 'venv', str(root / '.venv')], check=True)
        subprocess.run([python_for(root), '-m', 'pip', 'install', '-c', str(ROOT / 'integration/constraints.txt'), '-r', str(root / 'backend/requirements.txt')], cwd=root, check=True)
        subprocess.run([node, str(npm_cli), 'ci'], cwd=root / 'frontend', check=True)


def service_environment(name: str, system: dict) -> dict:
    env = os.environ.copy()
    backend = system['root'] / 'backend'
    # Override inherited paths: never share SQLite, workspaces, specifications or telemetry.
    env.update({
        'PYTHONPATH': str(backend),
        'PYTHONUNBUFFERED': '1',
        'DATABASE_URL': f"sqlite:///{(backend / 'studio.db').as_posix()}",
        'COST_STORE_PATH': str(backend / 'cost_tracking.db'),
        'WORKSPACE_DIR': str(backend / 'workspaces'),
        'SPECIFICATION_DIR': str(backend / 'specifications'),
        'MLFLOW_EXPERIMENT': f'agentia-{name}',
        'CORS_ORIGINS': json.dumps([f"http://{system['host']}:{system['frontend']}"]),
        'HOST': '127.0.0.1',
        'PORT': str(system['backend']),
    })
    return env


def require_free_ports() -> None:
    # Reserve all listeners together, then release; Vite also uses strictPort.
    sockets = []
    try:
        listeners = [('127.0.0.1', PORTAL_PORT)]
        for system in SYSTEMS.values():
            listeners.extend([('127.0.0.1', system['backend']), (system['host'], system['frontend'])])
        for host, port in listeners:
            family = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)[0][0]
            listener = socket.socket(family, socket.SOCK_STREAM)
            sockets.append(listener)
            if os.name == 'nt':
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                listener.bind((host, port))
            except OSError as exc:
                raise RuntimeError(f'Puerto ocupado: {host}:{port}. No se ha detenido ni reemplazado ningún servicio existente.') from exc
    finally:
        for listener in sockets:
            listener.close()


def wait_ready(url: str, child: subprocess.Popen, timeout: float = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError(f'El proceso terminó antes de responder en {url}; revisa .run/dual/*.log.')
        try:
            with HTTP.open(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(0.25)
    raise RuntimeError(f'No respondió {url}; revisa .run/dual/*.log.')


def stop_child(child: subprocess.Popen) -> None:
    if child.poll() is not None:
        return
    if os.name == 'nt':
        # Only a still-live process created by this launcher and its own descendants.
        subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], capture_output=True)
    else:
        os.killpg(child.pid, signal.SIGTERM)
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name != 'nt':
            os.killpg(child.pid, signal.SIGKILL)
        else:
            child.kill()
        child.wait(timeout=10)


def launch(open_browser: bool = True) -> None:
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node.js no está disponible.')
    for system in SYSTEMS.values():
        python_for(system['root'])
        if not (system['root'] / 'frontend/node_modules/vite/package.json').is_file():
            raise RuntimeError('Faltan dependencias frontend. Ejecuta python integration/launch.py --install.')
    require_free_ports()
    logs = ROOT / '.run/dual'
    logs.mkdir(parents=True, exist_ok=True)
    children = []
    handles = []
    portal = None
    try:
        for name, system in SYSTEMS.items():
            root = system['root']
            env = service_environment(name, system)
            commands = [
                ('backend', [python_for(root), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(system['backend'])], root),
                ('frontend', [node, str(ROOT / 'integration/dual-vite.mjs'), str(root / 'frontend'), system['host'], str(system['frontend']), str(system['backend'])], root / 'frontend'),
            ]
            for kind, command, cwd in commands:
                log = (logs / f'{name}-{kind}.log').open('w', encoding='utf-8')
                handles.append(log)
                options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
                child = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, **options)
                children.append(child)
                url = f"http://127.0.0.1:{system['backend']}/healthz" if kind == 'backend' else f"http://{system['host']}:{system['frontend']}/healthz"
                wait_ready(url, child)
            print(f"{name}: http://{system['host']}:{system['frontend']}", flush=True)
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(ROOT / 'integration/portal'))
        portal = ThreadingHTTPServer(('127.0.0.1', PORTAL_PORT), handler)
        threading.Thread(target=portal.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{PORTAL_PORT}'
        print(f'Selector listo: {url}\nCtrl+C para detener únicamente esta ejecución.', flush=True)
        if open_browser:
            webbrowser.open(url)
        while True:
            for child in children:
                if child.poll() is not None:
                    raise RuntimeError('Uno de los sistemas se detuvo. Revisa .run/dual/*.log.')
            time.sleep(0.5)
    finally:
        if portal:
            portal.shutdown()
            portal.server_close()
        for child in reversed(children):
            stop_child(child)
        for handle in handles:
            handle.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Preparar dos entornos Python y dos instalaciones npm, sin iniciar servicios.')
    parser.add_argument('--no-browser', action='store_true', help='No abrir el navegador automáticamente.')
    args = parser.parse_args()
    try:
        if args.install:
            install()
        else:
            launch(not args.no_browser)
    except KeyboardInterrupt:
        print('\nServicios de esta ejecución detenidos. Los datos se conservan.')
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
