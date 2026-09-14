import io
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Response
from fastapi.responses import StreamingResponse

from app.config import settings
from app.models.orchestrator import (
    LifecyclePhase,
    LifecycleState,
    PhaseTransitionRequest,
    PipelineRunRequest,
    ProjectOverviewSummary,
)
from app.models.session import GenerationSessionDB, SessionLocal, SessionStatus, SessionPhase
from app.services.export_service import export_full_bundle
from app.services.lifecycle_service import (
    clear_outdated_phases,
    get_project_overview,
    get_session_lifecycle,
    mark_downstream_outdated,
    transition_phase,
)
from app.services.pipeline_runner import (
    cancel_pipeline,
    get_pipeline_status,
    pause_pipeline,
    resume_pipeline,
    run_pipeline,
    stream_pipeline_events,
)

router = APIRouter(prefix="/orchestrator", tags=["Lifecycle Orchestrator & Auto-Pilot"])


def _verify_session_exists(session_id: str):
    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        return sess
    finally:
        db.close()


@router.get("/sessions/{session_id}/overview", response_model=ProjectOverviewSummary)
async def session_overview(session_id: str):
    """Retrieves high-level project summary and milestone metrics for the Home View."""
    _verify_session_exists(session_id)
    return get_project_overview(session_id)


@router.get("/sessions/{session_id}/lifecycle", response_model=LifecycleState)
async def session_lifecycle(session_id: str):
    """Returns the full lifecycle state, phase progress, and next recommended action."""
    _verify_session_exists(session_id)
    return get_session_lifecycle(session_id)


@router.post("/sessions/{session_id}/transition", response_model=LifecycleState)
async def transition_session_phase(session_id: str, payload: PhaseTransitionRequest):
    """Validates prerequisites and transitions the session to a target lifecycle phase."""
    _verify_session_exists(session_id)
    try:
        updated_state = transition_phase(session_id, payload.target_phase, force=payload.force)
        return updated_state
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/invalidate")
async def invalidate_downstream_phases(session_id: str, payload: Optional[Dict[str, Any]] = None):
    """Marks downstream phases as OUTDATED after an upstream artifact modification."""
    _verify_session_exists(session_id)
    mod_phase = (payload.get("modifiedPhase") if payload else None) or "REQUIREMENTS"
    outdated = mark_downstream_outdated(session_id, mod_phase)
    return {"sessionId": session_id, "modifiedPhase": mod_phase, "outdatedPhases": outdated}


@router.post("/pipeline/run", status_code=status.HTTP_202_ACCEPTED)
async def run_autopilot_pipeline(payload: PipelineRunRequest):
    """Initiates autonomous background Auto-Pilot pipeline execution."""
    target_session_id = payload.session_id
    if target_session_id == "new":
        target_session_id = str(uuid.uuid4())
        db = SessionLocal()
        try:
            db_sess = GenerationSessionDB(
                id=target_session_id,
                spec_id=str(uuid.uuid4()),
                spec_name="microservice-app",
                status=SessionStatus.QUEUED,
                phase=SessionPhase.INITIALIZATION,
                current_lifecycle_phase="REQUIREMENTS",
                lifecycle_mode="AUTO_PILOT",
                repair_attempts=0,
            )
            db.add(db_sess)
            db.commit()
        finally:
            db.close()
    else:
        _verify_session_exists(target_session_id)

    if payload.force:
        clear_outdated_phases(target_session_id)

    started = run_pipeline(
        session_id=target_session_id,
        target_phase=payload.target_phase or LifecyclePhase.DEVOPS_DEPLOY,
        stop_on_gate=payload.stop_on_gate,
        auto_deploy=payload.auto_deploy,
        api_key=payload.api_key,
        provider=payload.provider,
        model_name=payload.model,
    )
    if not started:
        raise HTTPException(
            status_code=400,
            detail="Pipeline is already running or cannot be started for this session."
        )

    return {
        "sessionId": target_session_id,
        "status": "RUNNING",
        "streamUrl": f"/api/v1/orchestrator/pipeline/{target_session_id}/events",
    }


@router.post("/pipeline/{session_id}/pause")
@router.post("/pipeline/pause")
async def pause_autopilot_pipeline(session_id: Optional[str] = None, payload: Optional[Dict[str, Any]] = None):
    """Pauses an active Auto-Pilot run and transitions to Guided Step-by-Step mode."""
    target_id = session_id or (payload.get("sessionId") if payload else None)
    if not target_id:
        raise HTTPException(status_code=400, detail="sessionId required")
    _verify_session_exists(target_id)
    success = pause_pipeline(target_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="No active running pipeline found to pause for this session."
        )
    return {"sessionId": target_id, "status": "PAUSED"}


@router.post("/pipeline/{session_id}/resume")
@router.post("/pipeline/resume")
async def resume_autopilot_pipeline(session_id: Optional[str] = None, payload: Optional[Dict[str, Any]] = None):
    """Resumes a paused Auto-Pilot run."""
    target_id = session_id or (payload.get("sessionId") if payload else None)
    if not target_id:
        raise HTTPException(status_code=400, detail="sessionId required")
    _verify_session_exists(target_id)
    success = resume_pipeline(target_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="No paused pipeline found to resume for this session."
        )
    return {"sessionId": target_id, "status": "RUNNING"}


@router.post("/pipeline/{session_id}/cancel")
@router.post("/pipeline/cancel")
async def cancel_autopilot_pipeline(session_id: Optional[str] = None, payload: Optional[Dict[str, Any]] = None):
    """Cancels an active or paused Auto-Pilot run."""
    target_id = session_id or (payload.get("sessionId") if payload else None)
    if not target_id:
        raise HTTPException(status_code=400, detail="sessionId required")
    _verify_session_exists(target_id)
    cancel_pipeline(target_id)
    return {"sessionId": target_id, "status": "CANCELLED"}


@router.get("/pipeline/{session_id}/events")
async def stream_pipeline_progress(session_id: str):
    """Streams real-time progress events for an active pipeline via Server-Sent Events (SSE)."""
    _verify_session_exists(session_id)
    return StreamingResponse(
        stream_pipeline_events(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions/{session_id}/export-bundle")
async def export_bundle_archive(session_id: str):
    """Downloads all workspace artifacts in a unified ZIP archive."""
    sess = _verify_session_exists(session_id)
    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    if not ws_path.exists() or not ws_path.is_dir():
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    zip_bytes = export_full_bundle(str(ws_path))
    filename = f"{sess.spec_name or 'microservice'}-complete-bundle.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

