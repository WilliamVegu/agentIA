"""One verification seam, so both execution paths verify identically.

**Why this module exists.** Verification used to live inside `sandbox_node`, which
only the LangGraph path reaches. The sequential product path -- `POST
/sessions/quick-start` with ``autoRun``, and ``/orchestrator/pipeline/run``, the
routes the readiness report tells clients to use -- ran the generation stages and a
static SAST audit and **never compiled or tested the generated code at all**. So on
the primary product path the acceptance signal did not merely depend on the
generator; it did not exist.

Duplicating the sequence into the second path would have produced two
implementations that drift, which is how one path silently stops injecting. This
repository has already paid for that lesson twice: the diagnostics writer had to be
collapsed to a single function after the stage-exhaustion branch wrote nothing, and
feature 014's best-effort write path reported success while logging nothing.

**The sequence, in order.** Strip version-control metadata, inject the
platform-authored contract test, run the hermetic offline build. The first two are
what make the third an *independent* signal rather than a restatement of the
generator's own opinion of itself.
"""

from __future__ import annotations
from app.services.session_operation_lock import SessionOperationLock

import asyncio
import concurrent.futures
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple
from contextvars import ContextVar
import threading
import uuid

from app.sandbox.docker_runner import DockerExecutionResult, run_docker_sandbox
from app.services.platform_verification import inject_contract_test, strip_vcs_metadata
from app.config import settings
from app.models.execution import ExecutionMode
from app.services.execution_policy import execution_mode

_operation_context = ContextVar('verification_operation', default=None)


@dataclass(frozen=True)
class WorkspaceVerification:
    """The outcome of one verification attempt, and how it was prepared."""

    result: DockerExecutionResult
    #: Workspace-relative path of the injected platform test, or ``None`` when the
    #: preconditions were absent so nothing independent ran. ``None`` is reported,
    #: never treated as a pass.
    platform_test_path: Optional[str]
    #: Version-control directories removed before the build.
    stripped: Tuple[str, ...] = ()
    workspace_fingerprint: Optional[str] = None
    source_changed: bool = False
    snapshot_id: Optional[str] = None

    @property
    def platform_verified(self) -> bool:
        return self.platform_test_path is not None


def run_workspace_verification(workspace_path, log_callback=None, mode=None):
    """Claim the same session lock as deployment before changing or verifying sources."""
    selected = execution_mode(workspace_path=workspace_path, explicit=mode)
    ws = Path(workspace_path).resolve()
    from app.models.session import SessionLocal, GenerationSessionDB
    with SessionLocal() as db:
        stored_session = db.get(GenerationSessionDB, ws.name)
        managed = bool(stored_session and stored_session.execution_mode == ExecutionMode.DOCKER
                       and ws == (Path(settings.WORKSPACE_DIR) / ws.name).resolve())
    if selected != ExecutionMode.DOCKER or not settings.DOCKER_ENABLED or not managed:
        return _verify_workspace(workspace_path, log_callback, selected)
    from app.services import docker_service, local_operations
    from app.models.devops import LocalDeploymentSession, DeploymentStatus
    from app.services.local_runtime import persist
    from app.services.logged_process import CommandCancelled
    borrowed = local_operations.has_borrowed_lock(ws.name)
    with docker_service._operations_lock:
        lock = docker_service._operation_locks.setdefault(ws.name, SessionOperationLock(ws.name))
    if not borrowed and not lock.acquire(blocking=False):
        return WorkspaceVerification(result=DockerExecutionResult(exit_code=1, fallback_used=True,
            fallback_reason='Hay otra operación de esta sesión; espere su resultado antes de verificar.'), platform_test_path=None)
    previous = docker_service._active_deployments.get(ws.name)
    row = previous.model_copy(deep=True) if previous else LocalDeploymentSession(sessionId=ws.name)
    row.operationId, row.status, row.errorMessage = str(uuid.uuid4()), DeploymentStatus.BUILDING, None
    row.healthStatus, row.testUrl = 'UNKNOWN', None
    event = local_operations.register(row, 'VERIFY')
    docker_service._active_deployments[ws.name] = row
    token = _operation_context.set((row, event))
    try:
        local_operations.phase(row, 'VERIFY', event)
        def logs(line):
            docker_service._log_message(ws.name, line, source='verify')
            if log_callback: log_callback(line)
        outcome = _verify_workspace(workspace_path, logs, selected)
        if event.is_set() and not outcome.result.verification_interrupted:
            outcome = WorkspaceVerification(result=DockerExecutionResult(exit_code=-1, fallback_used=True,
                verification_interrupted=True, fallback_reason='Verificación interrumpida; resultado no confirmado.'),
                platform_test_path=outcome.platform_test_path, stripped=outcome.stripped,
                workspace_fingerprint=outcome.workspace_fingerprint, source_changed=outcome.source_changed,
                snapshot_id=outcome.snapshot_id)
        result = outcome.result
        row.status = DeploymentStatus.IDLE if result.is_success else (DeploymentStatus.DOCKER_UNAVAILABLE
            if result.fallback_used and not result.verification_interrupted else DeploymentStatus.FAILED)
        row.operationPhase = 'INTERRUPTED' if result.verification_interrupted else ('COMPLETE' if result.is_success else 'VERIFY')
        row.errorMessage = (result.stderr or result.fallback_reason or 'Verificación no aprobada.')[:4000] if not result.is_success else None
        row.message = 'Verificación finalizada; consulte la evidencia de pruebas de la sesión.'
        return outcome
    except CommandCancelled as exc:
        row.status, row.operationPhase, row.errorMessage = DeploymentStatus.FAILED, 'INTERRUPTED', str(exc)
        return WorkspaceVerification(result=DockerExecutionResult(exit_code=-1, fallback_used=True,
            verification_interrupted=True, fallback_reason=str(exc)), platform_test_path=None)
    except Exception as exc:
        row.status, row.errorMessage = DeploymentStatus.FAILED, str(exc)
        raise
    finally:
        _operation_context.reset(token)
        local_operations.finish(row)
        docker_service._active_deployments[ws.name] = row
        try: persist(row)
        finally:
            if not borrowed: lock.release()


def _verify_workspace(workspace_path, log_callback=None, mode=None):
    selected = execution_mode(workspace_path=workspace_path, explicit=mode)
    if selected != ExecutionMode.DOCKER or not settings.DOCKER_ENABLED:
        return _verify_workspace_live(workspace_path, log_callback, selected)
    from app.services.source_snapshot import SourceSnapshot
    from app.services.verification_policy import workspace_fingerprint
    stripped = strip_vcs_metadata(workspace_path)
    inject_contract_test(workspace_path)
    snapshot = SourceSnapshot(workspace_path)
    try:
        outcome = _verify_workspace_live(str(snapshot.working), log_callback, selected)
        changed = outcome.source_changed or workspace_fingerprint(workspace_path) != snapshot.manifest['workspaceFingerprint']
        if changed and not outcome.source_changed:
            outcome.result.exit_code = outcome.result.exit_code or 1
            outcome.result.stderr += '\nLas fuentes cambiaron durante la verificación; evidencia OUTDATED. Reintente sobre las fuentes actuales.'
        snapshot.finish(outcome.result, changed)
        return WorkspaceVerification(result=outcome.result, platform_test_path=outcome.platform_test_path,
            stripped=tuple(stripped) + outcome.stripped, workspace_fingerprint=snapshot.manifest['workspaceFingerprint'],
            source_changed=changed, snapshot_id=snapshot.id)
    finally:
        snapshot.close()


def _verify_workspace_live(
    workspace_path: str,
    log_callback: Optional[Callable[[str], None]] = None,
    mode: Optional[ExecutionMode] = None,
) -> WorkspaceVerification:
    """Prepare a workspace and run the hermetic build against it.

    Synchronous, because both callers are: the graph node runs inside a worker, and
    the sequential pipeline runs in a daemon thread. The async runner is bridged
    here rather than in each caller, so the bridge exists once.
    """
    stripped = strip_vcs_metadata(workspace_path)
    if stripped and log_callback:
        log_callback(
            f"[VERIFY] Stripped version-control metadata: {', '.join(stripped)}"
        )

    platform_test = inject_contract_test(workspace_path)
    if log_callback:
        if platform_test is None:
            log_callback(
                "[VERIFY] NO platform contract test was injected: the workspace has no "
                "application class, no schema.sql, or no repository. This build's "
                "acceptance signal is entirely generator-authored."
            )
        else:
            log_callback(
                f"[VERIFY] Injected platform-authored persistence contract test: "
                f"{platform_test}"
            )

    # Remove stale XML before execution so earlier builds cannot supply proof.
    ws = Path(workspace_path).resolve()
    from app.services.verification_policy import workspace_fingerprint
    input_fingerprint = workspace_fingerprint(ws)
    report_dirs = [ws / "build/test-results/test", ws / "target/surefire-reports"]
    # Aggregate reactor reports as well as a single-module project.
    report_dirs = sorted(set(report_dirs + [p for p in ws.rglob('surefire-reports') if p.is_dir()] + [p for p in ws.rglob('test-results/test') if p.is_dir()]))
    selected_mode = execution_mode(workspace_path=workspace_path, explicit=mode)
    if selected_mode == ExecutionMode.SOURCE_ONLY:
        reason = "No ejecutadas por elección del usuario: sesión sin Docker."
        (ws / "VERIFICATION_STATUS.md").write_text(
            "# Estado de verificación\n\nCompilación, pruebas y despliegue Docker: NO EJECUTADOS.\n"
            "Elección de esta sesión: sin Docker. Entrega de fuentes sin verificación de ejecución.\n"
            "La auditoría SAST se registra por separado en security_audit_report.json.\n",
            encoding="utf-8")
        if log_callback:
            log_callback("[VERIFY] " + reason)
        result = DockerExecutionResult(exit_code=1, fallback_used=True,
                                       verification_skipped=True, fallback_reason=reason)
    elif not settings.DOCKER_ENABLED:
        result = DockerExecutionResult(exit_code=1, fallback_used=True,
            fallback_reason="Docker elegido, pero deshabilitado por el administrador. Reintentar o continuar sin Docker.")
    else:
        # Keep previous evidence when execution is skipped or prohibited.
        # Delete it only immediately before an actual new execution.
        for directory in report_dirs:
            if directory.resolve().is_relative_to(ws):
                for report in directory.glob("*.xml"):
                    if report.resolve().is_relative_to(ws):
                        report.unlink()
        (ws / "VERIFICATION_STATUS.md").unlink(missing_ok=True)
        result = _run_sandbox_blocking(workspace_path, log_callback)
    if not result.fallback_used:
        # A cold build can create module report directories for the first time.
        report_dirs = sorted(set(report_dirs + [p for p in ws.rglob('surefire-reports') if p.is_dir()] + [p for p in ws.rglob('test-results/test') if p.is_dir()]))
        import xml.etree.ElementTree as ET
        totals = [0, 0, 0, 0]
        found = False
        for directory in report_dirs:
            for report in directory.glob("*.xml"):
                if not report.resolve().is_relative_to(ws):
                    continue
                try:
                    root = ET.parse(report).getroot()
                    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
                    for suite in suites:
                        values = [int(suite.get(key, "0")) for key in ("tests", "failures", "errors", "skipped")]
                        if any(value < 0 for value in values):
                            raise ValueError("Negative test count")
                        totals = [a+b for a,b in zip(totals, values)]
                        found = True
                except (ET.ParseError, ValueError, OSError):
                    result.exit_code = 1
                    result.stderr += "\nInvalid test report: " + report.name
        if found:
            result.stdout += f"\nTests run: {totals[0]}, Failures: {totals[1]}, Errors: {totals[2]}, Skipped: {totals[3]}\n"

    source_changed = bool(input_fingerprint and not result.verification_skipped and not result.fallback_used
                          and workspace_fingerprint(ws) != input_fingerprint)
    if source_changed:
        result.exit_code = result.exit_code or 1
        result.stderr += '\nLas fuentes cambiaron durante la verificación; evidencia OUTDATED. Reintente sobre las fuentes actuales.'
    return WorkspaceVerification(
        result=result,
        platform_test_path=platform_test,
        stripped=stripped,
        workspace_fingerprint=input_fingerprint,
        source_changed=source_changed,
    )


def _run_sandbox_blocking(
    workspace_path: str,
    log_callback: Optional[Callable[[str], None]],
) -> DockerExecutionResult:
    """Drive the async sandbox runner from synchronous code, whatever the loop state.

    Three cases, and getting them wrong hangs or crashes: no loop, a loop that is not
    running, and a loop that IS running (a running loop cannot be re-entered with
    ``run_until_complete``, so the coroutine goes to a worker thread).
    """
    context = _operation_context.get()
    kwargs = {} if context is None else {'cancel_event': context[1], 'operation_id': context[0].operationId,
        'session_id': context[0].sessionId, 'mode': ExecutionMode.DOCKER, 'timeout_seconds': settings.LOCAL_BUILD_TIMEOUT}
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_docker_sandbox(workspace_path, log_callback=log_callback, **kwargs))
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return pool.submit(asyncio.run, run_docker_sandbox(workspace_path, log_callback=log_callback, **kwargs)).result()
