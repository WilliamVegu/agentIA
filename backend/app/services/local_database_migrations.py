"""Package authored SQL as once-only Liquibase migrations; never overwrite SQL edits."""
from pathlib import Path
import hashlib
import json
from types import SimpleNamespace
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
from app.services.lifecycle_artifacts import blueprint_from_generated_code, _entities_from_blueprint
from app.services.model_sql_service import schema_sql_from_draft


def write_migrations(workspace, database):
    database = str(database).upper()
    if database not in {'H2', 'POSTGRESQL', 'MYSQL'}:
        raise ValueError('Motor de migración no admitido')
    ws = Path(workspace)
    recovered = blueprint_from_generated_code(ws)
    draft = SimpleNamespace(entities=_entities_from_blueprint(recovered))
    # Authored root scripts win. Derived SQL fills only a missing file.
    schema = ws / 'schema.sql'
    schema_content = schema.read_text(encoding='utf-8') if schema.exists() else schema_sql_from_draft(draft, database)
    module = ws / 'bootstrap' if any((ws / 'bootstrap' / n).is_file() for n in ('pom.xml', 'build.gradle', 'build.gradle.kts')) else ws
    changes = module / 'src/main/resources/db/changelog'
    changes.mkdir(parents=True, exist_ok=True)

    def preserve(path, content):
        if path.exists():
            if path.read_text(encoding='utf-8') != content:
                raise ValueError(f'Migración existente diferente: {path.name}. Añada una nueva versión; no se modifica una migración publicada.')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')

    files = [('001-schema.sql', schema_content)]
    seed = ws / 'data.sql'
    if seed.is_file() and seed.read_text(encoding='utf-8').strip():
        files.append(('002-seed.sql', seed.read_text(encoding='utf-8')))
    header = ('<?xml version="1.0" encoding="UTF-8"?>\n'
              '<databaseChangeLog xmlns="http://www.liquibase.org/xml/ns/dbchangelog" '
              'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
              'xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog '
              'http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.24.xsd">\n')
    body = ''.join(f'  <changeSet id="{name[:-4]}" author="agentia">\n'
                   f'    <sqlFile path="{escape(name)}" relativeToChangelogFile="true" splitStatements="true" stripComments="true"/>\n'
                   '  </changeSet>\n' for name, _ in files)
    master = changes / 'db.changelog-master.xml'
    master_content = header + body + '</databaseChangeLog>\n'
    if master.exists():
        # Keep appended versions, while refusing changes to the initial changesets.
        try:
            existing = ET.fromstring(master.read_text(encoding='utf-8'))
            expected = ET.fromstring(master_content)
        except ET.ParseError as exc:
            raise ValueError('Changelog existente inválido; no se sobrescribe.') from exc
        if existing.tag != expected.tag:
            raise ValueError('Changelog existente incompatible; no se sobrescribe.')
        expected_ids = {change.attrib['id'] for change in expected}
        if any(node.attrib.get('id') in {'001-schema', '002-seed'}
               and node.attrib.get('id') not in expected_ids for node in existing):
            raise ValueError('Migración inicial retirada. Añada una nueva versión; no se omiten semillas publicadas.')
        for change in expected:
            candidates = [node for node in existing if node.attrib.get('id') == change.attrib['id'] and node.attrib.get('author') == change.attrib['author']]
            if len(candidates) != 1 or candidates[0].attrib != change.attrib or [(n.tag, n.attrib) for n in candidates[0]] != [(n.tag, n.attrib) for n in change]:
                raise ValueError('Migración inicial modificada en el changelog. Añada una nueva versión.')
        master_content = master.read_text(encoding='utf-8')
    # Properties supplement generated YAML without replacing its datasource configuration.
    props = module / 'src/main/resources/application.properties'
    values = ('spring.liquibase.change-log=classpath:db/changelog/db.changelog-master.xml\n'
              'spring.jpa.hibernate.ddl-auto=validate\nspring.sql.init.mode=never\n')
    required = dict(line.split('=', 1) for line in values.splitlines())
    if props.exists():
        configured = {}
        for line in props.read_text(encoding='utf-8').splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith(('#', '!')):
                key, separator, value = stripped.partition('=')
                if separator:
                    configured[key.strip()] = value.strip()
        if any(configured.get(key) != value for key, value in required.items()):
            raise ValueError('application.properties existente: configure explícitamente changelog, ddl-auto=validate y sql.init.mode=never; no se sobrescribe.')
    # Embedded H2 slice tests exercise a schema matching the actual Java fields,
    # independently of the production SQL dialect. They do not apply production seeds.
    test_changes = module / 'src/test/resources/db/changelog'
    test_xml = header + '  <changeSet id="001-schema-test" author="agentia">\n    <sqlFile path="001-schema-test.sql" relativeToChangelogFile="true"/>\n  </changeSet>\n</databaseChangeLog>\n'
    test_props = module / 'src/test/resources/application.properties'
    outputs = [(changes / name, content) for name, content in files]
    outputs += [(master, master_content), (test_changes / '001-schema-test.sql', schema_sql_from_draft(draft, 'H2')),
                (test_changes / 'db.changelog-test.xml', test_xml),
                (test_props, 'spring.liquibase.change-log=classpath:db/changelog/db.changelog-test.xml\nspring.jpa.hibernate.ddl-auto=validate\nspring.sql.init.mode=never\n')]
    if not props.exists():
        outputs.append((props, values))
    seal = changes / 'LOCAL_MIGRATIONS.json'
    metadata = {'formatVersion': 1, 'database': database,
                'files': {name: hashlib.sha256(content.encode('utf-8')).hexdigest() for name, content in files},
                'seedPolicy': 'ONCE_PER_DATABASE'}
    if seal.exists():
        try:
            previous = json.loads(seal.read_text(encoding='utf-8'))
        except (ValueError, OSError) as exc:
            raise ValueError('Registro de migraciones inválido; no se sobrescribe.') from exc
        if previous != metadata:
            raise ValueError('Motor o contenido de migraciones publicado diferente. Añada una nueva versión; cambiar motor requiere un proyecto/base nuevos.')
    outputs.append((seal, json.dumps(metadata, indent=2) + '\n'))
    if not schema.exists():
        outputs.append((schema, schema_content))
    # Check all conflicts before copying any migration or properties file.
    for path, content in outputs:
        if path.exists() and path.read_text(encoding='utf-8') != content:
            raise ValueError(f'Migración existente diferente: {path.name}. Añada una nueva versión.')
    for path, content in outputs:
        preserve(path, content)
