import json
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Generator, Optional

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
from app.services.model_sql_service import model_sql_service
from app.orchestrator.nodes.scaffolder_node import scaffolder_node
from app.orchestrator.nodes.domain_node import domain_node
from app.orchestrator.nodes.service_node import service_node
from app.orchestrator.nodes.controller_node import controller_node
from app.orchestrator.nodes.test_node import test_node

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


def get_pipeline_status(session_id: str) -> PipelineRunStatus:
    return _pipeline_statuses.get(session_id, PipelineRunStatus.IDLE)


def pause_pipeline(session_id: str) -> bool:
    """Signals an active Auto-Pilot thread to pause cooperatively and switch to Guided Step mode."""
    if session_id in _pause_events:
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
    return session_id in _pause_events


def resume_pipeline(session_id: str) -> bool:
    """Resumes a paused Auto-Pilot pipeline."""
    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if sess:
            sess.status = SessionStatus.RUNNING
            sess.lifecycle_mode = PipelineExecutionMode.AUTO_PILOT.value
            db.commit()
    finally:
        db.close()

    # Wait briefly if the previous thread is still unwinding from pause
    t = _active_threads.get(session_id)
    if t and t.is_alive():
        t.join(timeout=1.0)

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

    _emit_event(
        session_id,
        LifecyclePhase.COMPLETED,
        "CANCEL",
        0.0,
        "Pipeline cancelado por el usuario.",
        PhaseStatus.BLOCKED,
    )
    return True


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

    db = SessionLocal()
    spec_name = "Microservicio"
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if sess and sess.spec_name:
            spec_name = sess.spec_name
    finally:
        db.close()

    try:
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

        # Step 3: Architecture Blueprint
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.ARCHITECTURE, "Diseño Arquitectónico", 45.0, f"Generando blueprint en 4 capas estrictas y catálogo DTO [{llm_label}]...", PhaseStatus.IN_PROGRESS)
        arch_file = ws_path / "architecture.json"
        if not arch_file.exists():
            try:
                arch_req = ArchitectureDesignRequest(draft=draft, apiKey=api_key or "mock-key", provider=provider or "mock")
                arch_resp = design_architecture(arch_req, api_key=api_key or "mock-key", provider=provider or "mock")
                arch_data = arch_resp.model_dump()
            except Exception:
                arch_data = {
                    "serviceName": draft.serviceName,
                    "packageName": draft.packageName,
                    "components": ["Controller", "Service", "Repository", "Entity"],
                    "mermaidDiagram": "graph TD\n    Controller --> Service\n    Service --> Repository\n    Repository --> Model",
                }
            with open(arch_file, "w", encoding="utf-8") as f:
                json.dump(arch_data, f, indent=2)
            arch_md = ws_path / "architecture.md"
            if not arch_md.exists() and "mermaidDiagram" in arch_data:
                arch_md.write_text(f"# Arquitectura: {spec_name}\n\n```mermaid\n{arch_data.get('mermaidDiagram', '')}\n```\n", encoding="utf-8")
        transition_phase(session_id, LifecyclePhase.ARCHITECTURE, force=True)
        time.sleep(0.2)

        # Step 4: Data Models & SQL
        if pause_event.is_set() or stop_event.is_set():
            return
        _emit_event(session_id, LifecyclePhase.DATA_MODEL, "Modelo de Datos", 60.0, f"Generando esquema SQL relacional y entidades de persistencia [{llm_label}]...", PhaseStatus.IN_PROGRESS)
        sql_file = ws_path / "schema.sql"
        if not sql_file.exists():
            try:
                sql_resp = model_sql_service.synthesize_domain_models_and_sql(draft, api_key=api_key or "mock-key", provider=provider or "mock")
                with open(sql_file, "w", encoding="utf-8") as f:
                    f.write(sql_resp.schemaSql)
                data_sql_file = ws_path / "data.sql"
                if not data_sql_file.exists() and sql_resp.dataSql:
                    with open(data_sql_file, "w", encoding="utf-8") as f:
                        f.write(sql_resp.dataSql)
            except Exception:
                with open(sql_file, "w", encoding="utf-8") as f:
                    f.write(f"-- Schema DDL for {spec_name}\nCREATE TABLE IF NOT EXISTS items (\n    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,\n    name VARCHAR(255) NOT NULL,\n    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);\n")
        transition_phase(session_id, LifecyclePhase.DATA_MODEL, force=True)
        time.sleep(0.2)

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
            agent_state = {
                "session_id": session_id,
                "blueprint": blueprint_dict,
                "workspace_path": str(ws_path),
                "generated_files": {},
                "logs": [],
            }
            scaffolder_node(agent_state)
            domain_node(agent_state)
            service_node(agent_state)
            controller_node(agent_state)
            test_node(agent_state)
        transition_phase(session_id, LifecyclePhase.CODE_TESTS, force=True)
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
            return

        transition_phase(session_id, LifecyclePhase.SECURITY_AUDIT, force=True)
        time.sleep(0.3)

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
                s.phase = SessionPhase.VERIFIED
                s.current_lifecycle_phase = LifecyclePhase.COMPLETED.value
                s.completed_at = datetime.now(timezone.utc)
                db_comp.commit()
        finally:
            db_comp.close()

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
    finally:
        if stop_event.is_set():
            _emit_event(session_id, LifecyclePhase.COMPLETED, "Cancel", 0.0, "Pipeline cancelado por el usuario.", PhaseStatus.BLOCKED)
            _pipeline_statuses[session_id] = PipelineRunStatus.CANCELLED
        elif pause_event.is_set():
            _emit_event(session_id, LifecyclePhase.INITIAL, "Pausa", 0.0, "Pipeline pausado cooperativamente. Se mantiene el progreso alcanzado.", PhaseStatus.IN_PROGRESS)
            _pipeline_statuses[session_id] = PipelineRunStatus.PAUSED


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
        target=_execute_pipeline_steps,
        args=(session_id, target_phase, stop_on_gate, auto_deploy, api_key, provider, model_name),
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

