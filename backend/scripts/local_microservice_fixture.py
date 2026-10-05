"""Reproducible source fixtures; generating them never prepares or invokes Docker."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from app.orchestrator.stages.deterministic import scaffolder, domain, service, controller, test_synthesis
from app.services.devops_service import generate_all_devops_assets
from app.services.lifecycle_artifacts import _entities_from_blueprint
from app.services.model_sql_service import schema_sql_from_draft

CATALOG_VERSION = 2
BUILDS = ('maven', 'gradle')
DATABASES = ('H2', 'POSTGRESQL', 'MYSQL')


def create_fixture(workspace, build='maven', database='H2', *, seed=False,
                   layout='.', identity=None, host_port=19080, assets=True):
    """Only write a new/empty workspace; runtime credentials are never generated."""
    if build not in BUILDS or database not in DATABASES or layout not in ('.', 'bootstrap'):
        raise ValueError('Unsupported fixture build/database/layout')
    ws = Path(workspace)
    if ws.exists() and (not ws.is_dir() or any(ws.iterdir())):
        raise ValueError('Fixture destination must be new or empty')
    ws.mkdir(parents=True, exist_ok=True)
    module = ws if layout == '.' else ws / 'bootstrap'
    module.mkdir(exist_ok=True)
    blueprint = {'serviceName': 'probe-service', 'packageName': 'com.example.probe', 'basePort': 8080,
                 'databaseMode': database, 'inputInterface': {'buildToolPreference': build},
                 'entities': [{'name': 'Item', 'tableName': 'inventory_records' if seed else 'items',
                    'attributes': [{'name': 'id', 'type': 'Long', 'isPrimaryKey': True, 'nullable': False},
                                   {'name': 'name', 'type': 'String', 'nullable': False}]}], 'userStories': []}
    if seed:
        blueprint['entities'][0]['attributes'].extend([
            {'name': 'amount', 'type': 'BigDecimal', 'nullable': False},
            {'name': 'requestedAt', 'type': 'LocalDateTime', 'nullable': False}])
    state = {'blueprint': blueprint, 'workspace_path': str(module), 'generated_files': {}, 'logs': []}
    for stage in (scaffolder, domain, service, controller, test_synthesis):
        state.update(stage.emit(state))
    # The generic generator currently exposes create/read/delete. This fixture-only
    # endpoint completes CRUD acceptance without changing application generation.
    setters = '\n'.join(f'        item.set{a["name"][0].upper() + a["name"][1:]}(request.{a["name"]}());'
                        for a in blueprint['entities'][0]['attributes'] if a['name'] != 'id')
    service_interface = module / 'src/main/java/com/example/probe/service/ItemService.java'
    source = service_interface.read_text(encoding='utf-8')
    service_interface.write_text(source.rsplit('}', 1)[0] + '    ItemResponse update(Long id, CreateItemRequest request);\n}\n', encoding='utf-8')
    service_implementation = module / 'src/main/java/com/example/probe/service/impl/ItemServiceImpl.java'
    source = service_implementation.read_text(encoding='utf-8')
    service_implementation.write_text(source.rsplit('}', 1)[0] + '''
    @Override
    public ItemResponse update(Long id, CreateItemRequest request) {
        var item = repository.findById(id).orElseThrow(() -> new ResourceNotFoundException("Item not found: " + id));
''' + setters + '''
        return ItemResponse.fromEntity(repository.save(item));
    }
}
''', encoding='utf-8')
    update_controller = module / 'src/main/java/com/example/probe/controller/FixtureUpdateController.java'
    update_controller.write_text('''package com.example.probe.controller;
import com.example.probe.model.dto.CreateItemRequest;
import com.example.probe.model.dto.ItemResponse;
import com.example.probe.service.ItemService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

@RestController
public class FixtureUpdateController {
    private final ItemService service;
    public FixtureUpdateController(ItemService service) { this.service = service; }
    @PutMapping("/api/v1/items/{id}")
    public ItemResponse update(@PathVariable Long id, @Valid @RequestBody CreateItemRequest request) {
        return service.update(id, request);
    }
}
''', encoding='utf-8')
    # Same source SQL in all callers, including standalone acceptance.
    (ws / 'schema.sql').write_text(schema_sql_from_draft(
        SimpleNamespace(entities=_entities_from_blueprint(blueprint)), database), encoding='utf-8')
    if seed:
        (ws / 'data.sql').write_text("INSERT INTO inventory_records(name,amount,requested_at) VALUES ('Semilla',7.50,'2026-10-04 10:00:00');\n", encoding='utf-8')
    if assets:
        generate_all_devops_assets(str(ws), identity or ws.name, 'probe-service',
                                  db_engine=database, host_port=host_port)
    source_files = [p for p in module.rglob('*') if p.is_file() and
                    (p.name in {'pom.xml', 'build.gradle', 'settings.gradle'} or 'src' in p.relative_to(module).parts)]
    source_files += [p for p in (ws / 'schema.sql', ws / 'data.sql') if p.exists()]
    hashes = {p.relative_to(ws).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(set(source_files))}
    manifest = {'catalogVersion': CATALOG_VERSION, 'build': build, 'database': database,
                'buildDirectory': layout, 'seed': seed, 'files': hashes,
                'execution': 'NOT_EXECUTED', 'offlineVerified': False,
                'crudPath': '/api/v1/items', 'fixtureOnlyUpdateEndpoint': True,
                'validPayload': {'name': 'Fixture'},
                'invalidPayload': {'name': ''}}
    if seed:
        manifest['validPayload'].update(amount=12.34, requestedAt='2026-10-04T12:00:00')
    (ws / 'FIXTURE_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--build', choices=BUILDS, default='maven')
    parser.add_argument('--database', choices=DATABASES, default='H2')
    parser.add_argument('--seed', action='store_true')
    parser.add_argument('--layout', choices=('.', 'bootstrap'), default='.')
    args = parser.parse_args()
    manifest = create_fixture(args.destination, args.build, args.database, seed=args.seed, layout=args.layout)
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
