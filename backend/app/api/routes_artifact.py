import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Response, status

from app.config import settings
from app.models.artifact import ArtifactSummary, ArtifactFileType, VerificationMetrics
from app.models.session import SessionLocal, GenerationSessionDB, SessionStatus
from app.api.routes_session import SESSION_GENERATION_STATE

router = APIRouter(prefix="/sessions", tags=["Artifacts"])

def _detect_file_type(rel_path: str, full_path: Path) -> ArtifactFileType:
    norm_path = rel_path.replace("\\", "/")
    if norm_path.endswith("pom.xml"):
        return ArtifactFileType.POM_XML
    elif norm_path.endswith((".yml", ".yaml")):
        return ArtifactFileType.YAML_CONFIG
    elif "/src/test/" in norm_path or norm_path.startswith("src/test/"):
        return ArtifactFileType.TEST_SOURCE
    elif norm_path.endswith(".java"):
        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
            if "public record " in content:
                return ArtifactFileType.JAVA_RECORD
        except Exception:
            pass
        return ArtifactFileType.JAVA_SOURCE
    return ArtifactFileType.JAVA_SOURCE

@router.get("/{session_id}/artifacts", response_model=List[ArtifactSummary])
async def list_artifacts(session_id: str):
    """Returns the full hierarchical file tree of generated artifacts."""
    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
    finally:
        db.close()

    from app.services.workspace_guard import get_validated_workspace_path
    ws_path = get_validated_workspace_path(session_id, require_exists=True)
    if not ws_path.exists() or not ws_path.is_dir():
        return []

    artifacts: List[ArtifactSummary] = []
    ignored_dirs = {".git", "target", ".idea", "__pycache__", ".m2"}

    for root, dirs, files in os.walk(ws_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not (Path(root) / d).is_symlink() and not getattr((Path(root) / d).lstat(), "st_file_attributes", 0) & 0x400]
        for file in files:
            full_file_path = Path(root) / file
            try:
                rel_path = str(full_file_path.relative_to(ws_path)).replace("\\", "/")
                from app.services.workspace_guard import resolve_workspace_file
                full_file_path = resolve_workspace_file(session_id, rel_path, require_exists=True)
                file_type = _detect_file_type(rel_path, full_file_path)
                size_bytes = full_file_path.stat().st_size
                artifacts.append(
                    ArtifactSummary(
                        id=f"{session_id}:{rel_path}",
                        sessionId=session_id,
                        relativePath=rel_path,
                        fileType=file_type,
                        sizeBytes=size_bytes
                    )
                )
            except Exception:
                continue

    artifacts.sort(key=lambda a: a.relativePath)
    return artifacts

@router.get("/{session_id}/artifacts/content")
async def get_artifact_content(session_id: str, path: str = Query(..., description="Relative path of file")):
    """Returns the raw source code text of a specific artifact."""
    from app.services.workspace_guard import resolve_workspace_file, io_path
    target_file = io_path(resolve_workspace_file(session_id, path, require_exists=True))
    try:
        content = target_file.read_text(encoding="utf-8")
        return Response(content=content, media_type="text/plain; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read artifact: {str(e)}")

@router.get("/{session_id}/metrics", response_model=VerificationMetrics)
async def get_verification_metrics(session_id: str):
    """Returns test execution metrics for the session."""
    gen_state = SESSION_GENERATION_STATE.get(session_id)
    if gen_state and "test_metrics" in gen_state:
        return VerificationMetrics(**gen_state["test_metrics"])

    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")

        # Feature 012 / H08: deserialize real persisted verification metrics if available
        if sess.verification_metrics_json:
            try:
                import json
                persisted = json.loads(sess.verification_metrics_json)
                return VerificationMetrics(**persisted)
            except Exception:
                pass

        # If not executed or missing, return honest 0 tests, never fake mock numbers
        return VerificationMetrics(
            totalTests=0,
            passedTests=0,
            failedTests=0,
            executionDurationMs=0,
            allPassed=False,
        )
    finally:
        db.close()

