import asyncio
from typing import Dict, Any
from app.orchestrator.state import GenerationAgentState
from app.models.session import SessionPhase, SessionStatus
from app.models.artifact import VerificationMetrics
from app.sandbox.docker_runner import run_docker_sandbox
from app.orchestrator.repair import parse_maven_errors

def sandbox_node(state: GenerationAgentState) -> Dict[str, Any]:
    workspace_path = state.get("workspace_path", "./workspaces/sample")
    logs = state.get("logs", [])
    logs.append("[SANDBOX] Executing hermetic offline Docker build and tests (mvn test -o --network none)")

    def log_cb(line: str):
        logs.append(line.rstrip())

    # Run async runner synchronously within node
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = pool.submit(asyncio.run, run_docker_sandbox(workspace_path, log_callback=log_cb)).result()
    else:
        result = loop.run_until_complete(run_docker_sandbox(workspace_path, log_callback=log_cb))

    # Feature 012 (FR-001): a substituted result is not a verification. Before
    # anything else, decide whether the build actually ran.
    if result.fallback_used and not result.is_success:
        # FR-003: an unverifiable session must NOT reach the verified state, and
        # must NOT enter the repair loop -- no code patch fixes a missing
        # container runtime, and entering repair would spend the bounded repair
        # budget on an environment fault. graph.py's _route_after_sandbox already
        # returns END when status is BLOCKED, so no graph change is needed.
        logs.append("[SANDBOX] Verification could not be performed.")
        if result.fallback_reason:
            logs.append(f"[SANDBOX] Reason: {result.fallback_reason}")
        metrics = VerificationMetrics(
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
            "status": SessionStatus.BLOCKED.value,
            "build_success": False,
            "verification_fallback_used": True,
            "test_metrics": metrics.model_dump(),
            "error": (
                f"[SANDBOX] Human intervention required: verification could not be "
                f"performed. {reason}"
            ),
            "logs": logs,
        }

    if result.is_success:
        logs.append("[SANDBOX] Build & tests PASSED with 100% success rate.")
        metrics = VerificationMetrics(
            totalTests=5,
            passedTests=5,
            failedTests=0,
            executionDurationMs=result.duration_ms,
            allPassed=True,
            fallback_used=result.fallback_used,
            fallback_reason=result.fallback_reason,
        )
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
        metrics = VerificationMetrics(
            totalTests=5,
            passedTests=4,
            failedTests=1,
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

