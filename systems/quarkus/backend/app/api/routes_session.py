from app.services.execution_policy import execution_mode
from app.models.execution import ExecutionMode
from app.services.verification_policy import session_is_verified, verification_outcome, tests_really_passed
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, status, Request, Header
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
from app.orchestrator.stages.runner import select_generation_mode
from app.services.conformance_diagnostics import record_session_diagnostics

router = APIRouter(prefix="/sessions", tags=["Sessions"])

# Session memory stores for live streaming & state inspection
SESSION_EVENT_HISTORY: Dict[str, List[dict]] = {}
SESSION_EVENT_SUBSCRIBERS: Dict[str, List[asyncio.Queue]] = {}
SESSION_GENERATION_STATE: Dict[str, Dict[str, Any]] = {}
GRAPH_CANCEL_EVENTS: Dict[str, Any] = {}

class CreateSessionRequest(BaseModel):
    specId: str = Field(..., description="UUID of ingested specification")
    executionMode: ExecutionMode = ExecutionMode.SOURCE_ONLY
    modelName: Optional[str] = None

def _verification_fallback_used(db_sess) -> bool:
    """Whether verification actually ran, read from the persisted metrics.

    Feature 012 (FR-005). Degrades to ``False`` rather than raising when the
    metrics are absent or unparseable: a session row predating the column, or one
    whose metrics were never written, is a data gap and must not turn a session
    detail request into a server error.
    """
    raw = getattr(db_sess, "verification_metrics_json", None) if db_sess else None
    if not raw:
        return False
    try:
        return bool(json.loads(raw).get("fallback_used", False))
    except Exception:
        return False


def _persist_verification_metrics(db_sess, final_state: dict) -> None:
    """Store the verification metrics so the marking survives a process restart.

    Feature 012 (T019). Called before the branch's commit, so the detail endpoint
    can report whether verification actually ran even after a restart -- the
    in-process state does not survive one.
    """
    if db_sess is None:
        return
    metrics = final_state.get("test_metrics")
    if not metrics:
        return
    from app.services.graph_completion_policy import previous_failed
    if metrics.get('verificationSkipped') and previous_failed(db_sess):
        metrics={**json.loads(db_sess.verification_metrics_json),'verificationOutdated':True,'sourceDeliveryReady':False}
    db_sess.verification_metrics_json = json.dumps(metrics)


def _persist_diagnostics(session_id: str, final_state: dict) -> bool:
    """Record what was found wrong with this session's artifacts (feature 015, FR-001).

    Best-effort by design: a diagnostics failure must never stop a session from
    reaching its terminal state. Unlike feature 014's write path, however, the
    outcome is *returned* rather than swallowed -- a missing table there produced
    silent data loss while the caller reported success, and the same mistake here
    would leave sessions unmeasurable without anyone noticing.

    Runs on BOTH terminal paths. A blocked session is exactly the one worth
    diagnosing, so it must not be the path that skips recording.

    Delegates to the one writer so every terminal path, on every execution path,
    records identically. The sequential pipeline's stage-exhaustion branch is the
    case that proved the need: it wrote nothing at all.
    """
    return record_session_diagnostics(session_id, final_state)


def broadcast_session_event(session_id: str, event_type: str, data: dict):
    from app.services.session_event_service import publish_event
    return publish_event(session_id, event_type, data)


async def execute_generation_pipeline(session_id, spec_id, spec_name, blueprint_dict, *args, **kwargs):
    """The graph shares the durable single-writer contract with Auto-Pilot."""
    import threading
    from app.services.workspace_guard import get_validated_workspace_path
    from app.services.session_operation_lock import SessionOperationLock
    from app.services.operation_repository import begin_operation, get_operation, transition_operation
    from app.services.draft_revision_service import get_revision, save_revision, record_artifact
    from app.models.requirements import SpecificationDraft
    from app.services import pipeline_runner
    ws=get_validated_workspace_path(session_id,require_exists=False)
    ws.mkdir(parents=True,exist_ok=True)
    lock=SessionOperationLock(session_id)
    if not lock.acquire(False): raise HTTPException(409,'Otra operación escribe esta sesión')
    operation=None
    try:
        operation=begin_operation(session_id,'CODE_TESTS',{'entryPoint':'GRAPH'})
        operation=transition_operation(operation['operationId'],operation['version'],'RUNNING')
        revision=get_revision(session_id)
        if revision.get('revisionId'):
            if revision['source'] in {'MANUAL','LEGACY'} and revision['approvalStatus']!='APPROVED':
                raise HTTPException(409,'La revisión humana requiere aprobación exacta')
            blueprint_dict=revision['draft']
        else:
            payload=SpecificationDraft.model_validate(blueprint_dict).model_dump()
            revision=save_revision(session_id,payload,source='GENERATED',_operation_id=operation['operationId'])
            blueprint_dict=revision['draft']
        cancel_event=threading.Event()
        pipeline_runner._stop_events[session_id]=cancel_event
        pipeline_runner._pause_events[session_id]=threading.Event()
        GRAPH_CANCEL_EVENTS[session_id]=cancel_event
        await _execute_generation_pipeline_steps(session_id,spec_id,spec_name,blueprint_dict,*args,**kwargs)
        state=SESSION_GENERATION_STATE.get(session_id,{})
        for relative in state.get('generated_files',{}):
            if (ws/relative).is_file(): record_artifact(session_id,relative,'CODE_TESTS',revision['revisionId'])
    except asyncio.CancelledError:
        if operation:
            from app.services.operation_repository import finish_operation
            finish_operation(session_id,operation['operationId'],'INTERRUPTED',error_code='WORKER_CANCELLED')
        raise
    except Exception as error:
        if operation:
            from app.services.operation_repository import finish_operation
            finish_operation(session_id,operation['operationId'],'BLOCKED',error_code=type(error).__name__)
        raise
    finally:
        try:
            if operation:
                from app.services.operation_repository import finish_operation
                with SessionLocal() as db: row=db.get(GenerationSessionDB,session_id)
                finish_operation(session_id,operation['operationId'],
                    'COMPLETED' if row and row.status==SessionStatus.COMPLETED else 'BLOCKED')
        finally:
            GRAPH_CANCEL_EVENTS.pop(session_id,None)
            lock.release()


async def _execute_generation_pipeline_steps(session_id: str, spec_id: str, spec_name: str, blueprint_dict: dict, api_key=None, provider=None, model_name=None):
    """Background worker executing the LangGraph pipeline with concurrency controls."""
    db = SessionLocal()
    try:
        # 1. Enqueue & await worker slot
        if not await queue_manager.acquire_slot(session_id): return

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

        # 3b. Decide the generation mode ONCE, before the first stage runs, and
        # record it in the generation state (T018). The graph's node callables
        # are the retained deterministic implementations in this phase, so the
        # recorded mode is not yet consumed on this path (T020 is deferred — see
        # the feature's completion report); recording it here makes the decision
        # auditable and prepares the graph path for the same seam the sequential
        # path already uses.
        mode_selection = select_generation_mode(api_key=api_key,provider=provider,model_name=model_name)
        instruction_revision = ""
        try:
            from app.orchestrator.stages.instructions import load_instruction_set
            instruction_revision = load_instruction_set().revision
        except Exception:  # noqa: BLE001
            # Deterministic sessions do not read instructions, so an unloadable
            # set must not break the offline path.
            instruction_revision = ""

        from app.services.operation_repository import get_operation
        repair_operation=get_operation(session_id)
        initial_state = {
            "repair_operation_id":repair_operation["operationId"] if repair_operation else None,
            "session_id": session_id,
            "execution_mode": execution_mode(session_id).value,
            "blueprint": blueprint_dict,
            "workspace_path": ws_path,
            "current_phase": SessionPhase.INITIALIZATION.value,
            "generated_files": {},
            "repair_attempts": 0,
            "max_repair_attempts": settings.MAX_REPAIR_ATTEMPTS,
            "logs": [],
            "status": "RUNNING",
            "generation_mode": mode_selection.mode,
            "instruction_set_revision": instruction_revision,
            "llm_provider": mode_selection.provider,
            "llm_model": mode_selection.model,
            "llm_api_key": api_key,
        }

        def run_graph_with_streaming():
            accumulated_state = dict(initial_state)
            current_phase = "INITIALIZATION"
            last_log_count = 0

            for step in generation_graph.stream(initial_state):
                if GRAPH_CANCEL_EVENTS.get(session_id) and GRAPH_CANCEL_EVENTS[session_id].is_set():
                    accumulated_state['status']='CANCELLED'
                    break
                from app.services import pipeline_runner
                if pipeline_runner._pause_events.get(session_id) and pipeline_runner._pause_events[session_id].is_set():
                    accumulated_state['status']='PAUSED'
                    break
                from app.services.operation_repository import get_operation,checkpoint_operation
                operation=get_operation(session_id)
                if operation and operation['state'] in {'RUNNING','PAUSE_REQUESTED','CANCEL_REQUESTED'}:
                    checkpoint_operation(operation['operationId'],operation['version'],'CODE_TESTS',{'node':next(iter(step))})
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

                # Feature 012 (FR-005, T021): surface whether verification
                # actually ran as soon as the sandbox node finishes -- BEFORE any
                # terminal event. In permissive mode a session can still reach
                # VERIFIED, so this streaming event is the only place a watcher
                # learns the verification was synthetic. A structured field, not a
                # log line, so a machine consumer can branch without parsing.
                if node_name == "sandbox":
                    sandbox_metrics = node_output.get("test_metrics") or {}
                    broadcast_session_event(session_id, "verification_result", {
                        "sessionId": session_id,
                        "verificationFallbackUsed": bool(sandbox_metrics.get("fallback_used", False)),
                        "fallbackReason": sandbox_metrics.get("fallback_reason"),
                        "buildSuccess": node_output.get("build_success", False),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })

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
        graph_future = loop.run_in_executor(None, run_graph_with_streaming)
        try:
            final_state = await asyncio.shield(graph_future)
        except asyncio.CancelledError:
            # Keep the workspace lock until the actual writer has unwound.
            control = GRAPH_CANCEL_EVENTS.get(session_id)
            if control:
                control.set()
            await asyncio.shield(graph_future)
            raise

        from app.services.secret_redaction import without_credentials
        SESSION_GENERATION_STATE[session_id] = without_credentials(final_state)

        final_status = final_state.get("status", "COMPLETED")
        db_sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()

        if final_status in {'PAUSED','CANCELLED'}:
            if db_sess:
                db_sess.status=SessionStatus.PAUSED if final_status=='PAUSED' else SessionStatus.CANCELLED
                db.commit()
            broadcast_session_event(session_id,'session_control_ack',{'status':final_status})
            return

        if final_status == "COMPLETED":
            from app.services.graph_completion_policy import qualify_completion
            if not db_sess or not qualify_completion(db_sess,ws_path,final_state):
                final_status='BLOCKED'
                final_state['status']='BLOCKED'
                final_state['error']='La generación terminó sin evidencia vigente de verificación o entrega de fuentes auditadas'
            SESSION_GENERATION_STATE[session_id]=without_credentials(final_state)

        if final_status == "COMPLETED":
            metrics = final_state.get("test_metrics", {})
            if db_sess:
                db_sess.status = SessionStatus.COMPLETED
                db_sess.phase = SessionPhase.VERIFIED if tests_really_passed(metrics) else SessionPhase.TEST_SYNTHESIS
                db_sess.completed_at = datetime.now(timezone.utc)
                _persist_verification_metrics(db_sess, final_state)
                db.commit()

            # Recorded outside the db_sess guard: the diagnostic is worth keeping
            # even when the session row could not be loaded.
            _persist_diagnostics(session_id, final_state)

            broadcast_session_event(session_id, "session_completed", {
                "sessionId": session_id,
                "status": "COMPLETED",
                # FR-005: a session may reach VERIFIED under permissive mode with a
                # substituted verification, so the terminal event must say so.
                "verificationFallbackUsed": bool(metrics.get("fallback_used", False)),
                "fallbackReason": metrics.get("fallback_reason"),
                "totalTests": metrics.get("totalTests", 0),
                "passedTests": metrics.get("passedTests", 0),
                "failedTests": metrics.get("failedTests", 0),
                "durationMs": metrics.get("executionDurationMs", 0),
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
                _persist_verification_metrics(db_sess, final_state)
                db.commit()

            _persist_diagnostics(session_id, final_state)

            blocked_metrics = final_state.get("test_metrics") or {}
            broadcast_session_event(session_id, "session_blocked", {
                "sessionId": session_id,
                "attempt": final_state.get("repair_attempts", 3),
                "maxAttempts": settings.MAX_REPAIR_ATTEMPTS,
                "failureReason": final_state.get("error", "Human intervention required"),
                "status": "BLOCKED",
                # FR-005: distinguishes "could not verify" from a real build failure.
                "verificationFallbackUsed": bool(blocked_metrics.get("fallback_used", False)),
                "fallbackReason": blocked_metrics.get("fallback_reason"),
            })

    except Exception as ex:
        db_sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if db_sess:
            db_sess.status = SessionStatus.BLOCKED
            db_sess.phase = SessionPhase.FAILED
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
            if session_is_verified(s):
                pct = 100.0
            else:
                try:
                    lifecycle = get_session_lifecycle(s.id)
                    pct = lifecycle.completion_percentage
                    # Projection does not mutate stored outcomes.
                except Exception:
                    pct = 0.0

            items.append(
                GenerationSessionListItem(
                    sessionId=s.id,
                    specId=s.spec_id,
                    specName=s.spec_name,
                    status=s.status,
                    executionMode=s.execution_mode,
                    verificationOutcome=verification_outcome(s),
                    errorMessage=s.error_message,
                    phase=s.phase,
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
    (ws_path / "generation-settings.json").write_text(
        json.dumps({"databaseMode": payload.database_engine or "POSTGRESQL"}), encoding="utf-8"
    )
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
            execution_mode=payload.execution_mode.value,
            database_engine=payload.database_engine.value,
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
        run_pipeline(session_id, api_key=payload.api_key, provider=payload.llm_provider, model_name=payload.model_name, auto_deploy=payload.auto_deploy)
        pipeline_started = True

    return QuickStartSessionResponse(
        sessionId=session_id,
        executionMode=payload.execution_mode,
        specId=spec_id,
        specName=spec_name,
        status=SessionStatus.QUEUED,
        currentLifecyclePhase="REQUIREMENTS",
        lifecycleMode="AUTO_PILOT" if payload.auto_run else "GUIDED_STEP",
        pipelineStarted=pipeline_started,
        message="Sesión creada e inicializada correctamente.",
    )


@router.post("", response_model=GenerationSessionSummary, status_code=status.HTTP_202_ACCEPTED)
async def create_generation_session(payload: CreateSessionRequest,x_llm_api_key: Optional[str] = Header(None,alias="X-LLM-API-Key"),x_llm_provider: Optional[str] = Header(None,alias="X-LLM-Provider")):
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
            execution_mode=payload.executionMode,
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
            blueprint_dict=blueprint.model_dump(),
            api_key=x_llm_api_key,provider=x_llm_provider,model_name=payload.modelName
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
            executionMode=db_sess.execution_mode,
            verificationOutcome=verification_outcome(db_sess),
            queuePosition=pos,
            repairAttempts=db_sess.repair_attempts,
            createdAt=db_sess.created_at,
            startedAt=db_sess.started_at,
            completedAt=db_sess.completed_at,
            errorMessage=db_sess.error_message,
            # Feature 012 (FR-005): whether verification actually ran, read from
            # the persisted metrics so it survives a restart.
            verificationFallbackUsed=_verification_fallback_used(db_sess),
        )
    finally:
        db.close()

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_session(session_id: str):
    """Request cancellation; only the owning worker acknowledges its terminal state."""
    from app.services.pipeline_runner import cancel_pipeline
    from app.services.operation_repository import get_operation
    with SessionLocal() as db:
        row=db.get(GenerationSessionDB,session_id)
        if not row: raise HTTPException(404,'Session not found')
    if not cancel_pipeline(session_id): raise HTTPException(409,'No existe operación activa que cancelar')
    if session_id in GRAPH_CANCEL_EVENTS: GRAPH_CANCEL_EVENTS[session_id].set()
    return get_operation(session_id)

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

    from app.services.session_event_service import async_events, read_events
    try:
        after = int(request.headers.get('Last-Event-ID') or request.query_params.get('after') or '0')
    except ValueError:
        raise HTTPException(400, 'Cursor SSE inválido')
    read_events(session_id, after)  # Validate before response headers are sent.
    return EventSourceResponse(async_events(session_id, request, after))



from app.models.execution import ExecutionMode,ExecutionModeResponse,SessionVerificationResponse

class ExecutionModeRequest(BaseModel):
    executionMode: ExecutionMode


@router.patch('/{session_id}/execution-mode',response_model=ExecutionModeResponse)
async def change_execution_mode(session_id: str,payload: ExecutionModeRequest):
    from app.services.session_operation_lock import SessionOperationLock
    from app.services.operation_repository import get_operation,ACTIVE
    from app.services.local_runtime import latest
    operation=get_operation(session_id)
    if operation and operation['state'] in ACTIVE: raise HTTPException(409,'Existe una operación activa')
    lock=SessionOperationLock(session_id)
    if not lock.acquire(False): raise HTTPException(409,'Existe una operación activa')
    try:
        from app.services.operation_repository import transaction
        from app.models.reliability import PipelineOperation
        with SessionLocal() as db:
            transaction(db)
            if db.query(PipelineOperation).filter_by(session_id=session_id).filter(PipelineOperation.state.in_(ACTIVE)).first():
                raise HTTPException(409,'Existe una operación activa')
            session=db.get(GenerationSessionDB,session_id)
            if not session: raise HTTPException(404,'Session not found')
            if session.execution_mode==ExecutionMode.DOCKER and payload.executionMode==ExecutionMode.SOURCE_ONLY:
                deployment=latest(session_id)
                if deployment and deployment.state not in {'STOPPED','FAILED','CANCELLED'}:
                    raise HTTPException(409,'Detenga el despliegue propio antes de cambiar de modo')
            from app.services.draft_revision_service import update_execution_configuration
            update_execution_configuration(db,session,payload.executionMode.value)
            db.commit()
        return {'sessionId':session_id,'executionMode':payload.executionMode}
    finally: lock.release()


@router.post('/{session_id}/verify',response_model=SessionVerificationResponse)
async def retry_session_verification(session_id: str):
    from app.services.session_execution import verify_existing_sources
    return await asyncio.to_thread(verify_existing_sources,session_id)
