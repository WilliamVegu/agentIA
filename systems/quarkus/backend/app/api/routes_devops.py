from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import StreamingResponse

from app.models.devops import PlaygroundProxyRequest
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

    from app.services.workspace_guard import get_validated_workspace_path
    ws_path = get_validated_workspace_path(session_id, require_exists=True)
    if not ws_path.exists() or not ws_path.is_dir():
        raise HTTPException(status_code=404, detail="Project workspace directory not found")

    return ws_path, service_name


@router.post("/{session_id}/generate", response_model=DevOpsManifestBundle)
async def generate_manifests(
    session_id: str,
    db_engine: Optional[str] = None,
    host_port: Optional[int] = None
):
    """Generates all Docker, Compose, CI/CD, and Kubernetes assets for the workspace session."""
    from app.services.session_operation_lock import SessionOperationLock
    from app.services.operation_repository import get_operation, ACTIVE
    from app.services.local_runtime import configuration
    from app.services.draft_revision_service import record_artifact
    ws_path, service_name = _resolve_session_context(session_id)
    lock=SessionOperationLock(session_id)
    if not lock.acquire(False):
        raise HTTPException(409,'Otra operación escribe esta sesión')
    try:
        operation=get_operation(session_id)
        if operation and operation['state'] in ACTIVE:
            raise HTTPException(409,'La operación activa conserva su configuración')
        config=configuration(session_id)
        if not config['databaseEngine'] or not config['hostPort']:
            raise HTTPException(409,'Guarde una configuración explícita antes de generar manifiestos')
        if db_engine is not None and db_engine.upper()!=config['databaseEngine'].upper():
            raise HTTPException(409,'El motor solicitado difiere de la configuración guardada; guarde y regenere explícitamente')
        if host_port is not None and host_port!=config['hostPort']:
            raise HTTPException(409,'El puerto solicitado difiere de la configuración guardada; guarde y regenere explícitamente')
        service_name=config['serviceName'] or service_name
        audit=audit_workspace(str(ws_path),session_id,service_name)
        if not audit.qualityGate.canExport:
            raise HTTPException(403,f"Cannot generate DevOps manifests: Quality Gate is BLOCKED. {audit.qualityGate.summaryMessage}")
        bundle=generate_all_devops_assets(str(ws_path),session_id,service_name,
            db_engine=config['databaseEngine'],host_port=config['hostPort'])
        with SessionLocal() as db:
            revision_id=db.get(GenerationSessionDB,session_id).revision_id
        if revision_id:
            for relative in ['Dockerfile','docker-compose.yml','ASSET_CONFIGURATION.json','local-ci.py','prepare-builder.py']:
                if (ws_path/relative).is_file():
                    record_artifact(session_id,relative,'DEVOPS_DEPLOY',revision_id)
        return bundle
    finally:
        lock.release()


@router.post("/{session_id}/deploy", response_model=LocalDeploymentSession)
async def deploy_container(session_id: str, payload: Optional[DevOpsDeployRequest] = None):
    """Initiates local Docker deployment and compose orchestration."""
    ws_path, service_name = _resolve_session_context(session_id)

    from app.services.local_runtime import require_runtime_allowed
    require_runtime_allowed(session_id)
    # Enforce Quality Gate check before deploying
    audit = audit_workspace(str(ws_path), session_id, service_name)
    if not audit.qualityGate.canExport:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot deploy containers: Quality Gate is BLOCKED. {audit.qualityGate.summaryMessage}",
        )

    # Ensure manifests exist; if not, generate first
    if not (ws_path / "docker-compose.yml").exists():
        from app.services.local_runtime import configuration
        config=configuration(session_id)
        if not config['databaseEngine'] or not config['hostPort']: raise HTTPException(409,'Configuración explícita requerida')
        generate_all_devops_assets(str(ws_path), session_id, config['serviceName'] or service_name,db_engine=config['databaseEngine'],host_port=config['hostPort'])

    host_port = payload.hostPort if payload else None
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
    _resolve_session_context(session_id)
    return get_deployment_status(session_id)


def _log_cursor(request: Request):
    try:
        cursor=int(request.headers.get('Last-Event-ID') or request.query_params.get('after') or '0')
        if cursor<0: raise ValueError()
        return cursor
    except ValueError: raise HTTPException(400,'Cursor inválido')


@router.get("/{session_id}/logs/stream")
async def stream_container_logs(session_id: str, request: Request):
    """Streams real-time build and execution logs via Server-Sent Events (SSE)."""
    _resolve_session_context(session_id)
    return StreamingResponse(
        stream_logs(session_id, _log_cursor(request)),
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
    _resolve_session_context(session_id)
    return {"logs": get_deployment_logs(session_id)}


@router.post("/{session_id}/stop", response_model=LocalDeploymentSession)
async def stop_containers(session_id: str):
    """Stops and cleans up active local containers for the session."""
    ws_path, _ = _resolve_session_context(session_id)
    return stop_deployment(session_id, str(ws_path))


@router.post("/{session_id}/smoke-test", response_model=SmokeTestResult)
async def execute_smoke_test(session_id: str, host_port: Optional[int] = None):
    """Executes automated post-deployment health validation against its owned native Quarkus /q/health endpoint."""
    _resolve_session_context(session_id)
    result = run_smoke_test(session_id, host_port=host_port)
    return result



from pydantic import BaseModel
class CleanupRequest(BaseModel):
    deleteData: bool = False
    confirmationToken: Optional[str] = None


@router.get('/{session_id}/cleanup/preview')
async def preview_cleanup(session_id: str):
    _resolve_session_context(session_id)
    from app.services.local_runtime import require_runtime_allowed
    require_runtime_allowed(session_id)
    from app.services.runtime_lifecycle import cleanup_preview
    try: return cleanup_preview(session_id)
    except (ValueError,RuntimeError) as exc: raise HTTPException(409,str(exc)) from None


@router.post('/{session_id}/cleanup', response_model=LocalDeploymentSession)
async def cleanup_containers(session_id: str, payload: CleanupRequest):
    _resolve_session_context(session_id)
    from app.services.local_runtime import require_runtime_allowed
    require_runtime_allowed(session_id)
    from app.services.runtime_lifecycle import cleanup_owned
    from app.services.session_operation_lock import SessionOperationLock
    lock = SessionOperationLock(session_id)
    if not lock.acquire(False):
        raise HTTPException(409, 'Session has an active operation')
    try:
        cleanup_owned(session_id, delete_data=payload.deleteData, confirmation=payload.confirmationToken)
        from app.services.local_runtime import record_stopped
        record_stopped(session_id)
    except (ValueError,RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from None
    finally:
        lock.release()
    return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.STOPPED, healthStatus='DOWN')


@router.get('/{session_id}/configuration')
async def get_native_configuration(session_id: str):
    from app.services.local_runtime import configuration
    return configuration(session_id)


@router.get('/{session_id}/manifests')
async def read_native_manifests(session_id: str):
    from app.services.workspace_guard import resolve_workspace_file,io_path
    _resolve_session_context(session_id)
    paths={'dockerfileContent':'Dockerfile','dockerignoreContent':'.dockerignore','dockerComposeContent':'docker-compose.yml',
        'githubActionsWorkflow':'.github/workflows/ci-cd.yml','gitlabCiWorkflow':'.gitlab-ci.yml'}
    result={key:io_path(resolve_workspace_file(session_id,path,require_exists=True)).read_text(encoding='utf-8') for key,path in paths.items()}
    result['kubernetesManifests']={name:io_path(resolve_workspace_file(session_id,'k8s/'+name,require_exists=True)).read_text(encoding='utf-8') for name in ['deployment.yaml','service.yaml','configmap.yaml','ingress.yaml']}
    return result


@router.post('/{session_id}/playground')
async def native_playground(session_id: str,payload: PlaygroundProxyRequest):
    from app.models.devops import PlaygroundProxyRequest
    from app.services.playground_proxy import forward,PlaygroundProxyError
    _resolve_session_context(session_id)
    request=payload
    try: return forward(session_id,request.method,request.path,request.body)
    except PlaygroundProxyError as error: raise HTTPException(400,str(error))


@router.get('/{session_id}/playground/resources')
async def native_playground_resources(session_id: str):
    from app.services.playground_proxy import discover_resources
    workspace,_=_resolve_session_context(session_id)
    resources=discover_resources(session_id,str(workspace))
    return {'sessionId':session_id,'resources':resources,'defaultResource':resources[0] if resources else None}
