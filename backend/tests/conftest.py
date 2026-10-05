import os
import tempfile
from pathlib import Path
import pytest
from sqlalchemy import create_engine
import app.models.session as session_module
from app.models.session import Base, SessionLocal

# These pre-authentication API suites exercise their endpoint contracts, not login.
# Use the real loopback MVP endpoint; never bypass middleware or fabricate cookies.
_LEGACY_AUTHENTICATED_SUITES = {
    'test_app_examples', 'test_artifact_retrieval', 'test_code_generation_module',
    'test_e2e_flow', 'test_qe_api_surface', 'test_qe_injection_guard',
    'test_qe_specification_persistence', 'test_routes_architecture',
    'test_routes_artifact', 'test_routes_devops', 'test_routes_llm',
    'test_routes_orchestrator', 'test_routes_publish', 'test_routes_requirements',
    'test_routes_security', 'test_routes_session', 'test_routes_spec',
    'test_routes_tests',
}


@pytest.fixture(autouse=True)
def legacy_endpoint_authentication(request, monkeypatch, tmp_path):
    module = request.module
    if module.__name__.split('.')[-1] not in _LEGACY_AUTHENTICATED_SUITES:
        return
    from fastapi.testclient import TestClient
    from app.config import settings
    monkeypatch.setenv('STUDIO_AUTO_LOGIN', 'true')
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path / 'workspaces'))
    monkeypatch.setattr(settings, 'SPECIFICATION_DIR', str(tmp_path / 'specifications'))

    def authenticated_client(application, **kwargs):
        kwargs.update(base_url='http://localhost', client=('127.0.0.1', 50000))
        result = TestClient(application, **kwargs)
        assert result.post('/api/v1/auth/mvp').status_code == 200
        return result

    original = getattr(module, 'client', None)
    if isinstance(original, TestClient):
        monkeypatch.setattr(module, 'client', authenticated_client(original.app,
            raise_server_exceptions=original.raise_server_exceptions if hasattr(original, 'raise_server_exceptions') else False))
    if hasattr(module, 'TestClient'):
        monkeypatch.setattr(module, 'TestClient', authenticated_client)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Isolates pytest database to a temporary SQLite database,
    preventing any test sessions from polluting or leaving running sessions in studio.db,
    while maintaining full thread-safety across concurrent background threads.
    """
    temp_dir = tempfile.TemporaryDirectory()
    test_db_path = Path(temp_dir.name) / "test_studio.db"
    test_db_url = f"sqlite:///{test_db_path.as_posix()}"

    test_engine = create_engine(
        test_db_url,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    SessionLocal.configure(bind=test_engine)
    session_module.engine = test_engine

    yield test_engine

    try:
        temp_dir.cleanup()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def no_outbound_telemetry(tmp_path, monkeypatch):
    """Keep the suite hermetic: no test may reach the telemetry destination over the wire.

    ``cost/mlflow_sink.py`` mirrors every recorded LLM call to ``MLFLOW_TRACKING_URI``
    (default ``http://localhost:5000``). Its own tests fake the ``mlflow`` module, but any
    test that drives a call through the real recording seam -- the cost-recording suite
    does, deliberately, because that seam is the thing under test -- reaches the sink for
    real. With MLflow's stock HTTP defaults (120 s timeout, 5 retries) that blocked the
    whole suite for minutes on a host with no tracking server, so the suite could not be
    run to completion and coverage could not be measured at all.

    The destination is redirected to a throwaway **local** file store rather than being
    stubbed out. Stubbing the mirror would have made
    ``test_the_local_store_is_written_even_when_the_mirror_is_absent`` vacuous -- it
    asserts that the mirror really was consulted -- so the seam is left intact and only
    the address is changed. The address is patched on the setting, not on the module's
    ``_tracking_uri`` helper, so the helper itself stays under test.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", (tmp_path / "mlruns").as_uri())

