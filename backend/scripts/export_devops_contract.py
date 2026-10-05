"""Export local deployment OpenAPI from actual routes; no Docker/remote services."""
import argparse
import copy
import os
from pathlib import Path
import sys
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'specs/007-docker-cicd-orchestration/contracts/devops-api.yaml'


def build_contract(app, cookie_name):
    schema = app.openapi()
    selected = {
        '/api/v1/sessions', '/api/v1/sessions/quick-start', '/api/v1/sessions/{session_id}',
        '/api/v1/sessions/{session_id}/execution-mode', '/api/v1/sessions/{session_id}/verify',
        '/api/v1/auth/login', '/api/v1/auth/session', '/api/v1/auth/logout', '/api/v1/auth/mvp',
    }
    paths = {name: copy.deepcopy(value) for name, value in schema['paths'].items()
             if name.startswith('/api/v1/devops/') or name in selected}
    for name, methods in paths.items():
        for method, operation in methods.items():
            if method not in {'get', 'post', 'patch', 'delete', 'put'}: continue
            if not name.startswith('/api/v1/auth/'):
                operation['security'] = [{'StudioSession': []}]
                operation['responses'].setdefault('401', {'description': 'Cookie de sesión requerida.'})
            if name.endswith(('/configuration', '/generate', '/deploy', '/prepare', '/cancel', '/execution-mode', '/verify')):
                operation['responses'].setdefault('409', {'description': 'Conflicto de operación/configuración; consulte detail.'})
            if name.endswith(('/logs/stream', '/cleanup', '/playground')):
                operation['responses'].setdefault('400', {'description': 'Cursor inválido o acción rechazada; consulte detail.'})
    definitions = schema.get('components', {}).get('schemas', {})
    needed = set()
    def visit(value):
        if isinstance(value, dict):
            reference = value.get('$ref', '')
            if reference.startswith('#/components/schemas/'):
                key = reference.rsplit('/', 1)[-1]
                if key not in needed:
                    needed.add(key)
                    visit(definitions[key])
            for item in value.values(): visit(item)
        elif isinstance(value, list):
            for item in value: visit(item)
    visit(paths)
    return {'openapi': schema['openapi'], 'info': {
        'title': 'AgentIA - Contratos de despliegue local', 'version': '2026.10.05',
        'description': 'Generado desde FastAPI. SOURCE_ONLY por defecto. HTTP 200 no acredita pruebas ni readiness. Consulte contracts/README.md.'},
        'servers': [{'url': 'http://localhost:8000'}], 'paths': paths,
        'components': {'securitySchemes': {'StudioSession': {'type': 'apiKey', 'in': 'cookie', 'name': cookie_name}},
                       'schemas': {name: definitions[name] for name in sorted(needed)}}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / 'backend'))
    # Isolate database and tracing; exporting schemas must not use user sessions.
    with tempfile.TemporaryDirectory(prefix='agentia-contract-') as temporary:
        os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(temporary) / 'schema.db').as_posix()
        os.environ['MLFLOW_TRACKING_URI'] = (Path(temporary) / 'mlruns').as_uri()
        from app.cost import mlflow_sink
        mlflow_sink.enable_tracing = lambda: False
        from app.main import app
        from app.services.auth_service import COOKIE
        from app.models.session import engine
        try:
            contract = build_contract(app, COOKIE)
            if args.check:
                assert yaml.safe_load(TARGET.read_text(encoding='utf-8')) == contract, 'Contrato desactualizado; ejecute el exportador.'
                print('Contract matches FastAPI routes and models')
            else:
                TARGET.write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=True), encoding='utf-8')
                print('Exported', len(contract['paths']), 'paths')
        finally:
            engine.dispose()


if __name__ == '__main__':
    main()
