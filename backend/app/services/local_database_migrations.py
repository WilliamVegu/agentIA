"""Package authored SQL as once-only Liquibase migrations; never overwrite SQL edits."""
from pathlib import Path
from types import SimpleNamespace
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
from app.services.lifecycle_artifacts import blueprint_from_generated_code, _entities_from_blueprint
from app.services.model_sql_service import schema_sql_from_draft


def write_migrations(workspace, database):
    ws = Path(workspace)
    recovered = blueprint_from_generated_code(ws)
    draft = SimpleNamespace(entities=_entities_from_blueprint(recovered))
    # Authored root scripts win. Derived SQL fills only a missing file.
    schema = ws / 'schema.sql'
    if not schema.exists():
        schema.write_text(schema_sql_from_draft(draft, database), encoding='utf-8')
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

    files = [('001-schema.sql', schema.read_text(encoding='utf-8'))]
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
        for change in expected:
            candidates = [node for node in existing if node.attrib.get('id') == change.attrib['id'] and node.attrib.get('author') == change.attrib['author']]
            if len(candidates) != 1 or candidates[0].attrib != change.attrib or [(n.tag, n.attrib) for n in candidates[0]] != [(n.tag, n.attrib) for n in change]:
                raise ValueError('Migración inicial modificada en el changelog. Añada una nueva versión.')
        master_content = master.read_text(encoding='utf-8')
    # Properties supplement generated YAML without replacing its datasource configuration.
    props = module / 'src/main/resources/application.properties'
    values = ('spring.liquibase.change-log=classpath:db/changelog/db.changelog-master.xml\n'
              'spring.jpa.hibernate.ddl-auto=validate\nspring.sql.init.mode=never\n')
    if props.exists() and 'spring.liquibase.change-log=classpath:db/changelog/db.changelog-master.xml' not in props.read_text(encoding='utf-8'):
        raise ValueError('application.properties existente: configure explícitamente el changelog; no se sobrescribe.')
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
    # Check all conflicts before copying any migration or properties file.
    for path, content in outputs:
        if path.exists() and path.read_text(encoding='utf-8') != content:
            raise ValueError(f'Migración existente diferente: {path.name}. Añada una nueva versión.')
    for path, content in outputs:
        preserve(path, content)
