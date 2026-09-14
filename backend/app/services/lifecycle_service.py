import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.config import settings
from app.models.orchestrator import (
    LifecyclePhase,
    LifecycleState,
    PhaseState,
    PhaseStatus,
    PipelineExecutionMode,
    ProjectOverviewSummary,
)
from app.models.session import GenerationSessionDB, SessionLocal, SessionStatus
from app.services.security_service import audit_workspace
from app.services.docker_service import get_deployment_status

# Sequential order of all lifecycle phases
PHASE_ORDER = [
    LifecyclePhase.REQUIREMENTS,
    LifecyclePhase.STORIES,
    LifecyclePhase.ARCHITECTURE,
    LifecyclePhase.DATA_MODEL,
    LifecyclePhase.CODE_TESTS,
    LifecyclePhase.SECURITY_AUDIT,
    LifecyclePhase.DEVOPS_DEPLOY,
]

PHASE_METADATA = {
    LifecyclePhase.REQUIREMENTS: {
        "title": "1. Especificación & Requisitos",
        "description": "Ingesta del requerimiento y síntesis de especificación formal",
        "tabIndex": 1,
    },
    LifecyclePhase.STORIES: {
        "title": "2. Historias & Criterios BDD",
        "description": "Generación de historias de usuario y criterios Given/When/Then",
        "tabIndex": 2,
    },
    LifecyclePhase.ARCHITECTURE: {
        "title": "3. Diseño & Componentes",
        "description": "Blueprint arquitectónico, DTOs inmutables e interfaces de servicio",
        "tabIndex": 3,
    },
    LifecyclePhase.DATA_MODEL: {
        "title": "4. Modelo & Esquema SQL",
        "description": "Entidades JPA, scripts DDL/DML y selección de motor relacional",
        "tabIndex": 4,
    },
    LifecyclePhase.CODE_TESTS: {
        "title": "5. Código, Tests & Auto-Reparación",
        "description": "Síntesis del microservice Spring Boot 3, suites de tests y sandbox Surefire",
        "tabIndex": 5,
    },
    LifecyclePhase.SECURITY_AUDIT: {
        "title": "6. Seguridad & Quality Gate",
        "description": "Auditoría estática SAST, escaneo de secretos y validación constitucional",
        "tabIndex": 6,
    },
    LifecyclePhase.DEVOPS_DEPLOY: {
        "title": "7. DevOps & Despliegue",
        "description": "Dockerfile hermético, Compose, CI/CD, despliegue local y Kubernetes",
        "tabIndex": 7,
    },
}


def _get_workspace_path(session_id: str) -> Path:
    return Path(settings.WORKSPACE_DIR) / session_id


def get_session_lifecycle(session_id: str) -> LifecycleState:
    """Computes the full lifecycle state machine status by inspecting database records and workspace files."""
    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if not sess:
            # Return fresh initial state
            return LifecycleState(
                sessionId=session_id,
                currentPhase=LifecyclePhase.INITIAL,
                completionPercentage=0.0,
                phases=[],
                canAdvance=True,
                nextRecommendedAction="Iniciar nueva especificación en Pestaña 1",
                nextTargetPhase=LifecyclePhase.REQUIREMENTS,
            )

        ws_path = _get_workspace_path(session_id)
        outdated_phases = set()
        if sess.phase_progress_json:
            try:
                prog = json.loads(sess.phase_progress_json)
                outdated_phases = set(prog.get("outdated_phases", []))
            except Exception:
                outdated_phases = set()

        phase_states: List[PhaseState] = []
        completed_count = 0
        is_blocked = False
        blocked_reason = None

        # Determine phase completion based on workspace artifacts and DB status
        for idx, phase in enumerate(PHASE_ORDER):
            meta = PHASE_METADATA[phase]
            status = PhaseStatus.NOT_STARTED
            summary: Dict[str, Any] = {}
            can_enter = True
            reason = None

            # Phase 1: Requirements
            if phase == LifecyclePhase.REQUIREMENTS:
                if ws_path.exists() and (ws_path / "spec.md").exists():
                    status = PhaseStatus.COMPLETED
                    summary["specFile"] = "spec.md"
                elif sess.spec_id:
                    status = PhaseStatus.IN_PROGRESS
                else:
                    status = PhaseStatus.NOT_STARTED

            # Phase 2: Stories
            elif phase == LifecyclePhase.STORIES:
                stories_file = ws_path / "user_stories.json"
                if stories_file.exists():
                    status = PhaseStatus.COMPLETED
                    try:
                        with open(stories_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            summary["storiesCount"] = len(data) if isinstance(data, list) else len(data.get("stories", []))
                    except Exception:
                        summary["storiesCount"] = 1
                elif phase_states[0].status == PhaseStatus.COMPLETED:
                    status = PhaseStatus.NOT_STARTED
                else:
                    status = PhaseStatus.NOT_STARTED
                    can_enter = False
                    reason = "Requiere completar Especificación y Requisitos (Fase 1)"

            # Phase 3: Architecture
            elif phase == LifecyclePhase.ARCHITECTURE:
                arch_file = ws_path / "architecture.json"
                if arch_file.exists():
                    status = PhaseStatus.COMPLETED
                    summary["blueprint"] = "architecture.json"
                elif phase_states[1].status == PhaseStatus.COMPLETED:
                    status = PhaseStatus.NOT_STARTED
                else:
                    status = PhaseStatus.NOT_STARTED
                    can_enter = False
                    reason = "Requiere generar Historias de Usuario (Fase 2)"

            # Phase 4: Data Model
            elif phase == LifecyclePhase.DATA_MODEL:
                sql_file = ws_path / "schema.sql"
                if sql_file.exists():
                    status = PhaseStatus.COMPLETED
                    summary["schemaFile"] = "schema.sql"
                elif phase_states[2].status == PhaseStatus.COMPLETED:
                    status = PhaseStatus.NOT_STARTED
                else:
                    status = PhaseStatus.NOT_STARTED
                    can_enter = False
                    reason = "Requiere aprobar Diseño Arquitectónico (Fase 3)"

            # Phase 5: Code & Tests
            elif phase == LifecyclePhase.CODE_TESTS:
                pom_file = ws_path / "pom.xml"
                src_dir = ws_path / "src"
                if pom_file.exists() and src_dir.exists():
                    if sess.repair_attempts >= 3 and sess.status == SessionStatus.BLOCKED:
                        status = PhaseStatus.BLOCKED
                        is_blocked = True
                        blocked_reason = "Límite de 3 auto-reparaciones alcanzado (Principio V)"
                    else:
                        status = PhaseStatus.COMPLETED
                        summary["pom"] = "pom.xml"
                elif phase_states[3].status == PhaseStatus.COMPLETED:
                    status = PhaseStatus.NOT_STARTED
                else:
                    status = PhaseStatus.NOT_STARTED
                    can_enter = False
                    reason = "Requiere definir Modelo de Datos y SQL (Fase 4)"

            # Phase 6: Security Audit
            elif phase == LifecyclePhase.SECURITY_AUDIT:
                if phase_states[4].status == PhaseStatus.COMPLETED:
                    # Run or inspect security audit
                    try:
                        audit = audit_workspace(str(ws_path), session_id, sess.spec_name or "microservice")
                        qg_status = audit.qualityGate.status.value if hasattr(audit.qualityGate.status, "value") else str(audit.qualityGate.status)
                        summary["qualityGate"] = qg_status
                        summary["findingsCount"] = len(audit.vulnerabilities) + len(audit.violations)
                        if qg_status == "BLOCKED":
                            status = PhaseStatus.BLOCKED
                            is_blocked = True
                            blocked_reason = f"Quality Gate BLOQUEADO: {audit.qualityGate.summaryMessage}"
                        else:
                            status = PhaseStatus.COMPLETED
                    except Exception:
                        status = PhaseStatus.NOT_STARTED
                else:
                    status = PhaseStatus.NOT_STARTED
                    can_enter = False
                    reason = "Requiere compilar y verificar Código y Tests (Fase 5)"

            # Phase 7: DevOps & Deploy
            elif phase == LifecyclePhase.DEVOPS_DEPLOY:
                compose_file = ws_path / "docker-compose.yml"
                if compose_file.exists():
                    deploy_info = get_deployment_status(session_id)
                    summary["deploymentStatus"] = deploy_info.status
                    status = PhaseStatus.COMPLETED
                elif phase_states[5].status == PhaseStatus.COMPLETED:
                    status = PhaseStatus.NOT_STARTED
                else:
                    status = PhaseStatus.NOT_STARTED
                    can_enter = False
                    reason = "Requiere superar Auditoría de Seguridad con Quality Gate APROBADO (Fase 6)"

            # Check if this phase was marked outdated
            if phase.value in outdated_phases and status == PhaseStatus.COMPLETED:
                status = PhaseStatus.OUTDATED

            if status == PhaseStatus.COMPLETED:
                completed_count += 1

            phase_states.append(
                PhaseState(
                    phase=phase,
                    status=status,
                    title=meta["title"],
                    description=meta["description"],
                    tabIndex=meta["tabIndex"],
                    canEnter=can_enter,
                    blockingReason=reason,
                    artifactSummary=summary,
                )
            )

        # Calculate completion percentage
        completion_pct = round((completed_count / len(PHASE_ORDER)) * 100.0, 1)

        # Determine next recommended action
        next_action = "Revisar y continuar"
        next_phase = None
        for p in phase_states:
            if p.status in (PhaseStatus.NOT_STARTED, PhaseStatus.IN_PROGRESS, PhaseStatus.OUTDATED):
                next_action = f"Ejecutar: {p.title}"
                next_phase = p.phase
                break
        if completed_count == len(PHASE_ORDER):
            next_action = "¡Microservicio completamente sintetizado y desplegado!"
            next_phase = LifecyclePhase.COMPLETED

        current_phase_str = sess.current_lifecycle_phase or LifecyclePhase.INITIAL.value
        try:
            current_phase_enum = LifecyclePhase(current_phase_str)
        except ValueError:
            current_phase_enum = LifecyclePhase.INITIAL

        mode_str = sess.lifecycle_mode or PipelineExecutionMode.GUIDED_STEP.value
        try:
            active_mode_enum = PipelineExecutionMode(mode_str)
        except ValueError:
            active_mode_enum = PipelineExecutionMode.GUIDED_STEP

        from app.services.pipeline_runner import get_pipeline_status
        pipe_status = get_pipeline_status(session_id)

        return LifecycleState(
            sessionId=session_id,
            currentPhase=current_phase_enum,
            completionPercentage=completion_pct,
            phases=phase_states,
            nextRecommendedAction=next_action,
            nextTargetPhase=next_phase,
            canAdvance=not is_blocked,
            activeMode=active_mode_enum,
            isOutdated=len(outdated_phases) > 0,
            pipelineStatus=pipe_status,
        )
    finally:
        db.close()


def transition_phase(session_id: str, target_phase: LifecyclePhase, force: bool = False) -> LifecycleState:
    """Validates prerequisite invariant guards and advances session to target phase."""
    lifecycle = get_session_lifecycle(session_id)

    if not force:
        # Find the target phase in states
        target_state = next((p for p in lifecycle.phases if p.phase == target_phase), None)
        if target_state and not target_state.can_enter:
            raise ValueError(target_state.blocking_reason or f"No se cumplen los prerrequisitos para ingresar a {target_phase.value}")

    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if sess:
            sess.current_lifecycle_phase = target_phase.value
            db.commit()
    finally:
        db.close()

    return get_session_lifecycle(session_id)


def mark_downstream_outdated(session_id: str, modified_phase: LifecyclePhase):
    """Marks all downstream phases after modified_phase as OUTDATED in session progress tracking."""
    if modified_phase not in PHASE_ORDER:
        return

    mod_index = PHASE_ORDER.index(modified_phase)
    outdated = [p.value for p in PHASE_ORDER[mod_index + 1:]]

    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if sess:
            prog = {}
            if sess.phase_progress_json:
                try:
                    prog = json.loads(sess.phase_progress_json)
                except Exception:
                    prog = {}
            prog["outdated_phases"] = outdated
            prog["last_modified_phase"] = modified_phase.value
            sess.phase_progress_json = json.dumps(prog)
            db.commit()
    finally:
        db.close()


def clear_outdated_phases(session_id: str):
    """Clears outdated phase flags after re-synchronization."""
    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if sess and sess.phase_progress_json:
            try:
                prog = json.loads(sess.phase_progress_json)
                prog["outdated_phases"] = []
                sess.phase_progress_json = json.dumps(prog)
                db.commit()
            except Exception:
                pass
    finally:
        db.close()


def get_project_overview(session_id: str) -> ProjectOverviewSummary:
    """Compiles aggregate project metrics and milestone status for the Project Overview Home View."""
    lifecycle = get_session_lifecycle(session_id)
    ws_path = _get_workspace_path(session_id)

    db = SessionLocal()
    spec_name = "Microservicio"
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if sess and sess.spec_name:
            spec_name = sess.spec_name
    finally:
        db.close()

    # Calculate user stories count
    stories_count = 0
    stories_file = ws_path / "user_stories.json"
    if stories_file.exists():
        try:
            with open(stories_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                stories_count = len(data) if isinstance(data, list) else len(data.get("stories", []))
        except Exception:
            stories_count = 0

    # Calculate entities count & database
    entities_count = 0
    db_engine = "POSTGRESQL"
    sql_file = ws_path / "schema.sql"
    if sql_file.exists():
        try:
            with open(sql_file, "r", encoding="utf-8") as f:
                content = f.read()
                entities_count = content.count("CREATE TABLE")
                if "SERIAL" in content or "VARCHAR" in content:
                    db_engine = "POSTGRESQL"
                elif "AUTO_INCREMENT" in content:
                    db_engine = "MYSQL"
        except Exception:
            pass

    # Security verdict
    sec_verdict = "PENDING"
    try:
        audit = audit_workspace(str(ws_path), session_id, spec_name)
        sec_verdict = audit.qualityGate.status
    except Exception:
        pass

    # Deployment
    deploy_info = get_deployment_status(session_id)
    test_url = f"http://localhost:{deploy_info.hostPort}/actuator/health" if deploy_info.hostPort else None

    return ProjectOverviewSummary(
        sessionId=session_id,
        specName=spec_name,
        lifecycle=lifecycle,
        framework="Java 21 / Spring Boot 3",
        databaseEngine=db_engine,
        userStoriesCount=stories_count,
        entitiesCount=entities_count,
        testsPassed=(lifecycle.phases[4].status == PhaseStatus.COMPLETED) if len(lifecycle.phases) > 4 else False,
        securityAuditVerdict=sec_verdict,
        deploymentStatus=deploy_info.status.value if hasattr(deploy_info.status, "value") else str(deploy_info.status),
        deploymentUrl=test_url,
        pipelineStatus=lifecycle.pipeline_status,
    )


def mark_downstream_outdated(session_id: str, modified_phase: Union[str, LifecyclePhase]) -> List[str]:
    """Marks all downstream phases following modified_phase as OUTDATED in session progress."""
    phase_val = modified_phase.value if isinstance(modified_phase, LifecyclePhase) else str(modified_phase)

    # Find index of modified_phase in PHASE_ORDER
    mod_idx = None
    for idx, p in enumerate(PHASE_ORDER):
        if p.value == phase_val:
            mod_idx = idx
            break

    if mod_idx is None:
        return []

    downstream = [p.value for p in PHASE_ORDER[mod_idx + 1:]]
    if not downstream:
        return []

    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if not sess:
            return []

        prog = {}
        if sess.phase_progress_json:
            try:
                prog = json.loads(sess.phase_progress_json)
            except Exception:
                prog = {}

        existing_outdated = set(prog.get("outdated_phases", []))
        existing_outdated.update(downstream)
        prog["outdated_phases"] = list(existing_outdated)
        sess.phase_progress_json = json.dumps(prog)
        db.commit()
        return list(existing_outdated)
    finally:
        db.close()


def clear_outdated_phases(session_id: str) -> None:
    """Clears all outdated flags for a session when re-sync or regeneration completes."""
    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if not sess:
            return

        prog = {}
        if sess.phase_progress_json:
            try:
                prog = json.loads(sess.phase_progress_json)
            except Exception:
                prog = {}

        prog["outdated_phases"] = []
        sess.phase_progress_json = json.dumps(prog)
        db.commit()
    finally:
        db.close()


