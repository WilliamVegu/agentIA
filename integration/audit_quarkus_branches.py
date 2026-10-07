"""Read/live audit of the two Quarkus-named branches using local offline requests."""
import json
from pathlib import Path
import httpx
import yaml

OUT = Path(__file__).resolve().parent / 'validation'
OUT.mkdir(exist_ok=True)
observations = {}

CONTRACT = '''openapi: 3.1.0
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
components:
  schemas:
    ItemRecord:
      type: object
      properties:
        id:
          type: string
          format: uuid
        sku:
          type: string
'''

for branch, base in [('Quarkus_refact', 'http://127.0.0.1:8012'), ('Quarkus_refact_2', 'http://127.0.0.1:8013')]:
    with httpx.Client(base_url=base, trust_env=False, timeout=60, headers={'X-LLM-Provider': 'mock'}) as client:
        paths = client.get('/openapi.json').json()['paths']
        info = {'health_status': client.get('/healthz').status_code, 'quarkus_api_paths': [path for path in paths if '/quarkus/' in path]}
        if branch == 'Quarkus_refact_2':
            info['local_login_status'] = client.post('/api/v1/auth/mvp').status_code
            info['authenticated_quarkus_orders_status'] = client.get('/api/v1/quarkus/orders').status_code
            observations[branch] = info
            continue
        for build_tool in ['maven', 'gradle']:
            payload = {'basic_data': {'service_name': f'audit-inventory-{build_tool}', 'team': 'Audit', 'group_id': 'com.example.audit', 'java_version': '21', 'build_tool': build_tool},
                'business': {'description': 'Manage inventory products, stock levels and warehouse movements for each item.'},
                'technical': {'database': 'PostgreSQL', 'security': 'JWT (SmallRye JWT)', 'enable_kafka': False},
                'attachments': {'existing_openapi': CONTRACT}}
            created = client.post('/api/v1/quarkus/orders', json=payload)
            info[build_tool] = current = {'create_status': created.status_code}
            if created.status_code != 201:
                current['error'] = created.text
                continue
            order_id = created.json()['id']
            current['order_id'] = order_id
            prefix = '/api/v1/quarkus/orders/' + order_id
            approval = client.post(prefix + '/approve-contract', json={'approved_by': 'Local audit', 'modified_openapi': CONTRACT, 'approve_database_model': True})
            current['contract_approval_status'] = approval.status_code
            if approval.status_code != 200:
                current['contract_approval_error'] = approval.text
                continue
            proposal = approval.json()['architecture_proposal']
            selection = client.post(prefix + '/select-architecture', json={'selected_pattern': 'layered', 'chosen_build_tool': build_tool, 'extensions': proposal['recommended_extensions']})
            current['architecture_status'] = selection.status_code
            skeleton = client.post(prefix + '/generate-skeleton')
            current['skeleton_status'] = skeleton.status_code
            files = skeleton.json()['generated_files']
            current['framework_is_quarkus'] = 'quarkus' in files.get('pom.xml', files.get('build.gradle', '')).lower()
            properties = files['src/main/resources/application.properties']
            current['postgresql_selected'] = True
            current['production_uses_mssql'] = '%prod.quarkus.datasource.db-kind=mssql' in properties
            current['development_uses_sqlite'] = '%dev.quarkus.datasource.db-kind=sqlite' in properties
            build = client.post(prefix + '/build-and-test')
            current['build_and_test_status'] = build.status_code
            built = build.json()
            current['reported_tests_executed'] = built.get('tests_executed')
            current['reported_tests_summary'] = built.get('tests_summary')
            current['reported_review_score'] = built.get('code_review_report', {}).get('score')
            resources = {path: content for path, content in built['generated_files'].items() if path.endswith('Resource.java')}
            current['concrete_resources_implement_custom_contract_path'] = any('/warehouse/items' in text for text in resources.values())
            current['concrete_resources_expose_persistence_entities'] = any('@Valid ' in text and '.model.' in text for text in resources.values())
            current['generated_concrete_paths'] = [line.strip() for text in resources.values() for line in text.splitlines() if line.strip().startswith('@Path')]
            delivery = client.post(prefix + '/approve-delivery', json={'approved_by': 'Local audit', 'comments': 'Offline artifact inspection', 'target_git_repo': '', 'branch_name': 'audit'})
            current['delivery_status'] = delivery.status_code
            if delivery.status_code != 200:
                current['delivery_error'] = delivery.text
            export = client.get(prefix + '/export-zip')
            current['export_status'] = export.status_code
            if export.status_code == 200:
                (OUT / f'quarkus-refact-{build_tool}-audit.zip').write_bytes(export.content)
            (OUT / f'quarkus-refact-{build_tool}-order.json').write_text(json.dumps(built, indent=2, ensure_ascii=False), encoding='utf-8')
        payload['basic_data']['service_name'] = 'audit-no-auth'
        payload['technical']['security'] = 'Sin autenticación'
        no_auth = client.post('/api/v1/quarkus/orders', json=payload)
        no_auth_approval = client.post('/api/v1/quarkus/orders/' + no_auth.json()['id'] + '/approve-contract', json={'approved_by': 'Local audit'})
        info['no_security_approval_status'] = no_auth_approval.status_code
        info['no_security_approval_body'] = no_auth_approval.text
        # Exercise backend input validation without generating or publishing externally.
        empty = client.post('/api/v1/quarkus/orders', json={})
        info['empty_order_status'] = empty.status_code
        if empty.status_code == 201:
            info['empty_order_default_service'] = empty.json()['basic_data']['service_name']
        observations[branch] = info

(OUT / 'quarkus-branch-live-audit.json').write_text(json.dumps(observations, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(observations, indent=2, ensure_ascii=False))
