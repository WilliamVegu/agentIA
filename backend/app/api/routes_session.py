import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Header, HTTPException, status, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.models.execution import ExecutionMode, ExecutionModeResponse, SessionVerificationResponse
from app.services.execution_policy import execution_mode
from app.services.verification_policy import verification_outcome
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
from app.services.generated_code_fixes import (
    ensure_not_found_handler,
    normalise_generated_entities,
    normalise_generated_tests,
)
from app.services.lifecycle_artifacts import ensure_lifecycle_artifacts
from app.orchestrator.stages.runner import select_generation_mode
from app.services.conformance_diagnostics import record_session_diagnostics

router = APIRouter(prefix="/sessions", tags=["Sessions"])

# Session memory stores for live streaming & state inspection
SESSION_EVENT_HISTORY: Dict[str, List[dict]] = {}
SESSION_EVENT_SUBSCRIBERS: Dict[str, List[asyncio.Queue]] = {}
SESSION_GENERATION_STATE: Dict[str, Dict[str, Any]] = {}

class CreateSessionRequest(BaseModel):
    specId: str = Field(..., description="UUID of ingested specification")
    executionMode: ExecutionMode = ExecutionMode.SOURCE_ONLY
    modelName: Optional[str] = None


class ExecutionModeRequest(BaseModel):
    executionMode: ExecutionMode


@router.patch("/{session_id}/execution-mode", response_model=ExecutionModeResponse)
async def change_execution_mode(session_id: str, payload: ExecutionModeRequest):
    from app.services import docker_service
    from app.services.session_operation_lock import SessionOperationLock
    with docker_service._operations_lock:
        lock = docker_service._operation_locks.setdefault(session_id, SessionOperationLock(session_id))
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "Espere a que finalice la operación actual.")
    try:
        return _change_execution_mode(session_id, payload)
    finally:
        lock.release()


def _change_execution_mode(session_id: str, payload: ExecutionModeRequest):
    from app.services.docker_service import get_deployment_status
    from app.services.operation_repository import transaction, ACTIVE
    from app.models.reliability import PipelineOperation
    with SessionLocal() as db:
        transaction(db)
        row = db.get(GenerationSessionDB, session_id)
        if not row:
            raise HTTPException(404, "Session not found")
        if db.query(PipelineOperation).filter_by(session_id=session_id).filter(PipelineOperation.state.in_(ACTIVE)).first():
            raise HTTPException(409, "No se puede cambiar el modo durante una ejecución.")
        if row.execution_mode == ExecutionMode.DOCKER and payload.executionMode == ExecutionMode.SOURCE_ONLY:
            deployment = get_deployment_status(session_id)
            if deployment.status.value in ("BUILDING", "RUNNING", "HEALTHY", "DEGRADED"):
                raise HTTPException(409, "Detenga el despliegue antes de cambiar a sin Docker.")
        from app.services.draft_revision_service import update_execution_configuration
        update_execution_configuration(db,row,payload.executionMode.value)
        db.commit()
    return {"sessionId": session_id, "executionMode": payload.executionMode.value}


@router.post("/{session_id}/verify", response_model=SessionVerificationResponse)
async def retry_session_verification(session_id: str):
    from app.services.session_execution import verify_existing_sources
    return await asyncio.to_thread(verify_existing_sources, session_id)

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


def _record_session_cost(
    session_id: str,
    terminal_status: str,
    spec_name: Optional[str] = None,
    verification_fallback: bool = False,
    db_sess=None,
    db=None,
) -> None:
    """Roll call records into session cost record and persist to DB (H21)."""
    try:
        from app.cost.aggregate import aggregate_session
        record = aggregate_session(
            session_id=session_id,
            spec_name=spec_name or (getattr(db_sess, "spec_id", None) if db_sess else None),
            terminal_status=terminal_status,
            verification_fallback_used=verification_fallback,
        )
        if db_sess and record:
            db_sess.cost_record_json = json.dumps(record)
            if db:
                db.commit()
    except Exception:
        pass


def broadcast_session_event(session_id: str, event_type: str, data: dict):
    from app.services.session_event_service import publish_event
    return publish_event(session_id, event_type, data)


GRAPH_CANCEL_EVENTS: Dict[str, threading.Event] = {}

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


async def _execute_generation_pipeline_steps(
    session_id: str,
    spec_id: str,
    spec_name: str,
    blueprint_dict: dict,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
):
    """Background worker executing the LangGraph pipeline with concurrency controls."""
    GRAPH_CANCEL_EVENTS.setdefault(session_id, threading.Event())
    slot_acquired = False
    db = SessionLocal()
    try:
        # 1. Enqueue & await worker slot
        if not await queue_manager.acquire_slot(session_id):
            return
        slot_acquired = True

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
        # record it in the generation state (T018).
        #
        # The credentials must reach this call. Calling `select_generation_mode()`
        # with no arguments returns DETERMINISTIC for every request, so this route
        # used to emit offline templates while `/quick-start` emitted model output
        # -- two entry points, two different products, nothing in the response
        # distinguishing them. The caller's credentials arrive as the same
        # X-LLM-API-Key / X-LLM-Provider headers every other route already reads,
        # and `llm_api_key` must be placed in the state because `run_stage` builds
        # the model client from it.
        mode_selection = select_generation_mode(
            api_key=api_key,
            provider=provider,
            model_name=model_name,
        )
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
            # A DETERMINISTIC session records no provider or model, so it can
            # never be miscounted as model-generated. `mode_selection.provider`
            # and `.model` are populated only in MODEL mode.
            "llm_provider": mode_selection.provider,
            "llm_model": mode_selection.model,
            # Required: `run_stage` reads this to construct the client. Absent it,
            # a MODEL-mode session would fail at the first stage.
            "llm_api_key": api_key,
        }

        # Persist the artifacts this run was handed, before generating anything.
        #
        # The tabs read from the workspace, but this path writes only code -- no
        # spec.md, user_stories.json, architecture.json or schema.sql. Without this the
        # session showed its content during the run (from the frontend's state) and lost
        # it on reload: "the tabs are gone in history access". It is also what broke the
        # deploy, because `docker compose` creates a missing bind-mount source as a
        # DIRECTORY and Postgres then refused to read schema.sql as a SQL file.
        try:
            persisted = ensure_lifecycle_artifacts(ws_path, blueprint_dict)
            if persisted["written"]:
                print(f"[ARTIFACTS] persisted for {session_id}: {', '.join(persisted['written'])}")
            if persisted["skipped"]:
                print(f"[ARTIFACTS] left as they were: {', '.join(persisted['skipped'])}")
        except Exception as exc:  # noqa: BLE001
            # Never let artifact persistence stop a generation run; it is a fix for a
            # reporting gap, not a precondition for producing code.
            raise RuntimeError("No se pudieron persistir los artefactos de la revisión") from exc

        def run_graph_with_streaming():
            accumulated_state = dict(initial_state)
            current_phase = "INITIALIZATION"
            last_log_count = 0

            for step in generation_graph.stream(initial_state):
                if GRAPH_CANCEL_EVENTS.get(session_id) and GRAPH_CANCEL_EVENTS[session_id].is_set():
                    accumulated_state["status"] = "CANCELLED"
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

                # The entity classes now exist; correct the one defect that is
                # structurally predictable before anything compiles them.
                #
                # A generated `@NotNull` on a `@GeneratedValue` id makes Hibernate's
                # pre-insert Bean Validation reject every entity, because the id is
                # still null when it runs. Nothing reaches the database, so the
                # failure is silent at the SQL layer, and the generated service
                # returned 500 on every POST while GET worked and the build was green.
                # The test sources exist now; correct annotations the pinned Spring Boot
                # version does not provide, before the sandbox tries to compile them.
                if node_name == "test":
                    try:
                        fixed_tests = normalise_generated_tests(ws_path)
                        for path, what in fixed_tests.items():
                            print(f"[FIX] {path}: {'; '.join(what)} -> Spring Boot 3.2.3 compatible")
                    except Exception as exc:  # noqa: BLE001
                        print(f"[WARN] test normalisation failed: {type(exc).__name__}: {exc}")

                # The advice is written by now. Ensure an unmapped path is answered with
                # 404 rather than falling through to the generic handler's 500 -- the
                # deterministic emitter declares that handler and the model path does not.
                if node_name == "controller":
                    try:
                        for path, what in ensure_not_found_handler(ws_path).items():
                            print(f"[FIX] {path}: {what}")
                    except Exception as exc:  # noqa: BLE001
                        print(f"[WARN] 404 handler check failed: {type(exc).__name__}: {exc}")

                if node_name == "domain":
                    try:
                        corrected = normalise_generated_entities(ws_path)
                        for path, fields in corrected.items():
                            print(f"[FIX] removed @NotNull from generated id(s) in {path}: {', '.join(fields)}")
                    except Exception as exc:  # noqa: BLE001
                        print(f"[WARN] entity normalisation failed: {type(exc).__name__}: {exc}")

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
                    try:
                        with SessionLocal() as phase_db:
                            phase_row = phase_db.get(GenerationSessionDB, session_id)
                            if phase_row:
                                phase_row.phase = SessionPhase(next_phase)
                                phase_db.commit()
                    except Exception:
                        pass
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
        def run_owned_graph():
            from app.services.local_operations import borrowed_lock
            with borrowed_lock(session_id):
                return run_graph_with_streaming()
        graph_future = loop.run_in_executor(None, run_owned_graph)
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

        is_cancelled = (GRAPH_CANCEL_EVENTS.get(session_id) and GRAPH_CANCEL_EVENTS[session_id].is_set()) or (db_sess and db_sess.status == SessionStatus.CANCELLED)
        if is_cancelled:
            if db_sess:
                db_sess.status = SessionStatus.CANCELLED
                _record_session_cost(session_id, "CANCELLED", db_sess=db_sess, db=db)
                db.commit()
            _persist_diagnostics(session_id, final_state)
            await queue_manager.release_slot(session_id)
            return

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
                db_sess.phase = SessionPhase.CODE_GENERATION if metrics.get("verificationSkipped") else SessionPhase.VERIFIED
                db_sess.error_message = None
                db_sess.completed_at = datetime.now(timezone.utc)
                _persist_verification_metrics(db_sess, final_state)
                _record_session_cost(
                    session_id,
                    "COMPLETED",
                    verification_fallback=bool(metrics.get("fallback_used", False)),
                    db_sess=db_sess,
                    db=db,
                )
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
                "verificationSkipped": bool(metrics.get("verificationSkipped", False)),
                "totalTests": metrics.get("totalTests", 0),
                "passedTests": metrics.get("passedTests", 0),
                "failedTests": metrics.get("failedTests", 0),
                "durationMs": metrics.get("executionDurationMs", 0),
                "artifactCount": len(final_state.get("generated_files", {})),
                "downloadUrl": f"/api/v1/sessions/{session_id}/export"
            })
        else:
            # Blocked / Human intervention required
            blocked_metrics = final_state.get("test_metrics") or {}
            if db_sess:
                db_sess.status = SessionStatus.PAUSED if final_status == "PAUSED" else SessionStatus.BLOCKED
                db_sess.phase = SessionPhase.FAILED
                db_sess.error_message = final_state.get("error", "Human intervention required")
                db_sess.completed_at = datetime.now(timezone.utc)
                _persist_verification_metrics(db_sess, final_state)
                _record_session_cost(
                    session_id,
                    "BLOCKED",
                    verification_fallback=bool(blocked_metrics.get("fallback_used", False)),
                    db_sess=db_sess,
                    db=db,
                )
                db.commit()

            _persist_diagnostics(session_id, final_state)

            broadcast_session_event(session_id, "session_blocked", {
                "sessionId": session_id,
                "attempt": final_state.get("repair_attempts", 3),
                "maxAttempts": settings.MAX_REPAIR_ATTEMPTS,
                "failureReason": final_state.get("error", "Human intervention required"),
                "status": final_status,
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
            _record_session_cost(session_id, "BLOCKED", db_sess=db_sess, db=db)
            db.commit()
        broadcast_session_event(session_id, "session_blocked", {
            "sessionId": session_id,
            "failureReason": str(ex),
            "status": "BLOCKED"
        })
    finally:
        if slot_acquired:
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
            from app.services.verification_policy import session_is_verified
            if session_is_verified(s):
                pct = 100.0
            else:
                try:
                    lifecycle = get_session_lifecycle(s.id)
                    pct = lifecycle.completion_percentage
                    # Reading progress must never mutate execution status.
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
    spec_name = (payload.service_name or payload.spec_name or "app-service").strip()
    if not spec_name:
        spec_name = "app-service"

    text_content = (payload.raw_text or payload.prompt or "").strip()
    validate_target = text_content if text_content else spec_name

    if not validate_target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Por favor proporcione una descripción de requisitos o un nombre de microservicio.",
        )

    # Pre-flight Domain & Relevance Guardrail:
    # Verifies that the input request makes sense as a software microservice requirement
    # BEFORE creating workspace, database records, or starting background pipeline threads.
    try:
        from app.services.injection_guard import assert_no_injection, PromptInjectionError
        from app.services.specification_guard import (
            assert_looks_like_specification,
            UnlikelySpecificationError,
            verify_domain_relevance_llm,
            SpecAssessment,
        )

        assert_no_injection(validate_target, field="prompt")
        assert_looks_like_specification(validate_target, field="prompt")

        # If LLM credentials are provided and not mock, run fast semantic gate check
        if payload.api_key:
            is_valid, llm_reason = verify_domain_relevance_llm(
                validate_target,
                api_key=payload.api_key,
                provider=payload.llm_provider,
                model_name=payload.model_name,
            )
            if not is_valid:
                assessment = SpecAssessment(
                    plausible=False,
                    reasons=[llm_reason or "la solicitud no corresponde a un dominio de microservicio de software"],
                )
                raise UnlikelySpecificationError(assessment, field="prompt")

    except PromptInjectionError as injected:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=injected.to_dict())
    except UnlikelySpecificationError as unlikely:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=unlikely.to_dict())

    session_id = str(uuid.uuid4())
    spec_id = str(uuid.uuid4())

    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    if text_content:
        spec_file = ws_path / "spec.md"
        with open(spec_file, "w", encoding="utf-8") as f:
            f.write(f"# Feature Specification: {spec_name}\n\n{text_content}\n")

    db = SessionLocal()
    try:
        db_session = GenerationSessionDB(
            id=session_id,
            spec_id=spec_id,
            execution_mode=payload.execution_mode.value,
            database_engine=(payload.database_engine or "POSTGRESQL").upper(),
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
        run_pipeline(
            session_id,
            api_key=payload.api_key,
            provider=payload.llm_provider,
            model_name=payload.model_name,
            input_interface=payload.input_interface,
            auto_deploy=payload.auto_deploy,
        )
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
async def create_generation_session(
    payload: CreateSessionRequest,
    x_llm_api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
    x_llm_provider: Optional[str] = Header(default=None, alias="X-LLM-Provider"),
):
    """Triggers an autonomous generation session for an ingested specification.

    Reads the caller's LLM credentials from the same headers every other route
    uses. Without them this route silently selected DETERMINISTIC mode and emitted
    offline templates while `/quick-start` emitted model output (feature 011
    follow-up), so a client could not tell which product it had received.
    """
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
            execution_mode=payload.executionMode.value,
            database_engine=str(getattr(blueprint, "databaseMode", "POSTGRESQL")).upper(),
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
            blueprint_dict=blueprint.model_dump(),
            api_key=x_llm_api_key,
            provider=x_llm_provider,
            model_name=payload.modelName,
        )
    )

    return GenerationSessionSummary(
        sessionId=session_id,
        status=SessionStatus.QUEUED,
        queuePosition=position,
        executionMode=payload.executionMode,
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
            executionMode=db_sess.execution_mode,
            verificationOutcome=verification_outcome(db_sess),
            availableActions=["RETRY", "CONTINUE_WITHOUT_DOCKER"] if verification_outcome(db_sess).value == "ENVIRONMENT_UNAVAILABLE" else [],
            phase=db_sess.phase,
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

