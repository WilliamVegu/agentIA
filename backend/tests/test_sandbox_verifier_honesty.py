"""Sandbox verifier honesty tests (feature 012, tasks T007-T009).

These are the **honest-default** counterparts to the three permissive-path tests in
``test_docker_runner.py``. They assert the behaviour under the default
configuration, where a sandbox run that cannot actually build must NOT report
success.

Why this file exists: the pre-existing ``test_docker_runner.py`` asserted
``exit_code == 0`` and ``"BUILD SUCCESS"`` for a daemon-offline run, an
image-missing run, and a pipe failure — i.e. it encoded the bug as required
behaviour. A session could therefore reach ``VERIFIED`` for a workspace that was
never compiled, and every downstream figure inherited that. These tests pin the
opposite.

Injection is at the model/subprocess boundary (``check_docker_daemon`` and
``asyncio.create_subprocess_exec``), so no test here needs a real container
runtime or network access (Constitution Principle VI).
"""

import asyncio

import pytest

from app.config import settings
from app.models.session import SessionPhase, SessionStatus
from app.sandbox.docker_runner import run_docker_sandbox

SYNTHETIC_MARKER = "BUILD SUCCESS"


# ---------------------------------------------------------------------------
# Subprocess doubles for the four substitution triggers
# ---------------------------------------------------------------------------
class _MockStream:
    def __init__(self, data: bytes):
        self.data = data
        self.read = False

    async def readline(self):
        if not self.read:
            self.read = True
            return self.data
        return b""


class _MockProcess:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self.stdout = _MockStream(stdout)
        self.stderr = _MockStream(stderr)

    async def wait(self):
        return self.returncode


def _daemon(monkeypatch, available: bool) -> None:
    import app.services.docker_service as ds_mod
    monkeypatch.setattr(ds_mod, "check_docker_daemon", lambda: available)


def _spawn(monkeypatch, process) -> None:
    async def _fake(*args, **kwargs):
        return process
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake)


def _spawn_raises(monkeypatch, exc: Exception) -> None:
    async def _fake(*args, **kwargs):
        raise exc
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake)


# ---------------------------------------------------------------------------
# T007 — every substitution trigger reports a non-success under default config
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_trigger1_daemon_unavailable_is_not_a_success(monkeypatch, tmp_path):
    """Runtime unavailable: the classic case that reported VERIFIED for nothing."""
    _daemon(monkeypatch, False)

    result = await run_docker_sandbox(workspace_path=str(tmp_path))

    assert result.exit_code != 0, "a run that could not build reported success"
    assert result.is_success is False
    assert result.fallback_used is True
    assert result.fallback_reason, "no reason was recorded for the substitution"
    assert SYNTHETIC_MARKER not in result.stdout, "the synthetic success text was emitted"
    assert result.attribution_ambiguous is False, "this trigger is an unambiguous environment fault"
    assert result.matched_pattern is None


@pytest.mark.anyio
async def test_trigger2_runtime_executable_missing_is_not_a_success(monkeypatch, tmp_path):
    """The runtime executable is absent (FileNotFoundError on spawn)."""
    _daemon(monkeypatch, True)
    _spawn_raises(monkeypatch, FileNotFoundError("docker: command not found"))

    result = await run_docker_sandbox(workspace_path=str(tmp_path))

    assert result.exit_code != 0
    assert result.is_success is False
    assert result.fallback_used is True
    assert result.fallback_reason
    assert SYNTHETIC_MARKER not in result.stdout
    assert result.attribution_ambiguous is False


@pytest.mark.anyio
async def test_trigger3_runtime_communication_failure_is_not_a_success(monkeypatch, tmp_path):
    """The runtime is reachable but communication fails before the build runs.

    This is the *exception* path: spawning the container raises rather than
    returning a process. (A process that returns non-zero lands in trigger 4, so
    the distinction matters — mocking a return here would silently test the wrong
    branch.)
    """
    _daemon(monkeypatch, True)
    _spawn_raises(
        monkeypatch,
        RuntimeError("docker: connection refused while connecting to the daemon"),
    )

    result = await run_docker_sandbox(workspace_path=str(tmp_path))

    assert result.exit_code != 0
    assert result.is_success is False
    assert result.fallback_used is True
    assert result.fallback_reason
    assert SYNTHETIC_MARKER not in result.stdout
    assert result.attribution_ambiguous is False, "a communication failure is not ambiguous"


@pytest.mark.anyio
async def test_trigger4_environment_looking_build_failure_is_not_a_success(monkeypatch, tmp_path):
    """The most severe trigger: a real build FAILURE was being turned into a PASS.

    The build exits non-zero and its output matches a recognised environment
    pattern, so the cause may be the environment or the project. Either way the
    outcome must not be a synthetic success.
    """
    _daemon(monkeypatch, True)
    _spawn(monkeypatch, _MockProcess(
        returncode=1,
        stderr=b"[ERROR] The following artifacts could not be resolved: "
               b"org.springframework:spring-core:jar:3.2.3\n",
    ))

    result = await run_docker_sandbox(workspace_path=str(tmp_path))

    assert result.exit_code != 0, "a real build failure was reported as a pass"
    assert result.is_success is False
    assert result.fallback_used is True
    assert result.fallback_reason
    assert SYNTHETIC_MARKER not in result.stdout


@pytest.mark.anyio
async def test_a_real_failing_build_is_reported_as_a_failure_not_a_fallback(monkeypatch, tmp_path):
    """A genuine build failure with no environment pattern stays 'verified and failed'.

    The distinction FR-001 requires is not "everything fails" — it is that
    "could not verify" and "verified and failed" are told apart. A test assertion
    failure with ordinary output must NOT be classified as a fallback.
    """
    _daemon(monkeypatch, True)
    _spawn(monkeypatch, _MockProcess(
        returncode=1,
        stdout=b"[ERROR] Tests run: 1, Failures: 1, Errors: 0, Skipped: 0\n"
               b"[INFO] BUILD FAILURE\n",
    ))

    result = await run_docker_sandbox(workspace_path=str(tmp_path))

    assert result.exit_code != 0
    assert result.is_success is False
    assert result.fallback_used is False, "a genuine test failure was misreported as unverifiable"
    assert result.attribution_ambiguous is False
    assert SYNTHETIC_MARKER not in result.stdout
    assert "Tests run: 1, Failures: 1" in result.stdout, "the real build output was discarded"


@pytest.mark.anyio
async def test_a_real_passing_build_is_not_marked_as_a_fallback(monkeypatch, tmp_path):
    """The healthy path must stay healthy: no marking, real output preserved."""
    _daemon(monkeypatch, True)
    _spawn(monkeypatch, _MockProcess(
        returncode=0,
        stdout=b"[INFO] Tests run: 1, Failures: 0, Errors: 0, Skipped: 0\n[INFO] BUILD SUCCESS\n",
    ))

    result = await run_docker_sandbox(workspace_path=str(tmp_path))

    assert result.exit_code == 0
    assert result.is_success is True
    assert result.fallback_used is False
    assert result.fallback_reason is None
    assert "Tests run: 1, Failures: 0" in result.stdout


# ---------------------------------------------------------------------------
# T009 — ambiguous attribution is recorded, not resolved by guesswork
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_trigger4_records_the_matched_pattern_and_the_ambiguity(monkeypatch, tmp_path):
    """FR-009 / SC-007: a broken build file must stay distinguishable from a missing image."""
    _daemon(monkeypatch, True)
    _spawn(monkeypatch, _MockProcess(
        returncode=1,
        stderr=b"[ERROR] Non-resolvable parent POM for com.corp:notes:1.0\n",
    ))

    result = await run_docker_sandbox(workspace_path=str(tmp_path))

    assert result.fallback_used is True
    assert result.attribution_ambiguous is True, "the ambiguity was not recorded"
    assert result.matched_pattern, "the matched pattern was not recorded"
    assert result.matched_pattern in ("non-resolvable parent pom",), (
        f"unexpected pattern recorded: {result.matched_pattern!r}"
    )


def test_unambiguous_triggers_do_not_claim_ambiguity():
    """Only trigger 4 is ambiguous; the other three are definite environment faults."""
    from app.sandbox.docker_runner import DockerExecutionResult

    plain = DockerExecutionResult(exit_code=1)
    assert plain.attribution_ambiguous is False
    assert plain.matched_pattern is None
    assert plain.fallback_used is False


def test_the_environment_pattern_list_was_not_narrowed():
    """Q2 resolution: retain the pattern set; record the ambiguity instead.

    Narrowing would risk classifying a real environment fault as a project error,
    producing a false FAILURE -- worse than a false "could not verify".
    """
    import inspect

    source = inspect.getsource(
        __import__("app.sandbox.docker_runner", fromlist=["x"]).run_docker_sandbox
    )
    for pattern in (
        "unresolvablemodelexception",
        "projectbuildingexception",
        "non-resolvable parent pom",
        "unable to find image",
        "cannot connect to the docker daemon",
    ):
        assert pattern in source, f"the pattern {pattern!r} was removed from the set"


# ---------------------------------------------------------------------------
# T008 — terminal state, and the repair loop is NOT entered
# ---------------------------------------------------------------------------
def _sandbox_state(workspace) -> dict:
    return {
        "session_id": "t008",
        "workspace_path": str(workspace),
        "generated_files": {},
        "logs": [],
        "repair_attempts": 0,
        "max_repair_attempts": 5,
    }


def test_sandbox_node_blocks_instead_of_verifying(monkeypatch, tmp_path):
    """FR-003: no VERIFIED state, reason on the ``error`` key, marking in metrics."""
    from app.orchestrator.nodes.sandbox_node import sandbox_node

    _daemon(monkeypatch, False)

    out = sandbox_node(_sandbox_state(tmp_path))

    assert out["status"] == SessionStatus.BLOCKED.value
    assert out["current_phase"] == SessionPhase.FAILED.value
    assert out["build_success"] is False
    assert out["test_metrics"]["fallback_used"] is True
    assert out["test_metrics"]["allPassed"] is False, "a substitution must not claim passing tests"

    # FR-003: the reason goes on the state key `error`, which routes_session reads
    # via final_state.get("error") and persists into the error_message COLUMN.
    # Using the column's name as the key would silently discard the reason.
    assert out.get("error"), "no reason was recorded on the error key"
    assert "error_message" not in out, "the reason was written to the wrong state key"
    reason = out["error"].lower()
    assert "verif" in reason, f"the reason does not say verification failed: {out['error']!r}"
    assert "test" not in reason.replace("tested", ""), (
        f"the reason misattributes the fault to the generated code: {out['error']!r}"
    )


def test_blocked_sandbox_result_routes_to_end_not_repair(monkeypatch, tmp_path):
    """FR-003 / FR-023: an unverifiable session must not enter the repair loop.

    No code patch fixes a missing container runtime, and entering repair would
    spend the bounded repair budget on an environment fault.
    """
    from langgraph.graph import END
    from app.orchestrator.graph import _route_after_sandbox
    from app.orchestrator.nodes.sandbox_node import sandbox_node

    _daemon(monkeypatch, False)
    out = sandbox_node(_sandbox_state(tmp_path))

    assert _route_after_sandbox(out) == END, "an unverifiable session was routed into repair"


def test_real_sandbox_failure_still_routes_to_repair(monkeypatch, tmp_path):
    """The repair path must stay reachable for genuine build failures."""
    from app.orchestrator.graph import _route_after_sandbox

    state = {"build_success": False, "status": "RUNNING"}
    assert _route_after_sandbox(state) == "repair", (
        "a genuine build failure no longer reaches the repair loop"
    )
