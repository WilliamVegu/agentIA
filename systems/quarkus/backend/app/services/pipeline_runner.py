import json
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Optional

from app.config import settings
from app.models.orchestrator import (
    LifecyclePhase,
    PhaseStatus,
    PipelineExecutionMode,
    PipelineProgressEvent,
    PipelineRunStatus,
)
from app.models.session import GenerationSessionDB, SessionLocal, SessionPhase, SessionStatus
from app.models.execution import ExecutionMode
from app.services.lifecycle_service import (
    PHASE_ORDER,
    clear_outdated_phases,
    get_session_lifecycle,
    transition_phase,
)
from app.services.security_service import audit_workspace
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
_worker_operations: Dict[str, str] = {}
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
    operation_id = _worker_operations.get(session_id)
    if operation_id:
        from app.services.operation_repository import get_operation, checkpoint_operation, transition_operation
        operation = get_operation(session_id, operation_id)
        if operation and step in {'Error','Pausa','Cancel'}:
            try:
                phase = LifecyclePhase(operation.get('checkpoint', {}).get('phase'))
            except (ValueError, TypeError):
                pass
        if operation and operation['state'] in {'RUNNING','PAUSE_REQUESTED','CANCEL_REQUESTED'}:
            if status == PhaseStatus.BLOCKED and step != 'Cancel':
                transition_operation(operation_id, operation['version'], 'BLOCKED', checkpoint={'phase':phase.value}, error_code=error or 'GATE_BLOCKED')
            else:
                checkpoint_operation(operation_id, operation['version'], phase.value, {'status':status.value})
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

    from app.services.session_event_service import publish_event
    publish_event(session_id, "pipeline_progress", {
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
    from app.services.operation_repository import get_operation
    from fastapi import HTTPException
    try:
        operation = get_operation(session_id)
    except HTTPException:
        operation = None
    if operation:
        mapping = {'QUEUED':'RUNNING', 'PAUSE_REQUESTED':'RUNNING', 'CANCEL_REQUESTED':'RUNNING',
                   'BLOCKED':'AWAITING_INTERVENTION', 'INTERRUPTED':'PAUSED'}
        return PipelineRunStatus(mapping.get(operation['state'], operation['state']))
    return _pipeline_statuses.get(session_id, PipelineRunStatus.IDLE)


def pause_pipeline(session_id: str, *, operation_id=None, expected_version=None) -> bool:
    from app.services.operation_repository import get_operation, transition_operation
    operation = get_operation(session_id)
    if operation_id is not None and (not operation or operation['operationId'] != operation_id) or expected_version is not None and (not operation or operation['version'] != expected_version):
        from fastapi import HTTPException
        raise HTTPException(409,'Operación o versión obsoleta')
    if not operation or operation['state'] not in {'RUNNING', 'PAUSE_REQUESTED'}:
        return False
    if operation['state'] != 'PAUSE_REQUESTED':
        transition_operation(operation['operationId'], operation['version'], 'PAUSE_REQUESTED')
    _pause_events.setdefault(session_id, threading.Event()).set()
    return True


def cancel_pipeline(session_id: str, *, operation_id=None, expected_version=None) -> bool:
    from app.services.operation_repository import get_operation, transition_operation
    operation = get_operation(session_id)
    if operation_id is not None and (not operation or operation['operationId'] != operation_id) or expected_version is not None and (not operation or operation['version'] != expected_version):
        from fastapi import HTTPException
        raise HTTPException(409,'Operación o versión obsoleta')
    if not operation or operation['state'] not in {'QUEUED', 'RUNNING', 'PAUSE_REQUESTED', 'CANCEL_REQUESTED', 'PAUSED'}:
        return False
    target = 'CANCELLED' if operation['state'] == 'PAUSED' else 'CANCEL_REQUESTED'
    if operation['state'] != target:
        transition_operation(operation['operationId'], operation['version'], target)
    _stop_events.setdefault(session_id, threading.Event()).set()
    from app.services.queue_service import queue_manager
    if hasattr(queue_manager, "cancel_waiting"):
        queue_manager.cancel_waiting(session_id)
    return True


def resume_pipeline(session_id: str, *, operation_id=None, expected_version=None) -> bool:
    from app.services.operation_repository import get_operation
    operation = get_operation(session_id)
    if operation_id is not None and (not operation or operation['operationId'] != operation_id) or expected_version is not None and (not operation or operation['version'] != expected_version):
        from fastapi import HTTPException
        raise HTTPException(409,'Operación o versión obsoleta')
    previous = _active_threads.get(session_id)
    if previous and previous.is_alive():
        previous.join(timeout=1)
        if previous.is_alive():
            return False
    if not operation or operation['state'] not in {'PAUSED', 'INTERRUPTED'}:
        return False
    options = operation['options']
    credentials = _session_credentials.get(session_id, {})
    return run_pipeline(session_id, LifecyclePhase(operation['targetPhase']),
        stop_on_gate=options.get('stopOnGate', True), auto_deploy=options.get('autoDeploy', False),
        api_key=credentials.get('api_key'), provider=credentials.get('provider'),
        model_name=credentials.get('model_name'), **({'input_interface':options.get('inputInterface')} if 'quarkus' == 'springboot' else {}))


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
    from app.services.draft_revision_service import get_revision
    from fastapi import HTTPException
    # A structured revision takes precedence even when a live key is supplied.
    try:
        revision = get_revision(ws_path.name)
    except HTTPException as error:
        if error.status_code != 404:
            raise
        revision = {'draft': None, 'source': None}
    if revision['draft'] is not None:
        return SpecificationDraft.model_validate(revision['draft'])
    if revision.get('source') == 'LEGACY':
        raise ValueError('El borrador legacy necesita revisión; no se reemplazará por datos inventados')

    spec_file = ws_path / "spec.md"
    raw_prompt = spec_name
    if spec_file.exists():
        content = spec_file.read_text(encoding="utf-8")
        if len(content.strip()) > 10:
            raw_prompt = content.strip()

    draft = None
    if api_key and not LLMFactory.is_mock(api_key, provider):
        try:
            draft = transform_requirements(
                RequirementsTransformRequest(rawText=raw_prompt, serviceName=spec_name),
                api_key=api_key,
                chosen_provider=provider,
                chosen_model=model_name,
            )
        except Exception:
            draft = None

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
):
    """Executes each lifecycle phase sequentially in the background."""
    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    pause_event = _pause_events[session_id]
    stop_event = _stop_events[session_id]

    detected_llm = LLMFactory.detect_provider(api_key, provider)
    is_mock = LLMFactory.is_mock(api_key, provider)
    active_model = "offline-mock" if is_mock else LLMFactory.resolve_model_name(detected_llm, model_name)
    llm_label = "Modo Mock (Offline)" if is_mock else f"Motor LLM: {detected_llm.upper()} ({active_model})"

    if target_phase == LifecyclePhase.INITIAL:
        _pipeline_statuses[session_id] = PipelineRunStatus.COMPLETED
        return

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
    database_mode = "POSTGRESQL"
    generation_settings = ws_path / "generation-settings.json"
    if generation_settings.exists():
        database_mode = json.loads(generation_settings.read_text(encoding="utf-8")).get("databaseMode", database_mode)
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if sess and sess.spec_name:
            spec_name = sess.spec_name
            database_mode = sess.database_engine
    finally:
        db.close()

    try:
        _emit_event(session_id, LifecyclePhase.INITIAL, "Inicio", 5.0, f"Iniciando pipeline autónomo Auto-Pilot [{llm_label}]...", PhaseStatus.IN_PROGRESS)

        # Step 1: Requirements Check / Spec
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.REQUIREMENTS, "Especificación", 15.0, f"Sintetizando especificación y entidades de dominio [{llm_label}]...", PhaseStatus.IN_PROGRESS)
        draft = _get_or_create_draft(ws_path, spec_name, api_key=api_key, provider=provider, model_name=model_name)
        from app.services.draft_revision_service import get_revision, save_revision, record_artifact
        from app.models.reliability import ArtifactProvenance
        authority = get_revision(session_id)
        if authority['draft'] is None:
            draft.databaseMode = database_mode
            authority = save_revision(session_id, draft.model_dump(), source='GENERATED', _operation_id=_worker_operations.get(session_id))
        revision_id = authority['revisionId']
        database_mode = draft.databaseMode.upper()
        with SessionLocal() as revision_db:
            if revision_db.query(ArtifactProvenance).filter_by(session_id=session_id, status='OUTDATED').first():
                raise ValueError('Artefactos OUTDATED: regenere explícitamente desde la revisión vigente con backup')

        spec_file = ws_path / "spec.md"
        if not spec_file.exists():
            with open(spec_file, "w", encoding="utf-8") as f:
                f.write(draft.markdownSpec)
        transition_phase(session_id, LifecyclePhase.REQUIREMENTS, force=True)
        if target_phase == LifecyclePhase.REQUIREMENTS:
            _pipeline_statuses[session_id] = PipelineRunStatus.COMPLETED
            return
        time.sleep(0.2)

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
        if target_phase == LifecyclePhase.STORIES:
            _pipeline_statuses[session_id] = PipelineRunStatus.COMPLETED
            return
        time.sleep(0.2)

        # Step 3: Architecture Blueprint
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.ARCHITECTURE, "Diseño Arquitectónico", 45.0, f"Generando blueprint en 4 capas estrictas y catálogo DTO [{llm_label}]...", PhaseStatus.IN_PROGRESS)
        arch_file = ws_path / "architecture.json"
        new_architecture = not arch_file.exists()
        if new_architecture:
            if api_key and not LLMFactory.is_mock(api_key, provider):
                arch_req = ArchitectureDesignRequest(draft=draft, apiKey=api_key, provider=provider)
                arch_data = design_architecture(arch_req, api_key=api_key, provider=provider).model_dump()
            else:
                arch_data = _derive_architecture_from_draft(draft)
            with open(arch_file, "w", encoding="utf-8") as f:
                json.dump(arch_data, f, indent=2)
            arch_md = ws_path / "architecture.md"
            if not arch_md.exists() and "mermaidDiagram" in arch_data:
                arch_md.write_text(f"# Arquitectura: {spec_name}\n\n```mermaid\n{arch_data.get('mermaidDiagram', '')}\n```\n", encoding="utf-8")
        if new_architecture:
            record_artifact(session_id, 'architecture.json', 'ARCHITECTURE', revision_id)
        transition_phase(session_id, LifecyclePhase.ARCHITECTURE, force=True)
        if target_phase == LifecyclePhase.ARCHITECTURE:
            _pipeline_statuses[session_id] = PipelineRunStatus.COMPLETED
            return
        time.sleep(0.2)

        # Step 4: Data Models & SQL
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.DATA_MODEL, "Modelo de Datos", 60.0, f"Generando esquema SQL relacional y entidades de persistencia [{llm_label}]...", PhaseStatus.IN_PROGRESS)
        sql_file = ws_path / "schema.sql"
        new_sql = not sql_file.exists()
        if new_sql:
            if api_key and not LLMFactory.is_mock(api_key, provider):
                sql_resp = model_sql_service.synthesize_domain_models_and_sql(draft, api_key=api_key, provider=provider, model_name=model_name)
                from app.services.model_sql_service import generate_schema_sql
                sql_file.write_text(generate_schema_sql(sql_resp.entities, database_mode), encoding='utf-8')
            else:
                sql_file.write_text(schema_sql_from_draft(draft, database_mode), encoding='utf-8')
        if new_sql:
            record_artifact(session_id, 'schema.sql', 'DATA_MODEL', revision_id)
        transition_phase(session_id, LifecyclePhase.DATA_MODEL, force=True)
        if target_phase == LifecyclePhase.DATA_MODEL:
            _pipeline_statuses[session_id] = PipelineRunStatus.COMPLETED
            return
        time.sleep(0.2)

        # Step 5: Code & Tests
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.CODE_TESTS, "Código & Pruebas", 75.0, "Estructurando proyecto Quarkus 3.x, entidades Panache y suites de prueba...", PhaseStatus.IN_PROGRESS)
        pom_file = ws_path / "pom.xml"
        src_java = ws_path / "src" / "main" / "java"
        has_java = src_java.exists() and any(src_java.glob("**/*.java"))
        if not (pom_file.exists() and has_java):
            blueprint_dict = {
                "serviceName": draft.serviceName,
                "packageName": draft.packageName,
                "basePort": draft.basePort,
                "databaseMode": database_mode,
                "inputInterface": draft.inputInterface,
                "entities": [e.model_dump() for e in draft.entities],
                "userStories": [s.model_dump() for s in draft.userStories],
            }
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
            for relative_path in (agent_state.get('generated_files') or {}):
                record_artifact(session_id, relative_path, 'CODE_TESTS', revision_id)
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
        from app.services.workspace_verification import run_workspace_verification
        from app.services.verification_evidence import verification_metrics
        from app.services.execution_policy import execution_mode
        from app.services.verification_policy import tests_really_passed
        generate_all_devops_assets(str(ws_path),session_id,spec_name,db_engine=database_mode,host_port=draft.basePort)
        verification=run_workspace_verification(str(ws_path),mode=execution_mode(session_id))
        measured=verification_metrics(verification)
        with SessionLocal() as evidence_db:
            evidence_session=evidence_db.get(GenerationSessionDB,session_id)
            previous=json.loads(evidence_session.verification_metrics_json or '{}')
            if measured.get('verificationSkipped') and previous and not tests_really_passed(previous) and not previous.get('verificationSkipped'):
                previous['verificationOutdated']=True
                previous['sourceDeliveryReady']=False
                measured=previous
            evidence_session.verification_metrics_json=json.dumps(measured)
            evidence_db.commit()
        if not verification.result.verification_skipped and not tests_really_passed(measured):
            _emit_event(session_id,LifecyclePhase.CODE_TESTS,'Verificación bloqueada',78.0,
                verification.result.evidence_error or verification.result.fallback_reason or 'Compilación o pruebas no aprobadas',PhaseStatus.BLOCKED)
            _pipeline_statuses[session_id]=PipelineRunStatus.AWAITING_INTERVENTION
            return
        transition_phase(session_id, LifecyclePhase.CODE_TESTS, force=True)
        if target_phase == LifecyclePhase.CODE_TESTS:
            _pipeline_statuses[session_id] = PipelineRunStatus.COMPLETED
            return
        time.sleep(0.2)

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
            with SessionLocal() as gate_db:
                row=gate_db.get(GenerationSessionDB,session_id)
                if row:
                    row.status=SessionStatus.BLOCKED
                    row.error_message=audit.qualityGate.summaryMessage
                    gate_db.commit()
            return

        transition_phase(session_id, LifecyclePhase.SECURITY_AUDIT, force=True)
        if target_phase == LifecyclePhase.SECURITY_AUDIT:
            _pipeline_statuses[session_id] = PipelineRunStatus.COMPLETED
            return
        time.sleep(0.3)

        # Step 7: DevOps & Deploy
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.DEVOPS_DEPLOY, "DevOps & Manifiestos", 95.0, "Generando Dockerfile, Compose, CI/CD y manifiestos Kubernetes...", PhaseStatus.IN_PROGRESS)
        generate_all_devops_assets(str(ws_path), session_id, spec_name, db_engine=database_mode, host_port=draft.basePort)

        if auto_deploy and execution_mode(session_id) == ExecutionMode.DOCKER:
            _emit_event(session_id, LifecyclePhase.DEVOPS_DEPLOY, "Despliegue Local", 98.0, "Orquestando contenedores en Docker local...", PhaseStatus.IN_PROGRESS)
            deploy_local(session_id, str(ws_path), host_port=draft.basePort, _borrowed=True)
            from app.services.docker_service import wait_deployment
            wait_deployment(session_id, stop_event=stop_event, pause_event=pause_event)
            if stop_event.is_set() or pause_event.is_set(): return

        transition_phase(session_id, LifecyclePhase.DEVOPS_DEPLOY, force=True)
        clear_outdated_phases(session_id)

        _emit_event(session_id, LifecyclePhase.COMPLETED, "Finalizado", 100.0, "🎉 ¡Pipeline completado con éxito! Todos los artefactos están listos.", PhaseStatus.COMPLETED)
        _pipeline_statuses[session_id] = PipelineRunStatus.COMPLETED

        try:
            from app.services.session_event_service import publish_event
            publish_event(session_id, "session_completed", {
                "sessionId": session_id,
                "status": "COMPLETED",
                "message": "Pipeline completado con éxito.",
                "percent": 100.0,
                "artifactCount": sum(1 for path in ws_path.rglob('*') if path.is_file() and '.git' not in path.parts and 'target' not in path.parts),
                "downloadUrl": f"/api/v1/sessions/{session_id}/export"
            })
        except Exception:
            pass

        db_comp = SessionLocal()
        try:
            s = db_comp.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
            if s:
                s.status = SessionStatus.COMPLETED
                # This path generates test sources, but does not run Maven.
                # Only the sandbox verification path can claim VERIFIED.
                s.phase = SessionPhase.VERIFIED if tests_really_passed(measured) else SessionPhase.TEST_SYNTHESIS
                s.current_lifecycle_phase = LifecyclePhase.COMPLETED.value
                s.completed_at = datetime.now(timezone.utc)
                db_comp.commit()
        finally:
            db_comp.close()

    except Exception as e:
        _emit_event(session_id, LifecyclePhase.INITIAL, "Error", 0.0, f"Error en ejecución de pipeline: {str(e)}", PhaseStatus.BLOCKED, error=str(e))
        _pipeline_statuses[session_id] = PipelineRunStatus.FAILED

        try:
            from app.services.session_event_service import publish_event
            publish_event(session_id, "session_blocked", {
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
                s.phase = SessionPhase.FAILED
                s.error_message = str(e)
                db_err.commit()
        finally:
            db_err.close()
    finally:
        if stop_event.is_set():
            _emit_event(session_id, LifecyclePhase.COMPLETED, "Cancel", 0.0, "Pipeline cancelado por el usuario.", PhaseStatus.BLOCKED)
            _pipeline_statuses[session_id] = PipelineRunStatus.CANCELLED
        elif pause_event.is_set():
            _emit_event(session_id, LifecyclePhase.INITIAL, "Pausa", 0.0, "Pipeline pausado cooperativamente. Se mantiene el progreso alcanzado.", PhaseStatus.IN_PROGRESS)
            _pipeline_statuses[session_id] = PipelineRunStatus.PAUSED


def _execute_pipeline_with_cost(session_id, *args):
    from fastapi import HTTPException
    from app.services.operation_repository import get_operation, transition_operation
    from app.services.session_operation_lock import SessionOperationLock
    from app.cost.recording import recording_context

    def current(operation_id=None):
        try:
            return get_operation(session_id,operation_id)
        except HTTPException as error:
            if error.status_code!=404: raise
            return None

    operation=current()
    if operation is None: return
    operation_id=operation['operationId']
    lock=SessionOperationLock(session_id)
    if not lock.acquire(False):
        transition_operation(operation_id,operation['version'],'BLOCKED',error_code='WRITER_BUSY')
        return
    _worker_operations[session_id]=operation_id
    try:
        operation=current(operation_id)
        if operation is None: return
        transition_operation(operation_id,operation['version'],'RUNNING')
        with recording_context(session_id,'AUTOPILOT'):
            _execute_pipeline_steps(session_id,*args)
    except Exception as error:
        operation=current(operation_id)
        if operation and operation['state'] in {'QUEUED','RUNNING'}:
            transition_operation(operation_id,operation['version'],'BLOCKED',error_code=type(error).__name__)
        _pipeline_statuses[session_id]=PipelineRunStatus.FAILED
    finally:
        try:
            from app.services.operation_repository import finish_operation
            finish_operation(session_id,operation_id,
                'COMPLETED' if _pipeline_statuses.get(session_id)==PipelineRunStatus.COMPLETED else 'BLOCKED')
        finally:
            if _worker_operations.get(session_id)==operation_id:
                _worker_operations.pop(session_id,None)
            lock.release()


def run_pipeline(
    session_id: str,
    target_phase: LifecyclePhase = LifecyclePhase.DEVOPS_DEPLOY,
    stop_on_gate: bool = True,
    auto_deploy: bool = False,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    force: bool = False,
) -> bool:
    """Initiates an asynchronous background thread for autonomous Auto-Pilot execution."""
    t = _active_threads.get(session_id)
    if not force and t and t.is_alive() and _pipeline_statuses.get(session_id) == PipelineRunStatus.RUNNING:
        return False

    if api_key or provider or model_name:
        _session_credentials[session_id] = {"api_key": api_key, "provider": provider, "model_name": model_name}
    else:
        cached = _session_credentials.get(session_id, {})
        api_key = cached.get("api_key")
        provider = cached.get("provider")
        model_name = cached.get("model_name")

    from app.services.draft_revision_service import get_revision
    from app.services.operation_repository import begin_operation
    from app.services.workspace_guard import get_validated_workspace_path
    from fastapi import HTTPException
    get_validated_workspace_path(session_id, require_exists=True)
    revision = get_revision(session_id)
    if revision.get('draft') is not None and revision['source'] in {'MANUAL','LEGACY'} and revision['approvalStatus'] != 'APPROVED':
        raise HTTPException(409, 'Apruebe explícitamente la revisión antes de ejecutar')
    if not (api_key or '').strip() and (provider or '').strip().lower() not in {'mock','mock-mode','offline','offline-mock','testing'}:
        raise HTTPException(422, 'Configure un proveedor IA con credencial o elija explícitamente el modo offline')
    begin_operation(session_id, target_phase, {'stopOnGate':stop_on_gate, 'autoDeploy':auto_deploy, 'inputInterface':None})

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
        args=(session_id, target_phase, stop_on_gate, auto_deploy, api_key, provider, model_name),
        daemon=True,
    )
    _active_threads[session_id] = thread
    thread.start()
    return True


def stream_pipeline_events(session_id: str, after=0) -> Generator[str, None, None]:
    from app.services.session_event_service import stream_events
    yield from stream_events(session_id, after)


run_pipeline_in_background = run_pipeline

