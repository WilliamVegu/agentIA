import pytest
from integration.runtime_data_safety_cases import run_db_conservation


@pytest.mark.parametrize('engine_name', ['POSTGRESQL', 'MYSQL'])
def test_real_stop_restart_preserves_records(engine_name, tmp_path, monkeypatch):
    run_db_conservation(engine_name, tmp_path, monkeypatch)


def test_cleanup_needs_explicit_current_resource_preview(monkeypatch):
    from app.models.execution import ExecutionMode
    from app.services import runtime_lifecycle
    monkeypatch.setattr(runtime_lifecycle, 'execution_mode', lambda *a: ExecutionMode.DOCKER)
    monkeypatch.setattr(runtime_lifecycle, 'owned_resources', lambda *a: [])
    with pytest.raises(ValueError, match='deleteData'):
        runtime_lifecycle.cleanup_local('test-preview')
    with pytest.raises(ValueError, match='confirmation'):
        runtime_lifecycle.cleanup_local('test-preview', True)
