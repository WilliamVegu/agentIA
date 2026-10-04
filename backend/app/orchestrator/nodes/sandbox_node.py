from app.services.verification_policy import workspace_fingerprint
import asyncio
from typing import Dict, Any
from pathlib import Path
from app.orchestrator.state import GenerationAgentState
from app.models.session import SessionPhase, SessionStatus
from app.models.artifact import VerificationMetrics
from app.sandbox.docker_runner import parse_test_counts
from app.orchestrator.repair import parse_maven_errors
from app.services.workspace_verification import run_workspace_verification

def sandbox_node(state: GenerationAgentState) -> Dict[str, Any]:
    workspace_path = state.get("workspace_path", "./workspaces/sample")
    logs = state.get("logs", [])
    logs.append("[SANDBOX] Preparando verificación según la elección de ejecución de la sesión.")

    def log_cb(line: str):
        logs.append(line.rstrip())

    # Preparation and execution live in ONE seam (`run_workspace_verification`),
    # because the sequential product path must verify identically. When this logic
    # was inline here, only the graph path had it at all -- the route the readiness
    # report tells clients to use generated code and never compiled it.
    # Deployment dependencies must be present before tests establish evidence.
    from app.services.devops_service import generate_all_devops_assets
    blueprint = state.get("blueprint") or {}
    from app.models.session import SessionLocal, GenerationSessionDB
    session_id = state.get("session_id") or Path(workspace_path).name
    with SessionLocal() as db:
        session = db.get(GenerationSessionDB, session_id)
        service_name = blueprint.get("serviceName") or (session.spec_name if session else "microservice")
        database = blueprint.get("databaseMode") or (session.database_engine if session else "POSTGRESQL")
    if (Path(workspace_path) / "pom.xml").exists() or any((Path(workspace_path) / file).exists() for file in ("build.gradle", "build.gradle.kts")):
        generate_all_devops_assets(workspace_path, session_id, service_name, db_engine=database)
    verification = run_workspace_verification(workspace_path, log_callback=log_cb, mode=state.get("execution_mode"))
    result = verification.result
    platform_verified = verification.platform_verified

    if result.verification_skipped:
        logs.append("[SANDBOX] Pruebas no ejecutadas: modo sin virtualización. Continuando con entrega de fuentes.")
        metrics = VerificationMetrics(totalTests=0, passedTests=0, failedTests=0,
            allPassed=False, fallback_used=True, fallback_reason=result.fallback_reason,
            verificationSkipped=True, verificationOutcome="SKIPPED_BY_CHOICE", workspaceFingerprint=workspace_fingerprint(workspace_path))
        return {"current_phase": SessionPhase.CODE_GENERATION.value,
                "status": SessionStatus.COMPLETED.value, "build_success": False,
                "verification_fallback_used": True, "test_metrics": metrics.model_dump(),
                "error": None, "logs": logs}

    # Feature 012 (FR-001): a substituted result is not a verification. Before
    # anything else, decide whether the build actually ran.
    if result.fallback_used:
        # FR-003: an unverifiable session must NOT reach the verified state, and
        # must NOT enter the repair loop -- no code patch fixes a missing
        # container runtime, and entering repair would spend the bounded repair
        # budget on an environment fault. graph.py's _route_after_sandbox already
        # returns END when status is BLOCKED, so no graph change is needed.
        logs.append("[SANDBOX] Verification could not be performed.")
        if result.fallback_reason:
            logs.append(f"[SANDBOX] Reason: {result.fallback_reason}")
        metrics = VerificationMetrics(
            verificationOutcome="ENVIRONMENT_UNAVAILABLE",
            totalTests=0,
            passedTests=0,
            failedTests=0,
            executionDurationMs=result.duration_ms,
            allPassed=False,
            fallback_used=True,
            fallback_reason=result.fallback_reason,
        )
        # The reason goes on the `error` key: routes_session reads
        # final_state.get("error") and persists it into the error_message COLUMN.
        # Using the column's name as the state key would discard it silently.
        reason = result.fallback_reason or "the sandbox could not verify this workspace"
        return {
            "current_phase": SessionPhase.FAILED.value,
            "status": SessionStatus.PAUSED.value,
            "build_success": False,
            "verification_fallback_used": True,
            "test_metrics": metrics.model_dump(),
            "error": (
                f"[SANDBOX] Reintentar o continuar sin Docker: {reason}"
            ),
            "logs": logs,
        }

    if result.is_success:
        # Report what the build actually ran. The previous fixed
        # ``totalTests=5, passedTests=5`` was a fabricated figure in the one field
        # the acceptance signal rests on.
        counts = parse_test_counts(result.stdout)
        if counts is None:
            logs.append(
                "[SANDBOX] The build reported success but printed no test summary: "
                "there is no evidence that any test executed."
            )
            total, passed, failed = 0, 0, 0
            all_passed = False  # fail closed: no summary is not a demonstration
        else:
            total, passed = counts.total, counts.passed
            failed = counts.failures + counts.errors
            all_passed = counts.all_passed and counts.total > 0
        logs.append(
            f"[SANDBOX] Build & tests PASSED ({passed}/{total} tests). "
            f"Platform contract test injected: {platform_verified}."
        )
        metrics = VerificationMetrics(
            totalTests=total,
            passedTests=passed,
            failedTests=failed,
            executionDurationMs=result.duration_ms,
            allPassed=all_passed,
            workspaceFingerprint=workspace_fingerprint(workspace_path),
            fallback_used=result.fallback_used,
            fallback_reason=result.fallback_reason,
        )
        if not all_passed:
            return {"current_phase": SessionPhase.FAILED.value, "status": SessionStatus.BLOCKED.value,
                    "build_success": False, "test_metrics": metrics.model_dump(),
                    "error": "No successful nonempty test suite was demonstrated.", "logs": logs}
        return {
            "current_phase": SessionPhase.VERIFIED.value,
            "status": SessionStatus.COMPLETED.value,
            "build_success": True,
            "verification_fallback_used": result.fallback_used,
            "test_metrics": metrics.model_dump(),
            "logs": logs
        }
    else:
        logs.append(f"[SANDBOX] Build failed with exit code {result.exit_code}.")
        diag = parse_maven_errors(result.stdout + "\n" + result.stderr)
        counts = parse_test_counts(result.stdout)
        if counts is None:
            total, passed, failed = 0, 0, 0
        else:
            total, passed = counts.total, counts.passed
            failed = counts.failures + counts.errors
        metrics = VerificationMetrics(
            totalTests=total,
            passedTests=passed,
            failedTests=failed,
            executionDurationMs=result.duration_ms,
            allPassed=False,
            fallback_used=result.fallback_used,
            fallback_reason=result.fallback_reason,
        )
        return {
            "current_phase": SessionPhase.SELF_REPAIR.value,
            "build_success": False,
            "verification_fallback_used": result.fallback_used,
            "last_diagnostic": diag,
            "test_metrics": metrics.model_dump(),
            "logs": logs
        }

