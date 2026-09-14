from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.config import settings
from app.models.session import SessionLocal, GenerationSessionDB
from app.services.export_service import create_project_zip
from app.services.git_service import publish_to_git
from app.services.security_service import audit_workspace

router = APIRouter(prefix="/sessions", tags=["Export & Publish"])

class PublishRequest(BaseModel):
    repositoryUrl: str = Field(..., description="Target Git repository URL")
    branchName: str = Field(..., description="Feature branch name e.g. feature/001-order-service")
    gitToken: Optional[str] = Field(None, description="Ephemeral Personal Access Token (PAT)")
    commitMessage: Optional[str] = Field(
        default="feat: initial autonomous generation and verified test suite",
        description="Git commit message"
    )

class PublishResponse(BaseModel):
    branchUrl: str
    commitHash: str
    pullRequestUrl: Optional[str] = None
    branchName: str

@router.get("/{session_id}/export")
async def export_session_project(session_id: str):
    """Downloads the complete synthesized project as a standalone ZIP archive."""
    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        service_name = sess.spec_name or "microservice"
    finally:
        db.close()

    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    if not ws_path.exists() or not ws_path.is_dir():
        raise HTTPException(status_code=404, detail="Project workspace directory not found")

    # Enforce Quality Gate guard (Constitution Principle V & Feature 006)
    audit = audit_workspace(str(ws_path), session_id, service_name)
    if not audit.qualityGate.canExport:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot export artifact: Quality Gate is BLOCKED. {audit.qualityGate.summaryMessage}"
        )

    zip_bytes = create_project_zip(str(ws_path))

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{service_name}.zip"'
        }
    )

@router.post("/{session_id}/publish", response_model=PublishResponse)
async def publish_session_project(session_id: str, payload: PublishRequest):
    """Publishes the project to a dedicated Git feature branch using ephemeral credentials."""
    db = SessionLocal()
    service_name = "microservice"
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        if sess.spec_name:
            service_name = sess.spec_name
    finally:
        db.close()

    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    if not ws_path.exists() or not ws_path.is_dir():
        raise HTTPException(status_code=404, detail="Project workspace directory not found")

    # Enforce Quality Gate guard before publishing to Git
    audit = audit_workspace(str(ws_path), session_id, service_name)
    if not audit.qualityGate.canExport:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot publish to Git: Quality Gate is BLOCKED. {audit.qualityGate.summaryMessage}"
        )

    try:
        result = publish_to_git(
            workspace_path=str(ws_path),
            repository_url=payload.repositoryUrl,
            branch_name=payload.branchName,
            git_token=payload.gitToken,
            commit_message=payload.commitMessage or "feat: initial autonomous generation"
        )
        return PublishResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Git publishing failed: {str(e)}")

