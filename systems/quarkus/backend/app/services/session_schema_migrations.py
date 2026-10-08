"""Explicit SQLite schema upgrade with a backup and an auditable version."""
from pathlib import Path
import hashlib
import json
import logging
import sqlite3
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)
VERSION = 1
ADDITIONS = {
    'execution_mode': "VARCHAR(20) NOT NULL DEFAULT 'SOURCE_ONLY'",
    'database_engine': "VARCHAR(20) NOT NULL DEFAULT 'POSTGRESQL'",
    'current_lifecycle_phase': "VARCHAR(50) DEFAULT 'INITIAL'",
    'lifecycle_mode': "VARCHAR(50) DEFAULT 'GUIDED_STEP'",
    'phase_progress_json': 'TEXT',
    'generation_journal_json': 'TEXT',
    'artifact_provenance_json': 'TEXT',
    'verification_metrics_json': 'TEXT',
    'cost_record_json': 'TEXT',
    'revision_id': 'VARCHAR(36)',
    'configuration_version': 'INTEGER NOT NULL DEFAULT 0',
    'operation_version': 'INTEGER NOT NULL DEFAULT 0',
}


def migrate_sessions(engine):
    from app.models.session import Base
    from app.models import reliability  # noqa: F401 -- register durable tables
    owned = {item.__table__.name for item in vars(reliability).values()
             if isinstance(item, type) and item.__module__ == reliability.__name__ and hasattr(item, '__table__')}
    schema = [(table.name, [(column.name, str(column.type)) for column in table.columns])
              for table in Base.metadata.sorted_tables if table.name in owned]
    checksum = hashlib.sha256(json.dumps([VERSION, ADDITIONS, schema], sort_keys=True).encode()).hexdigest()
    tables = inspect(engine).get_table_names()
    if 'schema_migrations' in tables:
        with engine.connect() as connection:
            previous = connection.execute(text('SELECT checksum FROM schema_migrations WHERE migration_version=:v'), {'v': VERSION}).scalar()
        if previous:
            if previous != checksum:
                raise RuntimeError('Migration checksum mismatch; mutations stopped')
            return {'applied': [], 'backup': None, 'checksum': checksum}

    backup = None
    if engine.dialect.name == 'sqlite' and tables and engine.url.database not in (None, ':memory:'):
        path = Path(engine.url.database).resolve()
        backup_path = path.with_name(path.name + f'.pre-reliability-v{VERSION}.bak')
        if backup_path.exists():
            # Never overwrite a previous recovery point.
            import uuid
            backup_path = path.with_name(path.name + f'.pre-reliability-v{VERSION}-{uuid.uuid4().hex}.bak')
        with engine.connect() as source, sqlite3.connect(str(backup_path)) as destination:
            source.connection.driver_connection.backup(destination)
        backup = str(backup_path)

    with engine.begin() as connection:
        if engine.dialect.name == 'sqlite':
            connection.exec_driver_sql('BEGIN IMMEDIATE')
        if 'generation_sessions' in tables:
            columns = {column['name'] for column in inspect(connection).get_columns('generation_sessions')}
            for name, definition in ADDITIONS.items():
                if name not in columns:
                    connection.execute(text(f'ALTER TABLE generation_sessions ADD COLUMN {name} {definition}'))
        Base.metadata.create_all(bind=connection)
        connection.execute(text('INSERT INTO schema_migrations (migration_version,checksum,applied_at) VALUES (:v,:c,CURRENT_TIMESTAMP)'), {'v': VERSION, 'c': checksum})
    logger.info('Session migration %s applied; backup=%s', VERSION, backup)
    return {'applied': [VERSION], 'backup': backup, 'checksum': checksum}
