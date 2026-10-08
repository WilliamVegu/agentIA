from pathlib import Path
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query, Header
from fastapi.responses import StreamingResponse

from app.config import settings
from app.models.devops import (
    DeploymentStatus,
    DatabaseEngine,
    DevOpsDeployRequest,
    DevOpsManifestBundle,
    LocalDeploymentSession,
    PlaygroundProxyRequest,
    PlaygroundProxyResponse,
    PlaygroundResources,
    SmokeTestResult,
    DockerCapabilityReport,
    LocalCleanupRequest,
    LocalCancelRequest,
    LocalProjectConfiguration,
    DeploymentLogSnapshot,
)
from app.models.session import GenerationSessionDB, SessionLocal
from app.services.devops_service import generate_all_devops_assets
from app.services.docker_service import (
    deploy_local,
    get_deployment_log_snapshot,
    get_deployment_status,
    run_smoke_test,
    stop_deployment,
    stream_logs,
)
from app.services.playground_proxy import (
    PlaygroundProxyError,
    default_resource,
    discover_resources,
    forward,
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


@router.get("/{session_id}/diagnostics", response_model=DockerCapabilityReport)
async def docker_diagnostics(session_id: str):
    from app.services.docker_diagnostics import diagnose
    workspace, _ = _resolve_session_context(session_id)
    return await asyncio.to_thread(diagnose, session_id, workspace)


@router.get("/{session_id}/configuration", response_model=LocalProjectConfiguration)
async def project_configuration(session_id: str):
    from app.services.local_configuration import resolve_configuration
    workspace, _ = _resolve_session_context(session_id)
    try:
        config = resolve_configuration(workspace, session_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {key: config[key] for key in ('databaseEngine', 'hostPort', 'buildTool', 'buildDirectory')}


@router.post("/{session_id}/generate", response_model=DevOpsManifestBundle)
async def generate_manifests(
    session_id: str,
    db_engine: Optional[DatabaseEngine] = None,
    host_port: Optional[int] = Query(None, ge=1024, le=65535)
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

    try:
        bundle = generate_all_devops_assets(
            workspace_dir=str(ws_path),
            session_id=session_id,
            service_name=service_name,
            db_engine=db_engine,
            host_port=host_port,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return bundle


@router.post("/{session_id}/deploy", response_model=LocalDeploymentSession)
async def deploy_container(session_id: str, payload: Optional[DevOpsDeployRequest] = None):
    """Initiates local Docker deployment and compose orchestration."""
    ws_path, service_name = _resolve_session_context(session_id)
    from app.services.execution_policy import execution_mode
    if execution_mode(session_id).value == "SOURCE_ONLY":
        return get_deployment_status(session_id)
    from app.services.verification_policy import require_verified_session
    with SessionLocal() as db:
        require_verified_session(db.get(GenerationSessionDB, session_id))

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
    # Generation may add drivers/Actuator/manifests: old evidence cannot authorize
    # building those changed inputs, even if the first gate passed.
    with SessionLocal() as db:
        require_verified_session(db.get(GenerationSessionDB, session_id))

    with SessionLocal() as db:
        import json
        metrics = json.loads(db.get(GenerationSessionDB, session_id).verification_metrics_json or '{}')
        if not metrics.get('sourceSnapshotId'):
            raise HTTPException(403, 'Verifique de nuevo para crear un snapshot de fuentes antes de desplegar.')

    host_port = payload.hostPort if payload else None
    rebuild = payload.rebuild if payload and payload.rebuild else False

    try:
        session_status = deploy_local(
            session_id=session_id,
            workspace_dir=str(ws_path),
            host_port=host_port,
            rebuild=rebuild,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return session_status


@router.post("/{session_id}/prepare", response_model=LocalDeploymentSession)
async def prepare_environment(session_id: str):
    from app.services.execution_policy import execution_mode
    from app.services.local_preparation import prepare_local
    workspace, name = _resolve_session_context(session_id)
    if execution_mode(session_id).value == "SOURCE_ONLY":
        return get_deployment_status(session_id)
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, session_id)
        database = row.database_engine
        if row.status.value in ("RUNNING", "QUEUED"):
            raise HTTPException(409, "Espere a que termine la generación.")
    audit = audit_workspace(str(workspace), session_id, name)
    if not audit.qualityGate.canExport:
        raise HTTPException(403, audit.qualityGate.summaryMessage)
    current = get_deployment_status(session_id)
    if current.status.value in ("BUILDING", "RUNNING", "HEALTHY", "DEGRADED"):
        raise HTTPException(409, "Termine o detenga la operación actual antes de preparar.")
    from app.services.local_configuration import resolve_configuration
    try:
        database = resolve_configuration(workspace, session_id)['databaseEngine']
        generate_all_devops_assets(str(workspace), session_id, name, db_engine=database)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return prepare_local(session_id, str(workspace), database)


@router.get("/{session_id}/status", response_model=LocalDeploymentSession)
async def deployment_status(session_id: str):
    """Retrieves current container and deployment execution status."""
    _resolve_session_context(session_id)
    return get_deployment_status(session_id)


@router.get("/{session_id}/logs/stream", response_class=StreamingResponse,
            responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}})
async def stream_container_logs(session_id: str, last_event_id: Optional[str] = Header(None)):
    """Replay retained deployment logs after Last-Event-ID; not live container capture."""
    _resolve_session_context(session_id)
    cursor = 0
    if last_event_id is not None:
        if not last_event_id.isascii() or not last_event_id.isdecimal() or len(last_event_id) > 20:
            raise HTTPException(400, 'Last-Event-ID debe ser un entero no negativo de hasta 20 dígitos.')
        cursor = int(last_event_id)
    return StreamingResponse(
        stream_logs(session_id, after_id=cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{session_id}/logs", response_model=DeploymentLogSnapshot)
async def get_container_logs(session_id: str):
    """Retrieves all historical container execution logs without streaming."""
    _resolve_session_context(session_id)
    return get_deployment_log_snapshot(session_id)


@router.post("/{session_id}/stop", response_model=LocalDeploymentSession)
async def stop_containers(session_id: str):
    """Stops owned containers for the session, retaining data and resources."""
    ws_path, _ = _resolve_session_context(session_id)
    return stop_deployment(session_id, str(ws_path))


@router.post("/{session_id}/smoke-test", response_model=SmokeTestResult)
async def execute_smoke_test(session_id: str, host_port: Optional[int] = 8080):
    """Executes automated post-deployment health validation against /actuator/health."""
    result = run_smoke_test(session_id, host_port=host_port or 8080)
    return result


@router.post('/{session_id}/restart', response_model=LocalDeploymentSession)
async def restart_containers(session_id: str):
    from app.services.runtime_lifecycle import restart_local
    workspace, _ = _resolve_session_context(session_id)
    return restart_local(session_id, str(workspace))


@router.post('/{session_id}/cancel', response_model=LocalDeploymentSession)
async def cancel_local_operation(session_id: str, payload: LocalCancelRequest):
    from app.services.local_operations import request_cancel
    _resolve_session_context(session_id)
    try:
        return request_cancel(session_id, payload.operationId)
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.post('/{session_id}/cleanup', response_model=LocalDeploymentSession)
async def cleanup_containers(session_id: str, payload: LocalCleanupRequest):
    from app.services.runtime_lifecycle import cleanup_local
    _resolve_session_context(session_id)
    try:
        return cleanup_local(session_id, payload.deleteData, payload.confirmationToken)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))



@router.post("/{session_id}/playground", response_model=PlaygroundProxyResponse)
async def proxy_playground_call(session_id: str, payload: PlaygroundProxyRequest):
    """Forward one Live Playground call to this session's deployed container.

    The browser calls the platform (same origin); the platform calls the container.
    That removes the cross-origin request entirely, which the generated service cannot
    satisfy -- it ships no CORS configuration, so a direct browser call is rejected
    with 403 and appears as "Failed to fetch" while Docker is perfectly healthy.
    """
    ws_path, _ = _resolve_session_context(session_id)
    try:
        return PlaygroundProxyResponse(**forward(
            session_id, payload.method, payload.path, payload.body
        ))
    except PlaygroundProxyError as refused:
        # 400, not 500: the caller asked for something the proxy will not do. The
        # reason is returned verbatim because an operator debugging a legitimate call
        # needs to know which rule fired.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(refused))


@router.get("/{session_id}/playground/resources", response_model=PlaygroundResources)
async def get_playground_resources(session_id: str):
    """The REST paths this service exposes, read from its generated controllers.

    Exists so the CRUD form stops guessing. It previously posted to a hardcoded
    `/api/v1/orders`, which is wrong for every blueprint without an `Order` entity.
    """
    ws_path, _ = _resolve_session_context(session_id)
    return PlaygroundResources(
        sessionId=session_id,
        resources=discover_resources(session_id, str(ws_path)),
        defaultResource=default_resource(session_id, str(ws_path)),
    )

@router.get('/{session_id}/cleanup/preview')
async def preview_cleanup(session_id: str):
    _resolve_session_context(session_id)
    from app.services.runtime_lifecycle import cleanup_preview
    return cleanup_preview(session_id)
