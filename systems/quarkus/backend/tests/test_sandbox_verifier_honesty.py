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


# =========================================================================
# T013-T014 (US2), T016-T018 (US3), T024 — appended by feature 012 Phase 4/5/6.
#
# Imports are added here rather than in the header block so the T007-T009
# section above stays exactly as it was (append-only).
# =========================================================================
import json  # noqa: E402
import os  # noqa: E402
import uuid  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings as _settings  # noqa: E402
from app.main import app as _app  # noqa: E402
from app.models.session import GenerationSessionDB, SessionLocal  # noqa: E402


# ---------------------------------------------------------------------------
# T013 — US2: permissive mode parity (SC-002)
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_permissive_mode_restores_the_legacy_outcome(monkeypatch, tmp_path):
    """SC-002: the opt-in switch preserves the pre-change synthetic success."""
    monkeypatch.setattr(_settings, "ALLOW_HERMETIC_FALLBACK", True)
    _daemon(monkeypatch, False)

    result = await run_docker_sandbox(workspace_path=str(tmp_path))

    assert result.exit_code == 0
    assert result.is_success is True
    assert SYNTHETIC_MARKER in result.stdout


@pytest.mark.anyio
async def test_permissive_mode_still_records_the_marking(monkeypatch, tmp_path):
    """FR-007: permissive mode changes what is permitted, not what is recorded.

    Without this, permissive mode would be an audit blind spot and FR-008's
    filtering would be impossible.
    """
    monkeypatch.setattr(_settings, "ALLOW_HERMETIC_FALLBACK", True)
    _daemon(monkeypatch, False)

    result = await run_docker_sandbox(workspace_path=str(tmp_path))

    assert result.fallback_used is True
    assert result.fallback_reason


def test_permissive_session_reaches_verified_while_marked(monkeypatch, tmp_path):
    """FR-002 relaxing FR-003 (Q1 Option A): a permissive session MAY verify.

    The marking is what keeps that safe, so both halves are asserted together.
    """
    from app.orchestrator.nodes.sandbox_node import sandbox_node

    monkeypatch.setattr(_settings, "ALLOW_HERMETIC_FALLBACK", True)
    _daemon(monkeypatch, False)

    out = sandbox_node(_sandbox_state(tmp_path))

    assert out["status"] == SessionStatus.COMPLETED.value
    assert out["current_phase"] == SessionPhase.VERIFIED.value
    assert out["build_success"] is True
    assert out["test_metrics"]["fallback_used"] is True, "a synthetic pass was not marked"
    assert out["verification_fallback_used"] is True


def test_default_and_permissive_disagree_only_about_permission(monkeypatch, tmp_path):
    """The contrast: same trigger, same marking, different permission."""
    from app.orchestrator.nodes.sandbox_node import sandbox_node

    _daemon(monkeypatch, False)
    monkeypatch.setattr(_settings, "ALLOW_HERMETIC_FALLBACK", False)
    honest = sandbox_node(_sandbox_state(tmp_path))

    monkeypatch.setattr(_settings, "ALLOW_HERMETIC_FALLBACK", True)
    permissive = sandbox_node(_sandbox_state(tmp_path))

    assert honest["status"] == SessionStatus.BLOCKED.value
    assert permissive["status"] == SessionStatus.COMPLETED.value
    # Both mark it; neither hides it.
    assert honest["test_metrics"]["fallback_used"] is True
    assert permissive["test_metrics"]["fallback_used"] is True
    assert honest["test_metrics"]["fallback_reason"] == permissive["test_metrics"]["fallback_reason"]


# ---------------------------------------------------------------------------
# T014 — US2: mode detection fails safe
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_flag_absent_is_honest(monkeypatch, tmp_path):
    """The default is honest failure; the switch is never inferred."""
    monkeypatch.delattr(_settings, "ALLOW_HERMETIC_FALLBACK", raising=False)
    _daemon(monkeypatch, False)

    result = await run_docker_sandbox(workspace_path=str(tmp_path))

    assert result.exit_code != 0
    assert result.fallback_used is True


@pytest.mark.anyio
async def test_flag_explicitly_false_is_honest(monkeypatch, tmp_path):
    monkeypatch.setattr(_settings, "ALLOW_HERMETIC_FALLBACK", False)
    _daemon(monkeypatch, False)

    result = await run_docker_sandbox(workspace_path=str(tmp_path))

    assert result.exit_code != 0
    assert result.fallback_used is True


@pytest.mark.parametrize("bad_value", ["banana", "true", "1", 1, 0, None, []])
@pytest.mark.anyio
async def test_unrecognized_flag_value_fails_safe(monkeypatch, tmp_path, bad_value):
    """A typo must not silently permit synthetic verification.

    Only an explicit boolean True enables permissive mode. Note ``"true"`` is
    included deliberately: an operator passing it as a bare attribute assignment
    gets the honest path rather than an accidental opt-in.
    """
    monkeypatch.setattr(_settings, "ALLOW_HERMETIC_FALLBACK", bad_value)
    _daemon(monkeypatch, False)

    result = await run_docker_sandbox(workspace_path=str(tmp_path))

    assert result.exit_code != 0, f"{bad_value!r} enabled permissive mode"
    assert result.fallback_used is True


# ---------------------------------------------------------------------------
# T016 — US3: the metrics payload carries the marking (FR-005)
# ---------------------------------------------------------------------------
def test_metrics_payload_carries_the_marking(monkeypatch, tmp_path):
    from app.orchestrator.nodes.sandbox_node import sandbox_node

    _daemon(monkeypatch, False)
    out = sandbox_node(_sandbox_state(tmp_path))

    metrics = out["test_metrics"]
    assert "fallback_used" in metrics and metrics["fallback_used"] is True
    assert metrics.get("fallback_reason")


def test_metrics_never_claim_passing_without_verification_in_default_mode(monkeypatch, tmp_path):
    """A default-mode substitution must not report tests as passing."""
    from app.orchestrator.nodes.sandbox_node import sandbox_node

    _daemon(monkeypatch, False)
    out = sandbox_node(_sandbox_state(tmp_path))

    metrics = out["test_metrics"]
    assert metrics["allPassed"] is False
    assert metrics["passedTests"] == 0, "a substitution reported passed tests it never ran"
    assert metrics["totalTests"] == 0


# ---------------------------------------------------------------------------
# T017 — US3: session detail exposes the marking, and survives a restart (SC-005)
# ---------------------------------------------------------------------------
@pytest.fixture
def detail_session():
    """A real session row, removed afterwards."""
    session_id = f"t017-{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    try:
        db.add(GenerationSessionDB(
            id=session_id, spec_id="spec-t017", spec_name="t017",
            status=SessionStatus.COMPLETED, phase=SessionPhase.VERIFIED,
        ))
        db.commit()
    finally:
        db.close()
    yield session_id
    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
        db.commit()
    finally:
        db.close()


def test_session_detail_exposes_the_marking_across_a_restart(detail_session):
    """The marking is read back through a FRESH connection, so it is persisted.

    Uses a separate session/engine read rather than the object that wrote it: an
    in-process value would pass a naive assertion but would not survive the
    restart this requirement exists for.
    """
    db = SessionLocal()
    try:
        row = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == detail_session).first()
        row.verification_metrics_json = json.dumps({
            "totalTests": 0, "passedTests": 0, "failedTests": 0,
            "allPassed": False, "fallback_used": True,
            "fallback_reason": "the container runtime is not reachable",
        })
        db.commit()
    finally:
        db.close()

    response = TestClient(_app).get(f"/api/v1/sessions/{detail_session}")

    assert response.status_code == 200
    assert response.json()["verificationFallbackUsed"] is True
    assert response.json()["errorMessage"] is None


def test_session_detail_reports_false_without_metrics(detail_session):
    """A session predating the column is a data gap, not a server error."""
    response = TestClient(_app).get(f"/api/v1/sessions/{detail_session}")

    assert response.status_code == 200, "a session without metrics broke the detail endpoint"
    assert response.json()["verificationFallbackUsed"] is False


def test_session_detail_reports_false_on_unparseable_metrics(detail_session):
    """Corrupt metrics must degrade to False, never raise."""
    db = SessionLocal()
    try:
        row = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == detail_session).first()
        row.verification_metrics_json = "{not valid json"
        db.commit()
    finally:
        db.close()

    response = TestClient(_app).get(f"/api/v1/sessions/{detail_session}")

    assert response.status_code == 200
    assert response.json()["verificationFallbackUsed"] is False


# ---------------------------------------------------------------------------
# T018 — US3: the live stream carries a structured field
# ---------------------------------------------------------------------------
def test_stream_event_carries_the_marking_as_a_structured_field():
    """The stream payload exposes the marking as a field, not only as a log line."""
    from app.api.routes_session import SESSION_EVENT_HISTORY, broadcast_session_event

    session_id = f"t018-{uuid.uuid4().hex[:10]}"
    broadcast_session_event(session_id, "verification_result", {
        "sessionId": session_id,
        "verificationFallbackUsed": True,
        "fallbackReason": "the container runtime is not reachable",
        "buildSuccess": False,
    })

    events = SESSION_EVENT_HISTORY[session_id]
    payload = json.loads(events[0]["data"])
    assert payload["event"] == "verification_result"
    assert payload["verificationFallbackUsed"] is True
    assert payload["fallbackReason"]

    SESSION_EVENT_HISTORY.pop(session_id, None)


def test_the_route_wires_the_marking_into_every_event_payload():
    """Every terminal/stream event that reports an outcome must carry the marking.

    A structural guard: the behavioural shape is covered above, but nothing else
    would fail if a future edit dropped the field from one of the three payloads.
    """
    import inspect
    from app.api import routes_session

    source = inspect.getsource(routes_session)
    for event in ("verification_result", "session_completed", "session_blocked"):
        assert f'"{event}"' in source, f"the {event} event was removed"
    assert source.count('"verificationFallbackUsed"') >= 3, (
        "fewer than three event payloads carry the marking; one has been dropped"
    )
    assert "verification_metrics_json" in source, "the marking is no longer persisted"


# ---------------------------------------------------------------------------
# T024 — SC-003: a real build, verified outside the platform's sandbox wrapper
# ---------------------------------------------------------------------------
REAL_SANDBOX_ENV = "AGENTIA_RUN_REAL_SANDBOX"


def _runtime_reachable() -> bool:
    try:
        from app.services.docker_service import check_docker_daemon
        return bool(check_docker_daemon())
    except Exception:
        return False


def _real_project(root, passing: bool) -> str:
    """A minimal Maven project using the same parent as the warmed cache."""
    (root / "src" / "main" / "java" / "com" / "corp").mkdir(parents=True)
    (root / "src" / "test" / "java" / "com" / "corp").mkdir(parents=True)
    (root / "pom.xml").write_text(
        """<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.3</version>
    <relativePath/>
  </parent>
  <groupId>com.corp</groupId>
  <artifactId>sc003</artifactId>
  <version>1.0.0</version>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
""", encoding="utf-8")
    (root / "src" / "main" / "java" / "com" / "corp" / "App.java").write_text(
        "package com.corp;\npublic class App { public int add(int a, int b) { return a + b; } }\n",
        encoding="utf-8")
    assertion = "assertEquals(2, new App().add(1, 1))" if passing else "assertEquals(3, new App().add(1, 1))"
    (root / "src" / "test" / "java" / "com" / "corp" / "AppTest.java").write_text(
        "package com.corp;\n"
        "import org.junit.jupiter.api.Test;\n"
        "import static org.junit.jupiter.api.Assertions.assertEquals;\n"
        "public class AppTest {\n"
        "    @Test\n"
        "    void adds() {\n"
        f"        {assertion};\n"
        "    }\n}\n", encoding="utf-8")
    return str(root)


@pytest.mark.anyio
async def test_sc003_real_build_pass_and_fail(monkeypatch, tmp_path):
    """SC-003: with a real runtime, a real build runs and is NOT marked as a fallback.

    Opt-in via ``AGENTIA_RUN_REAL_SANDBOX=1`` so the default suite stays hermetic
    (Constitution Principle VI: no test may require a container runtime). Run it
    from a shell that can reach the runtime, per quickstart.md Scenario 3.

    The pass/fail pair is the substance of SC-003: it proves the verifier still
    distinguishes a real pass from a real fail once the synthetic path is closed.
    """
    if os.environ.get(REAL_SANDBOX_ENV) != "1":
        pytest.skip(f"set {REAL_SANDBOX_ENV}=1 in a shell that can reach the container runtime")
    if not _runtime_reachable():
        pytest.skip(
            "the container runtime is not reachable from THIS shell. This is not evidence "
            "that SC-003 fails -- it is a property of the invoking shell (see "
            "constitution-recheck.md §3). Verify from a capable shell."
        )

    monkeypatch.setattr(_settings, "ALLOW_HERMETIC_FALLBACK", False)

    passing = await run_docker_sandbox(workspace_path=_real_project(tmp_path / "pass", True),
                                       timeout_seconds=900)
    assert passing.fallback_used is False, "a real build was reported as a fallback"
    assert passing.exit_code == 0, f"the passing project did not build: {passing.stderr[-400:]}"
    assert passing.is_success is True

    failing = await run_docker_sandbox(workspace_path=_real_project(tmp_path / "fail", False),
                                       timeout_seconds=900)
    assert failing.fallback_used is False, "a real build was reported as a fallback"
    assert failing.exit_code != 0, "a failing test was reported as a pass"
    assert failing.is_success is False
