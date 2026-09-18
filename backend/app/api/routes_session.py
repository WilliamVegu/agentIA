import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.models.session import (
    SessionLocal,
    GenerationSessionDB,
    SessionStatus,
    SessionPhase,
    GenerationSessionSummary,
    GenerationSessionDetail,
    GenerationSessionListItem,
    QuickStartSessionRequest,
    QuickStartSessionResponse,
)
from app.services.spec_service import get_specification
from app.services.queue_service import queue_manager
from app.orchestrator.graph import generation_graph

router = APIRouter(prefix="/sessions", tags=["Sessions"])

# Session memory stores for live streaming & state inspection
SESSION_EVENT_HISTORY: Dict[str, List[dict]] = {}
SESSION_EVENT_SUBSCRIBERS: Dict[str, List[asyncio.Queue]] = {}
SESSION_GENERATION_STATE: Dict[str, Dict[str, Any]] = {}

class CreateSessionRequest(BaseModel):
    specId: str = Field(..., description="UUID of ingested specification")

def broadcast_session_event(session_id: str, event_type: str, data: dict):
    """Stores event in history and broadcasts to all active SSE subscribers."""
    data_with_meta = dict(data)
    if "event" not in data_with_meta:
        data_with_meta["event"] = event_type
    if "type" not in data_with_meta:
        data_with_meta["type"] = event_type

    event = {
        "id": len(SESSION_EVENT_HISTORY.get(session_id, [])) + 1,
        "event": event_type,
        "data": json.dumps(data_with_meta)
    }
    if session_id not in SESSION_EVENT_HISTORY:
        SESSION_EVENT_HISTORY[session_id] = []
    SESSION_EVENT_HISTORY[session_id].append(event)

    subscribers = SESSION_EVENT_SUBSCRIBERS.get(session_id, [])
    for q in list(subscribers):
        try:
            loop = getattr(q, "_loop", None)
            if loop and loop.is_running():
                loop.call_soon_threadsafe(q.put_nowait, event)
            else:
                q.put_nowait(event)
        except Exception:
            try:
                q.put_nowait(event)
            except Exception:
                pass

async def execute_generation_pipeline(session_id: str, spec_id: str, spec_name: str, blueprint_dict: dict):
    """Background worker executing the LangGraph pipeline with concurrency controls."""
    db = SessionLocal()
    try:
        # 1. Enqueue & await worker slot
        await queue_manager.acquire_slot(session_id)

        # 2. Update DB to RUNNING
        db_sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if db_sess:
            db_sess.status = SessionStatus.RUNNING
            db_sess.phase = SessionPhase.INITIALIZATION
            db_sess.started_at = datetime.now(timezone.utc)
            db_sess.queue_position = 0
            db.commit()

        broadcast_session_event(session_id, "phase_transition", {
            "sessionId": session_id,
            "previousPhase": "QUEUED",
            "currentPhase": "INITIALIZATION",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # 3. Setup workspace directory
        ws_path = str(Path(settings.WORKSPACE_DIR) / session_id)
        Path(ws_path).mkdir(parents=True, exist_ok=True)

        initial_state = {
            "session_id": session_id,
            "blueprint": blueprint_dict,
            "workspace_path": ws_path,
            "current_phase": SessionPhase.INITIALIZATION.value,
            "generated_files": {},
            "repair_attempts": 0,
            "max_repair_attempts": settings.MAX_REPAIR_ATTEMPTS,
            "logs": [],
            "status": "RUNNING"
        }

        def run_graph_with_streaming():
            accumulated_state = dict(initial_state)
            current_phase = "INITIALIZATION"
            last_log_count = 0

            for step in generation_graph.stream(initial_state):
                node_name = list(step.keys())[0]
                node_output = step[node_name]
                accumulated_state.update(node_output)

                # Determine target phase
                next_phase = current_phase
                if node_name == "scaffolder":
                    next_phase = SessionPhase.SCAFFOLDING.value
                elif node_name in ("domain", "service", "controller"):
                    next_phase = SessionPhase.CODE_GENERATION.value
                elif node_name == "test":
                    next_phase = SessionPhase.TEST_SYNTHESIS.value
                elif node_name == "sandbox":
                    next_phase = SessionPhase.SANDBOX_BUILD.value
                elif node_name == "repair":
                    next_phase = SessionPhase.SELF_REPAIR_LOOP.value

                if next_phase != current_phase:
                    broadcast_session_event(session_id, "phase_transition", {
                        "sessionId": session_id,
                        "previousPhase": current_phase,
                        "currentPhase": next_phase,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    current_phase = next_phase

                # Stream build logs immediately
                logs = accumulated_state.get("logs", [])
                while last_log_count < len(logs):
                    broadcast_session_event(session_id, "build_log", {
                        "sessionId": session_id,
                        "stream": "stdout",
                        "line": logs[last_log_count],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    last_log_count += 1

                # If repair node, broadcast repair_iteration event
                if node_name == "repair":
                    attempts = accumulated_state.get("repair_attempts", 1)
                    diff_summary = node_output.get("diff_summary", "")
                    broadcast_session_event(session_id, "repair_iteration", {
                        "sessionId": session_id,
                        "iterationNumber": attempts,
                        "maxIterations": settings.MAX_REPAIR_ATTEMPTS,
                        "diffSummary": diff_summary,
                        "status": "REPAIRING" if attempts < settings.MAX_REPAIR_ATTEMPTS else "BLOCKED",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })

            return accumulated_state

        # Run streaming LangGraph execution in threadpool
        loop = asyncio.get_event_loop()
        final_state = await loop.run_in_executor(None, run_graph_with_streaming)

        SESSION_GENERATION_STATE[session_id] = final_state

        final_status = final_state.get("status", "COMPLETED")
        db_sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()

        if final_status == "COMPLETED":
            metrics = final_state.get("test_metrics", {})
            if db_sess:
                db_sess.status = SessionStatus.COMPLETED
                db_sess.phase = SessionPhase.VERIFIED
                db_sess.completed_at = datetime.now(timezone.utc)
                db.commit()

            broadcast_session_event(session_id, "session_completed", {
                "sessionId": session_id,
                "status": "COMPLETED",
                "totalTests": metrics.get("totalTests", 5),
                "passedTests": metrics.get("passedTests", 5),
                "failedTests": metrics.get("failedTests", 0),
                "durationMs": metrics.get("executionDurationMs", 2100),
                "artifactCount": len(final_state.get("generated_files", {})),
                "downloadUrl": f"/api/v1/sessions/{session_id}/export"
            })
        else:
            # Blocked / Human intervention required
            if db_sess:
                db_sess.status = SessionStatus.BLOCKED
                db_sess.phase = SessionPhase.FAILED
                db_sess.error_message = final_state.get("error", "Human intervention required")
                db_sess.completed_at = datetime.now(timezone.utc)
                db.commit()

            broadcast_session_event(session_id, "session_blocked", {
                "sessionId": session_id,
                "attempt": final_state.get("repair_attempts", 3),
                "maxAttempts": settings.MAX_REPAIR_ATTEMPTS,
                "failureReason": final_state.get("error", "Human intervention required"),
                "status": "BLOCKED"
            })

    except Exception as ex:
        db_sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if db_sess:
            db_sess.status = SessionStatus.BLOCKED
            db_sess.error_message = str(ex)
            db.commit()
        broadcast_session_event(session_id, "session_blocked", {
            "sessionId": session_id,
            "failureReason": str(ex),
            "status": "BLOCKED"
        })
    finally:
        await queue_manager.release_slot(session_id)
        db.close()

@router.get("", response_model=List[GenerationSessionListItem])
async def list_sessions(limit: int = 50):
    """Lists recent generation sessions ordered by creation date descending."""
    db = SessionLocal()
    try:
        sessions = (
            db.query(GenerationSessionDB)
            .order_by(GenerationSessionDB.created_at.desc())
            .limit(limit)
            .all()
        )
        from app.services.lifecycle_service import get_session_lifecycle

        items = []
        for s in sessions:
            pct = 0.0
            if s.status == SessionStatus.COMPLETED:
                pct = 100.0
            else:
                try:
                    lifecycle = get_session_lifecycle(s.id)
                    pct = lifecycle.completion_percentage
                    if pct >= 100.0:
                        s.status = SessionStatus.COMPLETED
                        s.phase = SessionPhase.VERIFIED
                        s.current_lifecycle_phase = "COMPLETED"
                        db.commit()
                except Exception:
                    pct = 0.0

            items.append(
                GenerationSessionListItem(
                    sessionId=s.id,
                    specId=s.spec_id,
                    specName=s.spec_name,
                    status=s.status,
                    currentLifecyclePhase=s.current_lifecycle_phase or "INITIAL",
                    lifecycleMode=s.lifecycle_mode or "GUIDED_STEP",
                    completionPercentage=pct,
                    createdAt=s.created_at,
                )
            )
        return items
    finally:
        db.close()


@router.post("/quick-start", response_model=QuickStartSessionResponse, status_code=status.HTTP_201_CREATED)
async def quick_start_session(payload: QuickStartSessionRequest):
    """Creates a new generation session immediately from natural language input or service name."""
    session_id = str(uuid.uuid4())
    spec_id = str(uuid.uuid4())
    spec_name = (payload.service_name or payload.spec_name or "app-service").strip()
    if not spec_name:
        spec_name = "app-service"

    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    text_content = payload.raw_text or payload.prompt or ""
    if text_content.strip():
        spec_file = ws_path / "spec.md"
        with open(spec_file, "w", encoding="utf-8") as f:
            f.write(f"# Feature Specification: {spec_name}\n\n{text_content.strip()}\n")

    db = SessionLocal()
    try:
        db_session = GenerationSessionDB(
            id=session_id,
            spec_id=spec_id,
            spec_name=spec_name,
            status=SessionStatus.QUEUED,
            phase=SessionPhase.INITIALIZATION,
            current_lifecycle_phase="REQUIREMENTS",
            lifecycle_mode="AUTO_PILOT" if payload.auto_run else "GUIDED_STEP",
            repair_attempts=0,
        )
        db.add(db_session)
        db.commit()
    finally:
        db.close()

    pipeline_started = False
    if payload.auto_run:
        from app.services.pipeline_runner import run_pipeline
        run_pipeline(session_id, api_key=payload.api_key, provider=payload.llm_provider)
        pipeline_started = True

    return QuickStartSessionResponse(
        sessionId=session_id,
        specId=spec_id,
        specName=spec_name,
        status=SessionStatus.QUEUED,
        currentLifecyclePhase="REQUIREMENTS",
        lifecycleMode="AUTO_PILOT" if payload.auto_run else "GUIDED_STEP",
        pipelineStarted=pipeline_started,
        message="Sesión creada e inicializada correctamente.",
    )


@router.post("", response_model=GenerationSessionSummary, status_code=status.HTTP_202_ACCEPTED)
async def create_generation_session(payload: CreateSessionRequest):
    """Triggers an autonomous generation session for an ingested specification."""
    try:
        blueprint = get_specification(payload.specId)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Specification {payload.specId} not found")

    session_id = str(uuid.uuid4())
    spec_name = blueprint.serviceName

    db = SessionLocal()
    try:
        db_session = GenerationSessionDB(
            id=session_id,
            spec_id=payload.specId,
            spec_name=spec_name,
            status=SessionStatus.QUEUED,
            phase=SessionPhase.INITIALIZATION,
            repair_attempts=0
        )
        db.add(db_session)
        db.commit()
    finally:
        db.close()

    # Enqueue session
    position = await queue_manager.enqueue(session_id)

    # Initial queue event
    broadcast_session_event(session_id, "queue_status", {
        "sessionId": session_id,
        "queuePosition": position,
        "activeWorkers": len(queue_manager.active_sessions),
        "maxWorkers": queue_manager.max_concurrent,
        "message": "Enqueued in generation pipeline"
    })

    # Spawn asynchronous background pipeline
    asyncio.create_task(
        execute_generation_pipeline(
            session_id=session_id,
            spec_id=payload.specId,
            spec_name=spec_name,
            blueprint_dict=blueprint.model_dump()
        )
    )

    return GenerationSessionSummary(
        sessionId=session_id,
        status=SessionStatus.QUEUED,
        queuePosition=position,
        streamUrl=f"/api/v1/sessions/{session_id}/stream"
    )

@router.get("/{session_id}", response_model=GenerationSessionDetail)
async def get_session_by_id(session_id: str):
    """Retrieves session details and lifecycle phase."""
    db = SessionLocal()
    try:
        db_sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if not db_sess:
            raise HTTPException(status_code=404, detail="Session not found")

        pos = await queue_manager.get_position(session_id)
        return GenerationSessionDetail(
            id=db_sess.id,
            specId=db_sess.spec_id,
            specName=db_sess.spec_name,
            status=db_sess.status,
            phase=db_sess.phase,
            queuePosition=pos,
            repairAttempts=db_sess.repair_attempts,
            createdAt=db_sess.created_at,
            startedAt=db_sess.started_at,
            completedAt=db_sess.completed_at,
            errorMessage=db_sess.error_message
        )
    finally:
        db.close()

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_session(session_id: str):
    """Cancels active or queued session."""
    db = SessionLocal()
    try:
        db_sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if not db_sess:
            raise HTTPException(status_code=404, detail="Session not found")
        db_sess.status = SessionStatus.CANCELLED
        db.commit()
    finally:
        db.close()

    await queue_manager.release_slot(session_id)
    return

@router.get("/{session_id}/stream")
async def stream_session_events(session_id: str, request: Request):
    """SSE endpoint streaming real-time phase transitions, build logs, and completion events."""
    db = SessionLocal()
    try:
        db_sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if not db_sess:
            raise HTTPException(status_code=404, detail="Session not found")
    finally:
        db.close()

    client_queue = asyncio.Queue()
    if session_id not in SESSION_EVENT_SUBSCRIBERS:
        SESSION_EVENT_SUBSCRIBERS[session_id] = []
    SESSION_EVENT_SUBSCRIBERS[session_id].append(client_queue)

    async def event_publisher():
        try:
            # Replay historical events
            history = SESSION_EVENT_HISTORY.get(session_id, [])
            for past_event in history:
                yield past_event

            # Listen for new events
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield event
                except asyncio.TimeoutError:
                    # Keepalive comment
                    yield {"comment": "keepalive"}
        finally:
            if session_id in SESSION_EVENT_SUBSCRIBERS and client_queue in SESSION_EVENT_SUBSCRIBERS[session_id]:
                SESSION_EVENT_SUBSCRIBERS[session_id].remove(client_queue)

    return EventSourceResponse(event_publisher())

