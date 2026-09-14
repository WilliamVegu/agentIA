from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.config import settings
from app.models.devops import (
    DeploymentStatus,
    DevOpsDeployRequest,
    DevOpsManifestBundle,
    LocalDeploymentSession,
    SmokeTestResult,
)
from app.models.session import GenerationSessionDB, SessionLocal
from app.services.devops_service import generate_all_devops_assets
from app.services.docker_service import (
    deploy_local,
    get_deployment_logs,
    get_deployment_status,
    run_smoke_test,
    stop_deployment,
    stream_logs,
)
from app.services.security_service import audit_workspace

router = APIRouter(prefix="/devops", tags=["DevOps, Containerization & Deployment"])


def _resolve_session_context(session_id: str):
    """Retrieves session entity, workspace directory, and service name from DB."""
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

    return ws_path, service_name


@router.post("/{session_id}/generate", response_model=DevOpsManifestBundle)
async def generate_manifests(
    session_id: str,
    db_engine: Optional[str] = "POSTGRESQL",
    host_port: Optional[int] = 8080
):
    """Generates all Docker, Compose, CI/CD, and Kubernetes assets for the workspace session."""
    ws_path, service_name = _resolve_session_context(session_id)

    # Enforce Quality Gate check (Constitution Principle V & Feature 006)
    audit = audit_workspace(str(ws_path), session_id, service_name)
    if not audit.qualityGate.canExport:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot generate DevOps manifests: Quality Gate is BLOCKED. {audit.qualityGate.summaryMessage}",
        )

    bundle = generate_all_devops_assets(
        workspace_dir=str(ws_path),
        session_id=session_id,
        service_name=service_name,
        db_engine=db_engine or "POSTGRESQL",
        host_port=host_port or 8080,
    )
    return bundle


@router.post("/{session_id}/deploy", response_model=LocalDeploymentSession)
async def deploy_container(session_id: str, payload: Optional[DevOpsDeployRequest] = None):
    """Initiates local Docker deployment and compose orchestration."""
    ws_path, service_name = _resolve_session_context(session_id)

    # Enforce Quality Gate check before deploying
    audit = audit_workspace(str(ws_path), session_id, service_name)
    if not audit.qualityGate.canExport:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot deploy containers: Quality Gate is BLOCKED. {audit.qualityGate.summaryMessage}",
        )

    # Ensure manifests exist; if not, generate first
    if not (ws_path / "docker-compose.yml").exists():
        generate_all_devops_assets(str(ws_path), session_id, service_name)

    host_port = payload.hostPort if payload and payload.hostPort else 8080
    rebuild = payload.rebuild if payload and payload.rebuild else False

    session_status = deploy_local(
        session_id=session_id,
        workspace_dir=str(ws_path),
        host_port=host_port,
        rebuild=rebuild,
    )
    return session_status


@router.get("/{session_id}/status", response_model=LocalDeploymentSession)
async def deployment_status(session_id: str):
    """Retrieves current container and deployment execution status."""
    return get_deployment_status(session_id)


@router.get("/{session_id}/logs/stream")
async def stream_container_logs(session_id: str):
    """Streams real-time build and execution logs via Server-Sent Events (SSE)."""
    return StreamingResponse(
        stream_logs(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{session_id}/logs")
async def get_container_logs(session_id: str):
    """Retrieves all historical container execution logs without streaming."""
    return {"logs": get_deployment_logs(session_id)}


@router.post("/{session_id}/stop", response_model=LocalDeploymentSession)
async def stop_containers(session_id: str):
    """Stops and cleans up active local containers for the session."""
    ws_path, _ = _resolve_session_context(session_id)
    return stop_deployment(session_id, str(ws_path))


@router.post("/{session_id}/smoke-test", response_model=SmokeTestResult)
async def execute_smoke_test(session_id: str, host_port: Optional[int] = 8080):
    """Executes automated post-deployment health validation against /actuator/health."""
    result = run_smoke_test(session_id, host_port=host_port or 8080)
    return result

