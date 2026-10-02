from app.services.verification_policy import require_verified_session, session_is_verified, tests_really_passed, workspace_fingerprint, session_has_current_evidence
import json
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from app.config import settings
from app.models.orchestrator import (
    LifecyclePhase,
    PhaseStatus,
    PipelineExecutionMode,
    PipelineProgressEvent,
    PipelineRunStatus,
)
from app.models.session import GenerationSessionDB, SessionLocal, SessionPhase, SessionStatus
from app.services.lifecycle_service import (
    PHASE_ORDER,
    clear_outdated_phases,
    get_session_lifecycle,
    transition_phase,
)
from app.services.security_service import audit_workspace
from app.sandbox.docker_runner import parse_test_counts
from app.services.workspace_verification import run_workspace_verification
from app.services.conformance_diagnostics import record_session_diagnostics
from app.services.devops_service import generate_all_devops_assets
from app.services.docker_service import deploy_local
from app.models.blueprint import DomainEntity, EntityAttribute, UserStoryRecord, AcceptanceScenarioRecord
from app.models.requirements import SpecificationDraft
from app.services.llm_factory import LLMFactory
from app.services.requirements_service import (
    _generate_mock_decomposition,
    serialize_draft_to_markdown,
    transform_requirements,
    RequirementsTransformRequest,
)
from app.services.architecture_service import design_architecture, ArchitectureDesignRequest
from app.services.model_sql_service import model_sql_service, schema_sql_from_draft
# Feature 011 (T019): the sequential path now dispatches through the stage
# execution boundary instead of calling the five node callables directly. The
# boundary owns mode selection, budgeting, gating and provenance; the retained
# node implementations are reached through it and remain unmodified.
from app.orchestrator.stages import journal as generation_journal
from app.orchestrator.stages.runner import (
    STAGE_ORDER as GENERATION_STAGE_ORDER,
    run_stages as run_generation_stages,
    select_generation_mode,
)

# Thread-safe in-memory tracking
_active_threads: Dict[str, threading.Thread] = {}
_pause_events: Dict[str, threading.Event] = {}
_stop_events: Dict[str, threading.Event] = {}
_event_queues: Dict[str, queue.Queue] = {}
_pipeline_statuses: Dict[str, PipelineRunStatus] = {}
_session_credentials: Dict[str, Dict[str, Optional[str]]] = {}


def _get_queue(session_id: str) -> queue.Queue:
    if session_id not in _event_queues:
        _event_queues[session_id] = queue.Queue()
    return _event_queues[session_id]


def _emit_event(session_id: str, phase: LifecyclePhase, step: str, percent: float, message: str, status: PhaseStatus, error: Optional[str] = None):
    evt = PipelineProgressEvent(
        timestamp=datetime.now(timezone.utc),
        sessionId=session_id,
        phase=phase,
        step=step,
        percent=percent,
        message=message,
        status=status,
        error=error,
    )
    _get_queue(session_id).put(evt)

    try:
        from app.api.routes_session import broadcast_session_event
        broadcast_session_event(session_id, "pipeline_progress", {
            "sessionId": session_id,
            "phase": phase.value if hasattr(phase, "value") else str(phase),
            "stage": phase.value if hasattr(phase, "value") else str(phase),
            "step": step,
            "percent": percent,
            "message": message,
            "status": status.value if hasattr(status, "value") else str(status),
            "error": error,
            "log": f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] [{step}] {message}"
        })
    except Exception:
        pass


def _finalise_blocked_session(session_id: str, state: Dict[str, Any]) -> None:
    """Move a stage-exhausted session to its terminal state and record the evidence.

    **This is the exhaustion-path fix.** The branch this replaces set an in-memory
    pipeline status and returned: the session row stayed in its pre-run state
    forever, and no diagnostic record was written. The artifacts themselves were
    never lost -- which is exactly why it mattered, because nothing recorded them.
    A blocked session is the one most worth diagnosing, so it was the worst path to
    leave undiagnosed, and it also broke the "every session reaching a terminal
    state carries a record" guarantee (FR-001, SC-001).

    State, terminal status and evidence are written together because they are one
    fact: the session ended, here is why, and here is what was found wrong.
    """
    reason = state.get("error") or "Generation stages blocked; human intervention required"

    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if sess:
            sess.status = SessionStatus.BLOCKED
            sess.phase = SessionPhase.FAILED
            sess.error_message = reason
            sess.completed_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        # Never fatal: a session that cannot be marked must still be diagnosed.
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()

    # The one writer, shared with the graph path. It never raises; the return value
    # is deliberately ignored here because the pipeline has no caller to report to,
    # and the record's absence is visible in the corpus report regardless.
    record_session_diagnostics(session_id, state)


def get_pipeline_status(session_id: str) -> PipelineRunStatus:
    return _pipeline_statuses.get(session_id, PipelineRunStatus.IDLE)


def pause_pipeline(session_id: str) -> bool:
    """Signals an active Auto-Pilot thread to pause cooperatively and switch to Guided Step mode."""
    if session_id not in _pause_events or not _active_threads.get(session_id) or not _active_threads[session_id].is_alive():
        return False

    _pause_events[session_id].set()
    _pipeline_statuses[session_id] = PipelineRunStatus.PAUSED

    # Update DB to GUIDED_STEP and PAUSED
    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if sess:
            sess.status = SessionStatus.PAUSED
            sess.lifecycle_mode = PipelineExecutionMode.GUIDED_STEP.value
            db.commit()
            return True
    finally:
        db.close()
    return True


def resume_pipeline(session_id: str) -> bool:
    """Resumes a paused Auto-Pilot pipeline."""
    previous = _active_threads.get(session_id)
    if previous and previous.is_alive():
        previous.join(timeout=1.0)
        if previous.is_alive():
            return False
    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if sess:
            sess.status = SessionStatus.RUNNING
            sess.lifecycle_mode = PipelineExecutionMode.AUTO_PILOT.value
            db.commit()
    finally:
        db.close()

    creds = _session_credentials.get(session_id, {})
    return run_pipeline(
        session_id,
        api_key=creds.get("api_key"),
        provider=creds.get("provider"),
        model_name=creds.get("model_name"),
        force=True,
    )


def cancel_pipeline(session_id: str) -> bool:
    """Signals an active Auto-Pilot thread to cancel immediately and marks status as CANCELLED."""
    if session_id in _stop_events:
        _stop_events[session_id].set()
    if session_id in _pause_events:
        _pause_events[session_id].set()
    _pipeline_statuses[session_id] = PipelineRunStatus.CANCELLED

    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if sess:
            sess.status = SessionStatus.CANCELLED
            db.commit()
    finally:
        db.close()

    _record_pipeline_cost(session_id, terminal_status="CANCELLED")

    _emit_event(
        session_id,
        LifecyclePhase.COMPLETED,
        "CANCEL",
        0.0,
        "Pipeline cancelado por el usuario.",
        PhaseStatus.BLOCKED,
    )
    return True



def describe_block_reason(*, fallback_used: bool, fallback_reason: str = "") -> str:
    """Why the session is blocked, in the caller's terms.

    The distinction this exists to preserve: **the code failed** versus **the code was never
    measured**. They call for opposite responses -- fix the code, or fix the environment --
    and a single hardcoded sentence conflated them:

        "La compilación o pruebas unitarias fallaron en el sandbox hermético."

    That was emitted for every block, including runs where the sandbox never executed a
    build. Reported from a real session whose recorded reason was an unresolvable offline
    Maven cache; the operator was told to look at their generated code.
    """
    if fallback_used:
        detail = f" Motivo: {fallback_reason}" if fallback_reason else ""
        return (
            "No se pudo verificar el código: el sandbox hermético no llegó a ejecutar la "
            f"compilación, así que no hay resultado de pruebas.{detail}"
        )
    return "La compilación o las pruebas unitarias fallaron en el sandbox hermético."

def _record_pipeline_cost(
    session_id: str,
    terminal_status: str,
    spec_name: Optional[str] = None,
    verification_fallback: bool = False,
) -> None:
    """Record cost aggregation for pipeline run (H21)."""
    try:
        import json
        from app.cost.aggregate import aggregate_session
        record = aggregate_session(
            session_id=session_id,
            spec_name=spec_name,
            terminal_status=terminal_status,
            verification_fallback_used=verification_fallback,
        )
        if record:
            db = SessionLocal()
            try:
                s = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
                if s:
                    s.cost_record_json = json.dumps(record)
                    db.commit()
            finally:
                db.close()
    except Exception:
        pass


def _complete_target_phase(session_id: str, phase: LifecyclePhase, target_phase_label: str) -> None:
    """Finish the requested run; keep unverified partial projects paused."""
    _pipeline_statuses[session_id] = PipelineRunStatus.COMPLETED
    _emit_event(session_id, phase, "Meta Alcanzada", 100.0, f"Auto-Pilot completó la fase objetivo: {target_phase_label}", PhaseStatus.COMPLETED)
    verified = False
    db = SessionLocal()
    try:
        s = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if s:
            verified = session_has_current_evidence(s)
            s.status = SessionStatus.COMPLETED if verified else SessionStatus.PAUSED
            if verified:
                s.phase = SessionPhase.VERIFIED
            s.current_lifecycle_phase = phase.value
            s.completed_at = datetime.now(timezone.utc) if verified else None
            db.commit()
    finally:
        db.close()
    _record_pipeline_cost(session_id, terminal_status="COMPLETED" if verified else "PAUSED")



def _derive_architecture_from_draft(draft: SpecificationDraft) -> dict:
    """Deterministic per-entity 4-layer architecture (offline/no-key path).

    Replaces the removed mock generator: the architecture is DERIVED from the
    draft's entities (a component per entity per layer), never fabricated.
    """
    entities = draft.entities or []
    components = []
    edges = []
    for e in entities:
        components.append({"name": f"{e.name}Controller", "layer": "controller", "dependencies": [f"{e.name}Service"]})
        components.append({"name": f"{e.name}Service", "layer": "service", "dependencies": [f"{e.name}Repository"]})
        components.append({"name": f"{e.name}Repository", "layer": "repository", "dependencies": [e.name]})
        components.append({"name": e.name, "layer": "model", "dependencies": []})
        edges.append(f"    {e.name}Controller --> {e.name}Service")
        edges.append(f"    {e.name}Service --> {e.name}Repository")
        edges.append(f"    {e.name}Repository --> {e.name}")
    components.append({"name": "GlobalExceptionHandler", "layer": "infrastructure", "dependencies": []})
    mermaid = "graph TD\n" + "\n".join(edges) if edges else "graph TD"
    return {
        "serviceName": draft.serviceName,
        "packageName": draft.packageName,
        "basePort": draft.basePort,
        "components": components,
        "endpoints": [],
        "mermaidDiagram": mermaid,
    }


def _get_or_create_draft(ws_path: Path, spec_name: str, api_key: Optional[str] = None, provider: Optional[str] = None, model_name: Optional[str] = None) -> SpecificationDraft:
    spec_file = ws_path / "spec.md"
    raw_prompt = spec_name
    if spec_file.exists():
        try:
            content = spec_file.read_text(encoding="utf-8")
            if len(content.strip()) > 10:
                raw_prompt = content.strip()
        except Exception:
            pass

    draft = None
    if api_key and not LLMFactory.is_mock(api_key, provider):
        # A real key was supplied: the LLM MUST produce the draft. A silent fallback
        # to a hardcoded decomposition here is exactly the "garbage session" a model-
        # mode autopilot must never fabricate -- let it raise so the pipeline blocks.
        draft = transform_requirements(
            RequirementsTransformRequest(rawText=raw_prompt, serviceName=spec_name, provider=provider, modelName=model_name),
            api_key=api_key,
            provider=provider,
            model_name=model_name,
        )

    if draft is None:
        decomp = _generate_mock_decomposition(raw_text=raw_prompt, service_name=spec_name)
        entities = []
        for ent in decomp.entities:
            attrs = list(ent.attributes)
            if not any(getattr(a, "isPrimaryKey", False) for a in attrs):
                attrs.insert(0, EntityAttribute(name="id", type="Long", isPrimaryKey=True))
            entities.append(
                DomainEntity(
                    name=ent.name,
                    tableName=ent.tableName,
                    attributes=attrs,
                )
            )

        user_stories = []
        for st_idx, st in enumerate(decomp.userStories, start=1):
            scenarios = [
                AcceptanceScenarioRecord(
                    scenarioId=getattr(sc, "scenarioId", f"AC-{st_idx}.{sc_idx}"),
                    given=sc.given.strip(),
                    when=sc.when.strip(),
                    then=sc.then.strip(),
                )
                for sc_idx, sc in enumerate(st.scenarios, start=1)
            ]
            user_stories.append(
                UserStoryRecord(
                    id=f"US-{st_idx}",
                    priority=st.priority,
                    role=st.role,
                    intent=st.intent,
                    benefit=st.benefit,
                    scenarios=scenarios,
                )
            )

        draft = SpecificationDraft(
            serviceName=decomp.serviceName,
            packageName=decomp.packageName,
            basePort=8080,
            entities=entities,
            userStories=user_stories,
            assumptions=decomp.assumptions,
        )
        draft.markdownSpec = serialize_draft_to_markdown(draft)
    return draft


def _execute_pipeline_steps(
    session_id: str,
    target_phase: LifecyclePhase,
    stop_on_gate: bool,
    auto_deploy: bool,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    input_interface: Optional[dict] = None,
):
    """Executes each lifecycle phase sequentially in the background."""
    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    pause_event = _pause_events[session_id]
    stop_event = _stop_events[session_id]
    slot_acquired = False

    try:
        from app.services.queue_service import queue_manager
        if not queue_manager.acquire_slot_sync(session_id, stop_event):
            return
        slot_acquired = True

        # Everything below sits inside the handler, including the mode decision and the
        # instruction-set load. It used to start after them, so a failure there -- an
        # ambiguous API key, an unloadable instruction set on the MODEL path -- escaped
        # the function entirely. The caller is a daemon thread, so the exception died
        # with it: the session row stayed RUNNING and the operator watched a pipeline
        # that had already stopped. Failing loudly (invariant 11) is the intent; failing
        # silently *to the operator* was not.
        detected_llm = LLMFactory.detect_provider(api_key, provider)
        is_mock = LLMFactory.is_mock(api_key, provider)
        active_model = "offline-mock" if is_mock else LLMFactory.resolve_model_name(detected_llm, model_name)
        llm_label = "Modo Mock (Offline)" if is_mock else f"Motor LLM: {detected_llm.upper()} ({active_model})"

        def _phase_reached_or_exceeded(current_p: LifecyclePhase) -> bool:
            if not target_phase:
                return False
            phase_seq = [
                LifecyclePhase.REQUIREMENTS,
                LifecyclePhase.STORIES,
                LifecyclePhase.ARCHITECTURE,
                LifecyclePhase.DATA_MODEL,
                LifecyclePhase.CODE_TESTS,
                LifecyclePhase.SECURITY_AUDIT,
                LifecyclePhase.DEVOPS_DEPLOY,
                LifecyclePhase.COMPLETED,
            ]
            tgt = target_phase
            if isinstance(tgt, str):
                try:
                    tgt = LifecyclePhase(tgt)
                except Exception:
                    return False
            try:
                return phase_seq.index(current_p) >= phase_seq.index(tgt)
            except ValueError:
                return False

        # Feature 011 (T018): the generation mode is decided ONCE, here, before any
        # stage runs, and recorded in the generation state. Deciding per stage would
        # produce hybrid output (some artifacts template-shaped, some model-shaped)
        # and make the SC-001/SC-002 comparisons uninterpretable.
        mode_selection = select_generation_mode(
            api_key=api_key,
            provider=provider,
            model_name=model_name,
        )
        generation_mode = mode_selection.mode
        if generation_mode == generation_journal.GENERATION_MODE_MODEL:
            model_provider: Optional[str] = mode_selection.provider
            model_name_for_state: Optional[str] = mode_selection.model
        else:
            # A DETERMINISTIC session must record no provider or model, so it can
            # never be miscounted as model-generated.
            model_provider = None
            model_name_for_state = None
        instruction_revision = ""
        try:
            from app.orchestrator.stages.instructions import load_instruction_set
            instruction_revision = load_instruction_set().revision
        except Exception as exc:  # noqa: BLE001
            # The deterministic path does not read instructions, so a missing or
            # invalid instruction set must not break offline operation. In MODEL mode
            # the boundary loads the set itself and fails loudly (invariant 11).
            if generation_mode == generation_journal.GENERATION_MODE_MODEL:
                raise
            instruction_revision = ""
            print(f"[WARN] instruction set not loaded for deterministic session: {exc}")

        db = SessionLocal()
        spec_name = "Microservicio"
        try:
            sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
            if sess and sess.spec_name:
                spec_name = sess.spec_name
        finally:
            db.close()

        _emit_event(session_id, LifecyclePhase.INITIAL, "Inicio", 5.0, f"Iniciando pipeline autónomo Auto-Pilot [{llm_label}]...", PhaseStatus.IN_PROGRESS)

        # Step 1: Requirements Check / Spec
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.REQUIREMENTS, "Especificación", 15.0, f"Sintetizando especificación y entidades de dominio [{llm_label}]...", PhaseStatus.IN_PROGRESS)
        draft = _get_or_create_draft(ws_path, spec_name, api_key=api_key, provider=provider, model_name=model_name)
        spec_file = ws_path / "spec.md"
        if not spec_file.exists():
            with open(spec_file, "w", encoding="utf-8") as f:
                f.write(draft.markdownSpec)
        transition_phase(session_id, LifecyclePhase.REQUIREMENTS, force=True)
        time.sleep(0.2)
        if _phase_reached_or_exceeded(LifecyclePhase.REQUIREMENTS):
            _complete_target_phase(session_id, LifecyclePhase.REQUIREMENTS, str(target_phase))
            return

        # Step 2: User Stories
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.STORIES, "Historias de Usuario", 30.0, f"Registrando historias de usuario y criterios de aceptación BDD [{llm_label}]...", PhaseStatus.IN_PROGRESS)
        stories_file = ws_path / "user_stories.json"
        if not stories_file.exists():
            stories_data = [story.model_dump() for story in draft.userStories]
            with open(stories_file, "w", encoding="utf-8") as f:
                json.dump(stories_data, f, indent=2)
        transition_phase(session_id, LifecyclePhase.STORIES, force=True)
        time.sleep(0.2)
        if _phase_reached_or_exceeded(LifecyclePhase.STORIES):
            _complete_target_phase(session_id, LifecyclePhase.STORIES, str(target_phase))
            return

        # Step 3: Architecture Blueprint
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.ARCHITECTURE, "Diseño Arquitectónico", 45.0, f"Generando topología solicitada y catálogo DTO [{llm_label}]...", PhaseStatus.IN_PROGRESS)
        arch_file = ws_path / "architecture.json"
        if not arch_file.exists():
            if api_key and not LLMFactory.is_mock(api_key, provider):
                # Model mode: the LLM must produce the architecture. No silent
                # hardcoded fallback -- let it raise so the pipeline blocks.
                arch_req = ArchitectureDesignRequest(draft=draft, apiKey=api_key, provider=provider, modelName=model_name, architecturePreference=(input_interface or {}).get("architecturePreference"))
                arch_resp = design_architecture(arch_req, api_key=api_key, provider=provider)
                arch_data = arch_resp.model_dump()
            else:
                # Offline/no-key path: derive per-entity architecture, not a hardcoded list.
                arch_data = _derive_architecture_from_draft(draft)
            with open(arch_file, "w", encoding="utf-8") as f:
                json.dump(arch_data, f, indent=2)
            arch_md = ws_path / "architecture.md"
            if not arch_md.exists() and "mermaidDiagram" in arch_data:
                arch_md.write_text(f"# Arquitectura: {spec_name}\n\n```mermaid\n{arch_data.get('mermaidDiagram', '')}\n```\n", encoding="utf-8")
        transition_phase(session_id, LifecyclePhase.ARCHITECTURE, force=True)
        time.sleep(0.2)
        if _phase_reached_or_exceeded(LifecyclePhase.ARCHITECTURE):
            _complete_target_phase(session_id, LifecyclePhase.ARCHITECTURE, str(target_phase))
            return

        # Step 4: Data Models & SQL
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.DATA_MODEL, "Modelo de Datos", 60.0, f"Generando esquema SQL relacional y entidades de persistencia [{llm_label}]...", PhaseStatus.IN_PROGRESS)
        sql_file = ws_path / "schema.sql"
        if not sql_file.exists():
            try:
                sql_resp = model_sql_service.synthesize_domain_models_and_sql(draft, api_key=api_key, provider=provider, model_name=model_name)
                with open(sql_file, "w", encoding="utf-8") as f:
                    f.write(sql_resp.sqlSchema.schemaDdl)
                data_sql_file = ws_path / "data.sql"
                if not data_sql_file.exists() and sql_resp.sqlSchema.seedDml:
                    with open(data_sql_file, "w", encoding="utf-8") as f:
                        f.write(sql_resp.sqlSchema.seedDml)
                model_file = ws_path / "domain_model.json"
                if not model_file.exists():
                    with open(model_file, "w", encoding="utf-8") as f:
                        json.dump(sql_resp.model_dump(), f, indent=2)
            except Exception as exc:
                # Derive the DDL from THIS blueprint's entities instead of failing the run.
                #
                # A later refactor replaced this with a bare `raise`, which killed the session
                # whenever synthesis failed -- and left `schema_sql_from_draft` imported and
                # unused, the tell that it was collateral rather than a decision. Raising is
                # not the more honest option here: the fallback is derived from the blueprint
                # the session is actually building, not invented, and `lifecycle_artifacts`
                # still uses this same function for the same purpose. Failing the run also
                # removed the regression guard for the `items`-table defect: a project whose
                # schema said `items` while its entity mapped `orders` could not start against
                # its own database.
                print(f"[WARN] schema synthesis failed ({exc}); deriving DDL from the blueprint")
                fallback_ddl = schema_sql_from_draft(draft)
                with open(sql_file, "w", encoding="utf-8") as f:
                    f.write(fallback_ddl)
        transition_phase(session_id, LifecyclePhase.DATA_MODEL, force=True)
        time.sleep(0.2)
        if _phase_reached_or_exceeded(LifecyclePhase.DATA_MODEL):
            _complete_target_phase(session_id, LifecyclePhase.DATA_MODEL, str(target_phase))
            return

        # Step 5: Code & Tests
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.CODE_TESTS, "Código & Pruebas", 75.0, "Estructurando proyecto Spring Boot 3, entidades JPA y suites Mockito...", PhaseStatus.IN_PROGRESS)
        pom_file = ws_path / "pom.xml"
        src_java = ws_path / "src" / "main" / "java"
        has_java = src_java.exists() and any(src_java.glob("**/*.java"))
        if not (pom_file.exists() and has_java):
            blueprint_dict = {
                "serviceName": draft.serviceName,
                "packageName": draft.packageName,
                "basePort": draft.basePort,
                "entities": [e.model_dump() for e in draft.entities],
                "userStories": [s.model_dump() for s in draft.userStories],
            }
            # Wire the "interfaz de entrada" (volume/data/integrations/architecture)
            # so the deterministic scaffolder's InferenceEngine actually decides the
            # architecture (layered vs multi-module) and DB target instead of falling
            # back to the hardcoded default.
            if input_interface:
                blueprint_dict["inputInterface"] = input_interface
            agent_state = {
                "session_id": session_id,
                "blueprint": blueprint_dict,
                "workspace_path": str(ws_path),
                "generated_files": {},
                "logs": [],
                # Recorded once for the whole session (T018).
                "generation_mode": generation_mode,
                "instruction_set_revision": instruction_revision,
                "llm_provider": model_provider,
                "llm_model": model_name_for_state,
                "llm_api_key": api_key,
            }
            # T019 / research D8: consume the RETURNED state. The previous code
            # called the five node callables and discarded their return values,
            # which worked only because those nodes mutate the dicts retrieved
            # from state in place. A model-driven stage that builds a fresh dict
            # would have silently produced an empty workspace, surfacing as a
            # downstream security-audit or DevOps anomaly rather than a
            # generation bug.
            agent_state = run_generation_stages(
                agent_state,
                stages=GENERATION_STAGE_ORDER,
                api_key=api_key,
            )
            generated_count = len(agent_state.get("generated_files", {}) or {})
            print(
                f"[INFO] generation stages complete: mode={generation_mode}, "
                f"artifacts={generated_count}, "
                f"requests={(agent_state.get('generation_journal') or {}).get('total_requests', 0)}"
            )
            if agent_state.get("status") == SessionStatus.BLOCKED.value:
                _emit_event(
                    session_id,
                    LifecyclePhase.CODE_TESTS,
                    "Bloqueo por intervención humana requerida",
                    75.0,
                    agent_state.get("error") or "Generation stages blocked.",
                    PhaseStatus.BLOCKED,
                    error=agent_state.get("error"),
                )
                _pipeline_statuses[session_id] = PipelineRunStatus.AWAITING_INTERVENTION
                _finalise_blocked_session(session_id, agent_state)
                return
        transition_phase(session_id, LifecyclePhase.CODE_TESTS, force=True)
        time.sleep(0.2)

        # Step 5b: HERMETIC VERIFICATION.
        #
        # This path used to generate code and go straight to the static audit --
        # it never compiled or tested anything. So on the route the readiness
        # report tells clients to use, the acceptance signal was not merely
        # generator-authored: it did not exist. The graph path had verification
        # because `sandbox_node` owned it; the sequence of "strip VCS, inject the
        # platform contract test, build" now lives in one seam
        # (`run_workspace_verification`) so the two paths cannot drift.
        #
        # A build that could not run is NOT a pass: `result.fallback_used` marks a
        # substituted result, and the session is reported as unverified rather than
        # silently reaching a verified state (feature 012, FR-005).
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(
            session_id, LifecyclePhase.CODE_TESTS, "Verificación hermética",
            78.0, "Compilando y ejecutando la suite en el sandbox offline (mvn test -o)...",
            PhaseStatus.IN_PROGRESS,
        )
        generate_all_devops_assets(str(ws_path), session_id, service_name=spec_name)
        verification_logs: List[str] = []
        try:
            verification = run_workspace_verification(
                str(ws_path), log_callback=verification_logs.append
            )
        except Exception as exc:  # noqa: BLE001
            # A verifier that raises has verified nothing. Recording that honestly
            # is the whole point: an exception must not become a pass.
            verification = None
            verification_error: Optional[str] = f"{type(exc).__name__}: {exc}"
        else:
            verification_error = None

        if verification is None:
            build_success = False
            test_metrics = {
                "totalTests": 0, "passedTests": 0, "failedTests": 0,
                "allPassed": False, "fallback_used": True,
                "fallback_reason": f"the verifier raised: {verification_error}",
            }
        else:
            build_success = bool(verification.result.is_success)
            counts = parse_test_counts(verification.result.stdout)
            test_metrics = {
                "totalTests": counts.total if counts else 0,
                "passedTests": counts.passed if counts else 0,
                "failedTests": ((counts.failures + counts.errors) if counts else 0),
                # Fail closed: a build that reports success without printing a test
                # summary has not demonstrated that any test ran.
                "allPassed": bool(counts and counts.all_passed and counts.total > 0),
                "fallback_used": bool(verification.result.fallback_used),
                "fallback_reason": verification.result.fallback_reason,
                "platformContractTestInjected": verification.platform_verified,
                "workspaceFingerprint": workspace_fingerprint(ws_path),
            }

        build_success = build_success and tests_really_passed(test_metrics)

        # Persist onto the session row, so the detail endpoint can report whether
        # verification actually ran even after a restart (feature 012, T019).
        try:
            _session_db = SessionLocal()
            try:
                _row = (
                    _session_db.query(GenerationSessionDB)
                    .filter(GenerationSessionDB.id == session_id)
                    .first()
                )
                if _row is not None:
                    _row.verification_metrics_json = json.dumps(test_metrics)
                    _session_db.commit()
            finally:
                _session_db.close()
        except Exception:  # noqa: BLE001
            pass

        _emit_event(
            session_id, LifecyclePhase.CODE_TESTS,
            "Verificación hermética completada" if build_success else ("Verificación hermética omitida (sandbox inaccesible)" if (verification and verification.result.fallback_used) else "Verificación hermética fallida"),
            80.0,
            (
                f"BUILD SUCCESS: {test_metrics['passedTests']}/{test_metrics['totalTests']} tests"
                if build_success
                else ("Sandbox Docker no disponible; verificación no ejecutada" if (verification and verification.result.fallback_used)
                else "La compilación o las pruebas fallaron en el sandbox hermético")
            ),
            PhaseStatus.COMPLETED if build_success else PhaseStatus.BLOCKED,
            error=None if build_success else "Hermetic verification failed.",
        )
        time.sleep(0.2)

        if not build_success:
            # The reason below is the one the caller actually acted on, and it used to be a
            # hardcoded constant: "La compilación o pruebas unitarias fallaron en el sandbox
            # hermético." That was false whenever the sandbox could not run at all -- a
            # missing local dependency, an unreachable daemon, a cold offline cache -- and it
            # accused the generated code of a failure that had never been measured. A run
            # whose verification was never performed must say so, because the operator's next
            # move is completely different: fix the environment, not the code.
            _fallback = bool(verification and verification.result.fallback_used)
            _reason = (verification.result.fallback_reason if verification else None) or ""
            blocked_reason = describe_block_reason(
                fallback_used=_fallback, fallback_reason=_reason
            )

            _pipeline_statuses[session_id] = PipelineRunStatus.AWAITING_INTERVENTION
            db_fail = SessionLocal()
            try:
                s = db_fail.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
                if s:
                    s.status = SessionStatus.BLOCKED
                    s.phase = SessionPhase.FAILED
                    # Recorded truthfully: this column is read back by the session view.
                    s.error_message = blocked_reason
                    db_fail.commit()
            finally:
                db_fail.close()

            _record_pipeline_cost(session_id, terminal_status="BLOCKED")

            try:
                from app.api.routes_session import broadcast_session_event
                broadcast_session_event(session_id, "session_blocked", {
                    "sessionId": session_id,
                    "attempt": 0,
                    "maxAttempts": settings.MAX_REPAIR_ATTEMPTS,
                    "failureReason": blocked_reason,
                    # Distinguishes "your code failed" from "we could not check". The UI
                    # needs it to avoid sending the operator to debug code that never ran.
                    "verificationPerformed": not _fallback,
                    "verificationFallbackReason": _reason or None,
                    "status": "BLOCKED",
                })
            except Exception:
                pass
            return

        transition_phase(session_id, LifecyclePhase.CODE_TESTS, force=True)
        time.sleep(0.2)
        if _phase_reached_or_exceeded(LifecyclePhase.CODE_TESTS):
            _complete_target_phase(session_id, LifecyclePhase.CODE_TESTS, str(target_phase))
            return

        # Step 6: Security Audit & Quality Gate
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.SECURITY_AUDIT, "Auditoría de Seguridad", 85.0, "Ejecutando escaneo estático SAST y verificación de Quality Gate...", PhaseStatus.IN_PROGRESS)
        audit = audit_workspace(str(ws_path), session_id, spec_name)
        if stop_on_gate and audit.qualityGate.status == "BLOCKED":
            _emit_event(
                session_id,
                LifecyclePhase.SECURITY_AUDIT,
                "Compuerta de Calidad Bloqueada",
                85.0,
                f"🛑 Quality Gate BLOQUEADO: {audit.qualityGate.summaryMessage}",
                PhaseStatus.BLOCKED,
                error=audit.qualityGate.summaryMessage,
            )
            _pipeline_statuses[session_id] = PipelineRunStatus.AWAITING_INTERVENTION
            db_gate = SessionLocal()
            try:
                row = db_gate.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
                if row:
                    row.status = SessionStatus.BLOCKED
                    row.error_message = audit.qualityGate.summaryMessage
                    db_gate.commit()
            finally:
                db_gate.close()
            _record_pipeline_cost(session_id, terminal_status="BLOCKED")
            return

        transition_phase(session_id, LifecyclePhase.SECURITY_AUDIT, force=True)
        time.sleep(0.3)
        if _phase_reached_or_exceeded(LifecyclePhase.SECURITY_AUDIT):
            _complete_target_phase(session_id, LifecyclePhase.SECURITY_AUDIT, str(target_phase))
            return

        # Step 7: DevOps & Deploy
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.DEVOPS_DEPLOY, "DevOps & Manifiestos", 95.0, "Generando Dockerfile, Compose, CI/CD y manifiestos Kubernetes...", PhaseStatus.IN_PROGRESS)
        generate_all_devops_assets(str(ws_path), session_id, spec_name)

        if auto_deploy:
            _emit_event(session_id, LifecyclePhase.DEVOPS_DEPLOY, "Despliegue Local", 98.0, "Orquestando contenedores en Docker local...", PhaseStatus.IN_PROGRESS)
            deploy_local(session_id, str(ws_path))

        transition_phase(session_id, LifecyclePhase.DEVOPS_DEPLOY, force=True)
        clear_outdated_phases(session_id)

        _emit_event(session_id, LifecyclePhase.COMPLETED, "Finalizado", 100.0, "🎉 ¡Pipeline completado con éxito! Todos los artefactos están listos.", PhaseStatus.COMPLETED)
        _pipeline_statuses[session_id] = PipelineRunStatus.COMPLETED

        try:
            from app.api.routes_session import broadcast_session_event
            broadcast_session_event(session_id, "session_completed", {
                "sessionId": session_id,
                "status": "COMPLETED",
                "message": "Pipeline completado con éxito.",
                "percent": 100.0,
                "artifactCount": 10,
                "downloadUrl": f"/api/v1/sessions/{session_id}/export"
            })
        except Exception:
            pass

        db_comp = SessionLocal()
        try:
            s = db_comp.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
            if s:
                s.status = SessionStatus.COMPLETED
                is_truly_verified = bool(build_success and not (verification and verification.result.fallback_used))
                s.phase = SessionPhase.VERIFIED if is_truly_verified else SessionPhase.CODE_GENERATION
                s.current_lifecycle_phase = LifecyclePhase.COMPLETED.value
                s.completed_at = datetime.now(timezone.utc)
                db_comp.commit()
        finally:
            db_comp.close()

        _record_pipeline_cost(session_id, terminal_status="COMPLETED")

    except Exception as e:
        _emit_event(session_id, LifecyclePhase.INITIAL, "Error", 0.0, f"Error en ejecución de pipeline: {str(e)}", PhaseStatus.BLOCKED, error=str(e))
        _pipeline_statuses[session_id] = PipelineRunStatus.FAILED

        try:
            from app.api.routes_session import broadcast_session_event
            broadcast_session_event(session_id, "session_blocked", {
                "sessionId": session_id,
                "status": "BLOCKED",
                "failureReason": str(e),
                "error": str(e)
            })
        except Exception:
            pass

        db_err = SessionLocal()
        try:
            s = db_err.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
            if s:
                s.status = SessionStatus.BLOCKED
                s.error_message = str(e)
                db_err.commit()
        finally:
            db_err.close()

        _record_pipeline_cost(session_id, terminal_status="FAILED")
    finally:
        try:
            from app.services.queue_service import queue_manager
            if slot_acquired:
                queue_manager.release_slot_sync(session_id)
        except Exception:
            pass
        if stop_event.is_set():
            db_cancel = SessionLocal()
            try:
                row = db_cancel.get(GenerationSessionDB, session_id)
                if row:
                    row.status = SessionStatus.CANCELLED
                    db_cancel.commit()
            finally:
                db_cancel.close()
            _emit_event(session_id, LifecyclePhase.COMPLETED, "Cancel", 0.0, "Pipeline cancelado por el usuario.", PhaseStatus.BLOCKED)
            _pipeline_statuses[session_id] = PipelineRunStatus.CANCELLED
            _record_pipeline_cost(session_id, terminal_status="CANCELLED")
        elif pause_event.is_set():
            _emit_event(session_id, LifecyclePhase.INITIAL, "Pausa", 0.0, "Pipeline pausado cooperativamente. Se mantiene el progreso alcanzado.", PhaseStatus.IN_PROGRESS)
            _pipeline_statuses[session_id] = PipelineRunStatus.PAUSED


def _execute_pipeline_with_cost(session_id, *args):
    from app.cost.recording import recording_context
    with recording_context(session_id, "AUTOPILOT"):
        return _execute_pipeline_steps(session_id, *args)


def run_pipeline(
    session_id: str,
    target_phase: LifecyclePhase = LifecyclePhase.DEVOPS_DEPLOY,
    stop_on_gate: bool = True,
    auto_deploy: bool = False,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    force: bool = False,
    input_interface: Optional[dict] = None,
) -> bool:
    """Initiates an asynchronous background thread for autonomous Auto-Pilot execution."""
    t = _active_threads.get(session_id)
    # `force` is the documented way past this guard, and `resume_pipeline` relies on it: a
    # paused worker can still be unwinding when resume is called, and without the override
    # resume returned False and the session never restarted. The parameter was left in the
    # signature but no longer honoured, which made the failure silent.
    if not force and t and t.is_alive():
        return False

    if api_key or provider or model_name or input_interface is not None:
        cached = _session_credentials.get(session_id, {})
        cached.update({
            "api_key": api_key if api_key is not None else cached.get("api_key"),
            "provider": provider if provider is not None else cached.get("provider"),
            "model_name": model_name if model_name is not None else cached.get("model_name"),
        })
        if input_interface is not None:
            cached["input_interface"] = input_interface
        _session_credentials[session_id] = cached
    else:
        cached = _session_credentials.get(session_id, {})
        api_key = cached.get("api_key")
        provider = cached.get("provider")
        model_name = cached.get("model_name")

    input_interface = input_interface if input_interface is not None else _session_credentials.get(session_id, {}).get("input_interface")

    from app.services.queue_service import queue_manager
    queue_manager.reset_cancellation(session_id)
    _pause_events[session_id] = threading.Event()
    _stop_events[session_id] = threading.Event()
    _pipeline_statuses[session_id] = PipelineRunStatus.RUNNING

    # Update DB lifecycle_mode and status
    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if sess:
            sess.lifecycle_mode = PipelineExecutionMode.AUTO_PILOT.value
            sess.status = SessionStatus.RUNNING
            if not sess.started_at:
                sess.started_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()

    thread = threading.Thread(
        target=_execute_pipeline_with_cost,
        args=(session_id, target_phase, stop_on_gate, auto_deploy, api_key, provider, model_name, input_interface),
        daemon=True,
    )
    _active_threads[session_id] = thread
    thread.start()
    return True


def stream_pipeline_events(session_id: str) -> Generator[str, None, None]:
    """Generator streaming real-time Server-Sent Events (SSE) for the active pipeline."""
    q = _get_queue(session_id)

    # Yield initial connection ping
    yield f"event: connect\ndata: {json.dumps({'sessionId': session_id, 'status': 'CONNECTED'})}\n\n"

    while True:
        try:
            evt: PipelineProgressEvent = q.get(timeout=1.0)
            data = evt.model_dump(by_alias=True, mode="json")
            yield f"event: progress\ndata: {json.dumps(data)}\n\n"

            if evt.phase == LifecyclePhase.COMPLETED or evt.status == PhaseStatus.BLOCKED:
                break
        except queue.Empty:
            status = _pipeline_statuses.get(session_id, PipelineRunStatus.IDLE)
            if status in (PipelineRunStatus.COMPLETED, PipelineRunStatus.PAUSED, PipelineRunStatus.FAILED, PipelineRunStatus.AWAITING_INTERVENTION):
                break
            # Heartbeat comment to keep SSE connection alive
            yield ": heartbeat\n\n"


run_pipeline_in_background = run_pipeline

