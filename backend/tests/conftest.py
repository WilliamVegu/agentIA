import os
import tempfile
from pathlib import Path
import pytest
from sqlalchemy import create_engine
import app.models.session as session_module
from app.models.session import Base, SessionLocal

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

