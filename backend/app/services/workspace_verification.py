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

import asyncio
import concurrent.futures
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple

from app.sandbox.docker_runner import DockerExecutionResult, run_docker_sandbox
from app.services.platform_verification import inject_contract_test, strip_vcs_metadata


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

    @property
    def platform_verified(self) -> bool:
        return self.platform_test_path is not None


def run_workspace_verification(
    workspace_path: str,
    log_callback: Optional[Callable[[str], None]] = None,
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
    report_dirs = [ws / "build/test-results/test", ws / "target/surefire-reports"]
    for directory in report_dirs:
        if directory.resolve().is_relative_to(ws):
            for report in directory.glob("*.xml"):
                if report.resolve().is_relative_to(ws):
                    report.unlink()
    result = _run_sandbox_blocking(workspace_path, log_callback)
    if not result.fallback_used:
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

    return WorkspaceVerification(
        result=result,
        platform_test_path=platform_test,
        stripped=stripped,
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
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_docker_sandbox(workspace_path, log_callback=log_callback))
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return pool.submit(asyncio.run, run_docker_sandbox(workspace_path, log_callback=log_callback)).result()
