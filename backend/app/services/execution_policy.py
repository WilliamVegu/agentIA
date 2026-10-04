"""Resolve persisted session policy without probing Docker for source delivery."""
from pathlib import Path
from app.models.execution import ExecutionMode


def execution_mode(session_id=None, workspace_path=None, explicit=None) -> ExecutionMode:
    if explicit is not None:
        return ExecutionMode(explicit)
    # Import lazily: the session models also expose this enum in their schemas.
    from app.models.session import SessionLocal, GenerationSessionDB
    identity = session_id or (Path(workspace_path).name if workspace_path else None)
    if identity:
        with SessionLocal() as db:
            row = db.get(GenerationSessionDB, identity)
            if row:
                return ExecutionMode(row.execution_mode or ExecutionMode.SOURCE_ONLY)
    return ExecutionMode.SOURCE_ONLY
