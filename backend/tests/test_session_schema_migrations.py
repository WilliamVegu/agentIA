from pathlib import Path
import pytest
from sqlalchemy import create_engine, text


def test_migration_is_additive_backed_up_and_idempotent(tmp_path):
    from app.services.session_schema_migrations import migrate_sessions
    path = tmp_path / 'legacy.db'
    engine = create_engine(f'sqlite:///{path.as_posix()}')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE generation_sessions (id TEXT PRIMARY KEY, spec_id TEXT, spec_name TEXT, status TEXT)'))
        connection.execute(text("INSERT INTO generation_sessions VALUES ('legacy','spec','Original','BLOCKED')"))
    first = migrate_sessions(engine)
    assert first['applied'] == [1]
    assert Path(first['backup']).exists()
    assert migrate_sessions(engine)['applied'] == []
    with engine.connect() as connection:
        assert connection.execute(text('SELECT spec_name,status FROM generation_sessions')).one() == ('Original','BLOCKED')
        columns = {row[1] for row in connection.execute(text('PRAGMA table_info(generation_sessions)'))}
        assert {'execution_mode','database_engine','revision_id','configuration_version'} <= columns
        assert connection.execute(text('SELECT count(*) FROM verification_runs')).scalar_one() == 0
        assert connection.execute(text('SELECT count(*) FROM draft_revisions')).scalar_one() == 0
    engine.dispose()


def test_migration_checksum_error_stops_mutations(tmp_path):
    from app.services.session_schema_migrations import migrate_sessions
    engine = create_engine(f'sqlite:///{(tmp_path/"test.db").as_posix()}')
    migrate_sessions(engine)
    with engine.begin() as connection:
        connection.execute(text("UPDATE schema_migrations SET checksum='invalid'"))
    with pytest.raises(RuntimeError, match='checksum'):
        migrate_sessions(engine)
    engine.dispose()


def test_new_database_and_legacy_failed_not_certified(tmp_path):
    from app.services.session_schema_migrations import migrate_sessions
    engine = create_engine(f'sqlite:///{(tmp_path/"test.db").as_posix()}')
    migrate_sessions(engine)
    from app.models.session import Base
    assert {'draft_revisions','session_events','pipeline_operations','repair_attempts'} <= set(Base.metadata.tables)
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM verification_runs')).scalar_one() == 0
    engine.dispose()


def test_failed_migration_rolls_back_and_can_be_retried(tmp_path, monkeypatch):
    from app.services.session_schema_migrations import migrate_sessions
    from app.models.session import Base
    engine = create_engine(f'sqlite:///{(tmp_path/"partial.db").as_posix()}')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE generation_sessions (id TEXT PRIMARY KEY, status TEXT)'))
        connection.execute(text("INSERT INTO generation_sessions VALUES ('original','BLOCKED')"))
    native = Base.metadata.create_all
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            raise RuntimeError('migration interrupted')
        patch.setattr(Base.metadata, 'create_all', fail)
        with pytest.raises(RuntimeError, match='interrupted'):
            migrate_sessions(engine)
    with engine.connect() as connection:
        columns = {row[1] for row in connection.execute(text('PRAGMA table_info(generation_sessions)'))}
        assert 'execution_mode' not in columns
        assert connection.execute(text('SELECT status FROM generation_sessions')).scalar_one() == 'BLOCKED'
    assert migrate_sessions(engine)['applied'] == [1]
    engine.dispose()
