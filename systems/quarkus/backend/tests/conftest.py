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
def clean_owned_test_orphans(setup_test_db):
    """Only the disposable suite DB: legacy fixtures delete sessions through raw SQL."""
    from app.models.reliability import DraftRevision,SessionConfiguration,PipelineOperation,ArtifactProvenance,VerificationRun,AuditRun,DeploymentOperation,RepairAttempt,SessionEvent
    from app.models.session import GenerationSessionDB
    def cleanup():
        with SessionLocal(bind=setup_test_db) as db:
            existing=db.query(GenerationSessionDB.id)
            for model in (SessionEvent,RepairAttempt,DeploymentOperation,AuditRun,VerificationRun,ArtifactProvenance,PipelineOperation,DraftRevision,SessionConfiguration):
                db.query(model).filter(~model.session_id.in_(existing)).delete(synchronize_session=False)
            db.commit()
    cleanup()
    yield
    cleanup()
