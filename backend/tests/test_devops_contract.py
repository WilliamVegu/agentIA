"""Keep published local API semantics tied to actual FastAPI models/routes."""
from pathlib import Path

import pytest
import yaml

from app.main import app
from app.models.devops import DeploymentStatus
from app.models.execution import ExecutionMode, VerificationOutcome
from app.services.auth_service import COOKIE
from scripts.export_devops_contract import build_contract


@pytest.fixture
def contract():
    path = Path(__file__).resolve().parents[2] / 'specs/007-docker-cicd-orchestration/contracts/devops-api.yaml'
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def test_published_contract_matches_actual_routes_and_models(contract):
    assert contract == build_contract(app, COOKIE)


def test_source_default_and_evidence_enums_remain_distinct(contract):
    schemas = contract['components']['schemas']
    assert schemas['QuickStartSessionRequest']['properties']['executionMode']['default'] == 'SOURCE_ONLY'
    for name, enum in [('ExecutionMode', ExecutionMode), ('VerificationOutcome', VerificationOutcome),
                       ('DeploymentStatus', DeploymentStatus)]:
        assert set(schemas[name]['enum']) == {item.value for item in enum}
    assert 'COMPLETED' not in schemas['VerificationOutcome']['enum']
    assert 'HEALTHY' not in schemas['VerificationOutcome']['enum']


def test_configuration_and_optional_deploy_port_contract(contract):
    schemas = contract['components']['schemas']
    config = schemas['LocalProjectConfiguration']
    assert set(config['required']) == {'databaseEngine', 'hostPort', 'buildTool', 'buildDirectory'}
    assert config['properties']['hostPort']['minimum'] == 1024
    assert config['properties']['hostPort']['maximum'] == 65535
    deploy = schemas['DevOpsDeployRequest']
    assert 'hostPort' not in deploy.get('required', [])
    assert deploy['properties']['hostPort'].get('default') is None


def test_private_cookie_and_sse_header_contract(contract):
    scheme = contract['components']['securitySchemes']['StudioSession']
    assert (scheme['in'], scheme['name']) == ('cookie', COOKIE)
    for path, operations in contract['paths'].items():
        if path.startswith('/api/v1/auth/'):
            continue
        for verb, operation in operations.items():
            if verb in {'get', 'post', 'patch', 'delete'}:
                assert operation['security'] == [{'StudioSession': []}]
                assert '401' in operation['responses']
    stream = contract['paths']['/api/v1/devops/{session_id}/logs/stream']['get']
    assert any(p['name'] == 'last-event-id' and p['in'] == 'header' for p in stream['parameters'])
    assert '400' in stream['responses']
    assert 'text/event-stream' in stream['responses']['200']['content']


def test_all_exported_schema_references_resolve(contract):
    def visit(value):
        if isinstance(value, dict):
            if '$ref' in value:
                ref = value['$ref']
                assert ref.startswith('#/')
                current = contract
                for part in ref[2:].split('/'):
                    current = current[part]
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(contract)
