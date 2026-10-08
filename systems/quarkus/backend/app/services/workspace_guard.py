import os
import re
import stat
import tempfile
from pathlib import Path, PureWindowsPath
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

    lexical_root = Path(settings.WORKSPACE_DIR).absolute()
    _reject_links(lexical_root / session_id, lexical_root)
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

        if not sess_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found.",
            )

    return ws_path


def _reject_links(path: Path, root: Path):
    current = path
    while True:
        try:
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise HTTPException(400, 'Linked/reparse workspace paths are not permitted')
        except FileNotFoundError:
            pass
        if current == root:
            break
        if current == current.parent:
            raise HTTPException(400, 'Workspace path escaped its root')
        current = current.parent


def validate_relative_file(file_path: str) -> Path:
    if not isinstance(file_path, str) or not file_path or any(ord(char) < 32 for char in file_path):
        raise HTTPException(400, 'A relative file path is required')
    windows = PureWindowsPath(file_path)
    normalized = file_path.replace('\\', '/')
    parts = normalized.split('/')
    if windows.drive or windows.root or normalized.startswith('/') or ':' in normalized or '%' in normalized:
        raise HTTPException(400, 'Absolute, drive, UNC, ADS or encoded paths are not permitted')
    if any(part in ('', '.', '..') or part.rstrip(' .') != part for part in parts):
        raise HTTPException(400, 'Invalid relative path')
    if any(part.lower() in ('.git', '.agentia-runtime', '.operation-locks') for part in parts):
        raise HTTPException(400, 'Internal state is not an editable source file')
    devices = re.compile(r'^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', re.I)
    if any(devices.match(part) for part in parts):
        raise HTTPException(400, 'Device paths are not permitted')
    return Path(*parts)


def resolve_workspace_file(session_id: str, file_path: str, *, require_exists=False) -> Path:
    workspace = get_validated_workspace_path(session_id, require_exists=True)
    root = Path(settings.WORKSPACE_DIR).resolve()
    _reject_links(Path(settings.WORKSPACE_DIR).absolute() / session_id, Path(settings.WORKSPACE_DIR).absolute())
    relative = validate_relative_file(file_path)
    candidate = workspace / relative
    _reject_links(candidate, root)
    resolved = candidate.resolve()
    if not resolved.is_relative_to(workspace) or resolved == workspace:
        raise HTTPException(400, 'Path outside session workspace')
    if require_exists and not io_path(resolved).is_file():
        raise HTTPException(404, 'Source file not found')
    return resolved


def io_path(path: Path) -> Path:
    value = str(path.absolute())
    if os.name == 'nt' and not value.startswith('\\\\?\\'):
        return Path('\\\\?\\' + value)
    return path


def atomic_write_workspace_file(session_id: str, file_path: str, content: str) -> Path:
    target = resolve_workspace_file(session_id, file_path)
    io_path(target.parent).mkdir(parents=True, exist_ok=True)
    resolve_workspace_file(session_id, file_path)
    descriptor, temporary = tempfile.mkstemp(prefix='.agentia-edit-', suffix='.tmp', dir=io_path(target.parent))
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        resolve_workspace_file(session_id, file_path)
        os.replace(temporary, io_path(target))
    finally:
        if os.path.exists(temporary):
            # Only unlink our temporary file after checking its parent again.
            resolve_workspace_file(session_id, file_path)
            os.unlink(temporary)
    return target
