from app.services.verification_policy import require_verified_session, session_is_verified, tests_really_passed, session_allows_source_delivery, verification_outcome
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
    PipelineRunStatus,
    ProjectOverviewSummary,
)
from app.models.session import GenerationSessionDB, SessionLocal, SessionStatus, SessionPhase
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
                        summary["storiesCount"] = 0
                        status = PhaseStatus.BLOCKED
                        is_blocked = True
                        reason = "No se pudo leer el archivo de historias; revise su contenido"
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
                build_file = pom_file.exists() or (ws_path / "build.gradle").exists() or (ws_path / "build.gradle.kts").exists()
                src_dir = ws_path / "src"
                if build_file and src_dir.exists():
                    if sess.repair_attempts >= 3 and sess.status == SessionStatus.BLOCKED:
                        status = PhaseStatus.BLOCKED
                        is_blocked = True
                        reason = "Límite de 3 auto-reparaciones alcanzado (Principio V)"
                    elif sess.status == SessionStatus.BLOCKED or sess.phase == SessionPhase.FAILED:
                        status = PhaseStatus.BLOCKED
                        is_blocked = True
                        reason = sess.error_message or "Verificación o compilación de pruebas falló"
                    elif sess.status == SessionStatus.CANCELLED:
                        status = PhaseStatus.BLOCKED
                        is_blocked = True
                        reason = "Sesión cancelada"
                    elif session_is_verified(sess):
                        status = PhaseStatus.COMPLETED
                        summary["build"] = "pom.xml" if pom_file.exists() else "Gradle"
                    elif session_allows_source_delivery(sess):
                        status = PhaseStatus.COMPLETED
                        summary["verification"] = "No ejecutada: entrega de fuentes elegida sin Docker"
                        reason = "Código generado; compilación y pruebas no ejecutadas."
                    else:
                        status = PhaseStatus.IN_PROGRESS
                        reason = "Código generado; pruebas reales pendientes"
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
                        from app.services.verification_evidence import current_audit
                        audit=current_audit(session_id,ws_path)
                        if audit is None:
                            audit=audit_workspace(str(ws_path),session_id,sess.spec_name or "microservice")
                        qg_status=getattr(audit.qualityGate.status,'value',audit.qualityGate.status)
                        summary['qualityGate']=qg_status
                        summary['findingsCount']=len(audit.vulnerabilities)+len(audit.violations)
                        if not audit.qualityGate.canExport or qg_status!='PASS':
                            status=PhaseStatus.BLOCKED
                            is_blocked=True
                            reason=f"Quality Gate BLOQUEADO: {audit.qualityGate.summaryMessage}"
                        else:
                            status=PhaseStatus.COMPLETED
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
                    if sess.execution_mode == "SOURCE_ONLY" and phase_states[5].status == PhaseStatus.COMPLETED:
                        status = PhaseStatus.COMPLETED
                        summary["deployment"] = "No ejecutado: entrega de fuentes elegida sin Docker"
                        reason = "Manifiestos generados; despliegue no ejecutado."
                    else:
                        status = PhaseStatus.COMPLETED if str(getattr(deploy_info.status, "value", deploy_info.status)) == "HEALTHY" else PhaseStatus.IN_PROGRESS
                    if status != PhaseStatus.COMPLETED:
                        reason = "Manifiestos generados; despliegue saludable pendiente"
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
            next_action = "Flujo completado; consulte por separado la verificación y el despliegue"
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
        if pipe_status == PipelineRunStatus.IDLE and sess:
            if sess.status == SessionStatus.RUNNING:
                pipe_status = PipelineRunStatus.RUNNING
            elif sess.status == SessionStatus.PAUSED:
                pipe_status = PipelineRunStatus.PAUSED
            elif sess.status == SessionStatus.CANCELLED:
                pipe_status = PipelineRunStatus.CANCELLED
            elif sess.status == SessionStatus.COMPLETED:
                pipe_status = PipelineRunStatus.COMPLETED

        if sess.status == SessionStatus.CANCELLED:
            is_blocked = True
            next_action = "Pipeline cancelado por el usuario"
        elif sess.status == SessionStatus.PAUSED:
            next_action = "Pipeline pausado. Puede reanudar o continuar en modo asistido"

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
    db_engine = sess.database_engine if sess else "POSTGRESQL"
    sql_file = ws_path / "schema.sql"
    if sql_file.exists():
        try:
            with open(sql_file, "r", encoding="utf-8") as f:
                content = f.read()
                entities_count = content.count("CREATE TABLE")
        except Exception:
            pass

    from app.services.draft_revision_service import get_revision
    revision = get_revision(session_id)
    if revision['draft'] is not None:
        stories_count = len(revision['draft']['userStories'])
        entities_count = len(revision['draft']['entities'])
        db_engine = revision['draft']['databaseMode'].upper()

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

    real_tests_passed = False
    if sess.verification_metrics_json:
        try:
            vm = json.loads(sess.verification_metrics_json)
            if (
                vm.get("totalTests", 0) > 0
                and vm.get("passedTests", 0) == vm.get("totalTests")
                and vm.get("allPassed", False)
                and not vm.get("fallback_used", False)
            ):
                real_tests_passed = True
        except Exception:
            pass
    real_tests_passed = session_is_verified(sess)
    try:
        verification_metrics = json.loads(sess.verification_metrics_json or "{}")
        tests_executed = (verification_metrics.get("totalTests", 0) > 0
                          and not verification_metrics.get("fallback_used", False))
    except (ValueError, TypeError):
        tests_executed = False

    return ProjectOverviewSummary(
        sessionId=session_id,
        executionMode=sess.execution_mode if sess else "SOURCE_ONLY",
        verificationOutcome=verification_outcome(sess).value if sess else "NOT_RUN",
        specName=spec_name,
        lifecycle=lifecycle,
        framework="Java 21 / Spring Boot 3",
        databaseEngine=db_engine,
        userStoriesCount=stories_count,
        entitiesCount=entities_count,
        testsPassed=real_tests_passed,
        testsExecuted=tests_executed,
        securityAuditVerdict=sec_verdict,
        deploymentStatus=deploy_info.status.value if hasattr(deploy_info.status, "value") else str(deploy_info.status),
        deploymentUrl=deploy_info.testUrl,
        pipelineStatus=lifecycle.pipeline_status,
    )


#: The artifacts whose presence means a phase has actually been built. Deliberately
#: the same conditions `get_session_progress` uses to derive COMPLETED from the
#: workspace, so the two cannot disagree about whether a phase exists.
_PHASE_COMPLETION_ARTIFACTS = {
    LifecyclePhase.REQUIREMENTS: ("spec.md",),
    LifecyclePhase.STORIES: ("user_stories.json",),
    LifecyclePhase.ARCHITECTURE: ("architecture.json",),
    LifecyclePhase.DATA_MODEL: ("schema.sql",),
    LifecyclePhase.CODE_TESTS: ("pom.xml", "src"),
    LifecyclePhase.SECURITY_AUDIT: ("security_audit_report.json",),
    LifecyclePhase.DEVOPS_DEPLOY: ("docker-compose.yml",),
}


def completed_phases(session_id: str) -> set:
    """The phases whose artifacts exist on disk, i.e. that have actually been built.

    Derived from the workspace rather than from a stored flag, for the same reason the
    status view does it that way: a flag can claim a phase ran when nothing was written.
    """
    ws_path = _get_workspace_path(session_id)
    return {
        phase.value
        for phase, artifacts in _PHASE_COMPLETION_ARTIFACTS.items()
        if all((ws_path / artifact).exists() for artifact in artifacts)
    }


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

    # Only a phase that has been BUILT can become stale. A phase with no artifacts is
    # not outdated, it is simply not built yet -- and on a first pass through the
    # lifecycle every downstream phase is empty.
    #
    # This is the bug reported from the UI: clicking "Aprobar y Diseñar Arquitectura"
    # saves the requirements and then marked all five downstream phases outdated, so the
    # banner announced "upstream modifications detected" when nothing had been modified.
    # The phases could not even display as OUTDATED -- the status view only shows that
    # for a COMPLETED phase -- so the flag existed solely to raise the banner. Its
    # "Re-sincronizar" button then re-runs generation to DEVOPS_DEPLOY for a state that
    # was already correct, spending real model calls to fix nothing.
    built = completed_phases(session_id)
    stale = [phase for phase in downstream if phase in built]

    # No early return when `stale` is empty: the stored flags still have to be pruned,
    # or a flag whose artifact was removed keeps the banner up with nothing behind it.
    # A first version of this fix returned early and left exactly that state behind,
    # which the test `test_flags_for_artifacts_that_no_longer_exist_are_dropped` caught.

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

        # Drop flags for phases that are no longer built (a workspace reset, or an
        # artifact removed). Keeping them would keep the banner up with nothing behind it.
        existing_outdated = {p for p in prog.get("outdated_phases", []) if p in built}
        existing_outdated.update(stale)
        prog["outdated_phases"] = sorted(existing_outdated)
        sess.phase_progress_json = json.dumps(prog)
        db.commit()
        return sorted(existing_outdated)
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


