"""Native localhost smoke probe with empty PATH, no Docker and no IA calls."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
from verify_native_source_flow import stop_process_tree

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--installation', type=Path, required=True)
parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
args = parser.parse_args()
target, project = args.installation.resolve(), args.project.resolve()
if not (target / 'installation-result.json').is_file():
    parser.error('Se requiere una instalación completa del kit nativo.')
def port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]
backend_port, frontend_port = port(), port()
while frontend_port == backend_port:
    frontend_port = port()
config = target / 'native-smoke-vite.mjs'
config.write_text(f'export default {{server:{{proxy:{{"/healthz":"http://127.0.0.1:{backend_port}"}}}}}};', encoding='utf-8')
environment = dict(os.environ, PATH='', PYTHONDONTWRITEBYTECODE='1', GIT_PYTHON_REFRESH='quiet',
    PYTHONPATH=str(project / 'backend'), DATABASE_URL='sqlite:///' + (target / 'health.sqlite').as_posix(),
    WORKSPACE_DIR=str(target / 'workspaces'), SPECIFICATION_DIR=str(target / 'specifications'),
    COST_STORE_PATH=str(target / 'cost.sqlite'), LANGCHAIN_TRACING_V2='false',
    HTTP_PROXY='http://127.0.0.1:9', HTTPS_PROXY='http://127.0.0.1:9',
    GEMINI_API_KEY='', GOOGLE_API_KEY='', OPENAI_API_KEY='', GROQ_API_KEY='', ANTHROPIC_API_KEY='')
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def get(url):
    with opener.open(url, timeout=3) as response:
        assert response.status == 200
        return response.read().decode()
def ready(url, process):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('El proceso terminó; consulte los logs de native-smoke.')
        try:
            return get(url)
        except OSError:
            time.sleep(0.5)
    raise RuntimeError('Readiness localhost agotado.')
processes, streams = [], []
report = {'result': 'RUNNING', 'pathEmpty': True, 'externalNetworkGloballyBlocked': False}
try:
    commands = [
        ('backend', [target / 'venv/Scripts/python.exe', '-B', '-m', 'uvicorn', 'app.main:app',
                     '--host', '127.0.0.1', '--port', str(backend_port)], target),
        ('frontend', [target / 'node/node.exe', target / 'frontend/node_modules/vite/bin/vite.js',
                      '--config', config, '--host', '127.0.0.1', '--port', str(frontend_port), '--strictPort'], target / 'frontend')]
    for label, command, cwd in commands:
        output = (target / f'native-smoke-{label}.log').open('w', encoding='utf-8')
        streams.append(output)
        processes.append(subprocess.Popen([str(item) for item in command], cwd=cwd, env=environment,
                                          stdout=output, stderr=subprocess.STDOUT))
    health = json.loads(ready(f'http://127.0.0.1:{backend_port}/healthz', processes[0]))
    html = ready(f'http://127.0.0.1:{frontend_port}', processes[1])
    assert '<html' in html.lower()
    proxy = json.loads(get(f'http://127.0.0.1:{frontend_port}/healthz'))
    assert proxy['status'] == health['status'] == 'UP'
    assert proxy['app'] == health['app'] and proxy['version'] == health['version']
    report.update(result='PASS', backendHealth=True, frontendHttp=True, healthProxy=True,
                  backendPort=backend_port, frontendPort=frontend_port)
except Exception as exc:
    report.update(result='FAILED', error=str(exc))
finally:
    for process in processes:
        stop_process_tree(process)
    for output in streams:
        output.close()
    report['processesStopped'] = all(process.poll() is not None for process in processes)
    (target / 'native-smoke-result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
if report['result'] != 'PASS':
    raise SystemExit(1)
