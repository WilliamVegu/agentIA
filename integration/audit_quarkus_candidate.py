"""Local offline checks of Quarkus in the separately checked out Unificado branch."""
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent / 'validation' / 'quarkus-unificado-audit.json'
os.chdir(root)
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['WORKSPACE_DIR'] = str(root / '.run/history/workspaces')
os.environ['SPECIFICATION_DIR'] = str(root / '.run/history/specifications')
os.environ['COST_STORE_PATH'] = str(root / '.run/history/cost.db')
os.environ['MLFLOW_TRACKING_URI'] = (root / '.run/history/mlruns').as_uri()
os.environ['ALLOW_OFFLINE_MOCK'] = 'true'
os.environ['DOCKER_ENABLED'] = 'false'
sys.path.insert(0, str(root / 'backend'))

from fastapi.testclient import TestClient
from app.main import app

contract = '''openapi: 3.1.0
info:
  title: Inventory audit
  version: 1.0.0
paths:
  /warehouse/items:
    get:
      operationId: findWarehouseItems
      responses:
        '200':
          description: Inventory
'''
report = {}
with TestClient(app, headers={'X-LLM-Provider': 'mock'}) as client:
    for tool in ('maven', 'gradle'):
        payload = {'basic_data': {'service_name': f'history-audit-{tool}', 'team': 'Audit', 'group_id': 'com.example.audit', 'java_version': '21', 'build_tool': tool},
            'business': {'description': 'Manage inventory products, stock levels and warehouse movements for each item.'},
            'technical': {'database': 'PostgreSQL', 'security': 'JWT (SmallRye JWT)', 'enable_kafka': False},
            'attachments': {'existing_openapi': contract}}
        create = client.post('/api/v1/quarkus/orders', json=payload)
        assert create.status_code == 201, create.text
        prefix = '/api/v1/quarkus/orders/' + create.json()['id']
        approve = client.post(prefix + '/approve-contract', json={'approved_by': 'Local audit', 'modified_openapi': contract, 'approve_database_model': True})
        assert approve.status_code == 200, approve.text
        select = client.post(prefix + '/select-architecture', json={'selected_pattern': 'layered', 'chosen_build_tool': tool, 'extensions': approve.json()['architecture_proposal']['recommended_extensions']})
        assert select.status_code == 200, select.text
        skeleton = client.post(prefix + '/generate-skeleton')
        assert skeleton.status_code == 200, skeleton.text
        build = client.post(prefix + '/build-and-test')
        assert build.status_code == 200, build.text
        files = build.json()['generated_files']
        properties = files['src/main/resources/application.properties']
        resources = [content for path, content in files.items() if path.endswith('Resource.java')]
        delivery = client.post(prefix + '/approve-delivery', json={'approved_by': 'Local audit', 'target_git_repo': '', 'branch_name': 'audit'})
        export = client.get(prefix + '/export-zip')
        report[tool] = {'create_status': create.status_code, 'approve_status': approve.status_code,
            'select_status': select.status_code, 'skeleton_status': skeleton.status_code,
            'build_status': build.status_code, 'delivery_status': delivery.status_code, 'export_status': export.status_code,
            'delivered_state': delivery.json().get('status'),
            'postgresql_selected_but_production_mssql': '%prod.quarkus.datasource.db-kind=mssql' in properties,
            'custom_contract_path_implemented_by_concrete_resources': any('/warehouse/items' in content for content in resources),
            'reported_tests_executed': build.json().get('tests_executed'),
            'reported_tests_summary': build.json().get('tests_summary')}
    payload['technical']['security'] = 'Sin autenticación'
    create = client.post('/api/v1/quarkus/orders', json=payload)
    assert create.status_code == 201, create.text
    approve = client.post('/api/v1/quarkus/orders/' + create.json()['id'] + '/approve-contract', json={'approved_by': 'Local audit'})
    report['no_security'] = {'approval_status': approve.status_code, 'response': approve.json()}

out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
