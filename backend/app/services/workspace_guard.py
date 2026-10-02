import os
import re
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, status

from app.config import settings


def get_validated_workspace_path(session_id: str, require_exists: bool = False) -> Path:
    """
    Validates session_id for path traversal attempts and ensures the workspace path
    resolves strictly inside settings.WORKSPACE_DIR.

    Optionally verifies that the session exists in the database or workspace on disk.
    Raises HTTPException(400) on path traversal attempts or invalid format.
    Raises HTTPException(404) if require_exists is True and the session is not found.
    """
    if not session_id or not isinstance(session_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid sessionId is required.",
        )

    # Reject traversal characters or control sequences
    if ".." in session_id or "/" in session_id or "\\" in session_id or "%" in session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sessionId: Path traversal attempt detected.",
        )

    # Check safe alphanumeric/hyphen pattern (standard UUID or kebab-case id)
    if not re.match(r"^[A-Za-z0-9_-]+$", session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sessionId format.",
        )

    ws_root = Path(settings.WORKSPACE_DIR).resolve()
    ws_path = (ws_root / session_id).resolve()

    try:
        common = os.path.commonpath([str(ws_root), str(ws_path)])
        if common != str(ws_root) or ws_path == ws_root:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid workspace path containment.",
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cross-drive path traversal detected.",
        )

    if require_exists:
        from app.models.session import GenerationSessionDB, SessionLocal
        db = SessionLocal()
        sess_exists = False
        try:
            sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
            if sess:
                sess_exists = True
        finally:
            db.close()

        if not sess_exists and not ws_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found.",
            )

    return ws_path
