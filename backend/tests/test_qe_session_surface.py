"""QE coverage: the session surface (``api/routes_session.py``).

This is the product's main surface -- create, list, read, cancel, and the SSE stream the
monitor screen lives on -- and it sat at 69.9%, the second-worst module of any size. The
uncovered half was mostly the *outcome* paths: what gets persisted and broadcast when a
generation finishes, finishes as BLOCKED, or blows up.

That is the half worth testing, because the failure mode is not a crash. It is a session
that reaches a terminal state and tells the operator the wrong thing, or tells them
nothing at all:

* ``verificationFallbackUsed`` (feature 012) exists so a session that reached VERIFIED on a
  *substituted* verification says so. If the flag stops being persisted, the UI silently
  goes back to claiming a real verification.
* The BLOCKED path must record diagnostics **as well as** the COMPLETED path. A blocked
  session is precisely the one worth diagnosing; it would be easy to write the recording
  call only on the happy path and never notice.
* A crash inside the graph must still terminate the session. An exception escaping the
  worker leaves the row at RUNNING forever and the UI polling a session that is gone.

The SSE generator is driven directly (``response.body_iterator``) rather than through an
HTTP client, so the replay/keepalive/cleanup contract is asserted without a socket or a
timeout race. The endpoints themselves are called as coroutines, which is what they are --
routing is FastAPI's job and is covered elsewhere.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import app.api.routes_session as rs  # noqa: E402
import app.services.lifecycle_service as lifecycle  # noqa: E402
from app.services.verification_policy import workspace_fingerprint  # noqa: E402
from app.models.session import (  # noqa: E402
    GenerationSessionDB,
    QuickStartSessionRequest,
    SessionLocal,
    SessionPhase,
    SessionStatus,
)

SESSION_ID = "qe-session-surface"


class _Unsettable:
    """Rejects attribute assignment, to prove the persistence helpers swallow the failure."""

    def __setattr__(self, name, value):
        raise RuntimeError("row is detached")


class _FakeRow:
    def __init__(self, raw=None):
        self.verification_metrics_json = raw


class _Mode:
    mode = "deterministic"
    provider = "offline"
    model = "mock"
    reason = "test"


class _FakeGraph:
    """A LangGraph stand-in whose ``stream`` replays a scripted list of node outputs."""

    def __init__(self, steps=None, explode=None):
        self._steps = steps or []
        self._explode = explode

    def stream(self, initial_state):
        if self._explode is not None:
            raise self._explode
        return iter(self._steps)


@pytest.fixture(autouse=True)
def isolated_module_state(monkeypatch):
    """The three module-level stores are process-global; each test gets a clean slate."""
    monkeypatch.setattr(rs, "SESSION_EVENT_HISTORY", {})
    monkeypatch.setattr(rs, "SESSION_EVENT_SUBSCRIBERS", {})
    monkeypatch.setattr(rs, "SESSION_GENERATION_STATE", {})
    yield


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(rs.settings, "WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr(lifecycle.settings, "WORKSPACE_DIR", str(tmp_path))
    return tmp_path


def _make_session(session_id, **overrides):
    defaults = dict(
        id=session_id,
        spec_id="spec-qe",
        spec_name="OrderService",
        status=SessionStatus.QUEUED,
        phase=SessionPhase.INITIALIZATION,
        current_lifecycle_phase="INITIAL",
        lifecycle_mode="GUIDED_STEP",
        repair_attempts=0,
    )
    defaults.update(overrides)
    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
        db.add(GenerationSessionDB(**defaults))
        db.commit()
    finally:
        db.close()


def _row(session_id):
    db = SessionLocal()
    try:
        return db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
    finally:
        db.close()


def _events(session_id):
    return [event["event"] for event in rs.SESSION_EVENT_HISTORY.get(session_id, [])]


def _payload(session_id, event_type):
    for event in rs.SESSION_EVENT_HISTORY.get(session_id, []):
        if event["event"] == event_type:
            return json.loads(event["data"])
    raise AssertionError(f"no {event_type} event was broadcast")


# ---------------------------------------------------------------------------
# _verification_fallback_used -- the honesty flag
# ---------------------------------------------------------------------------
def test_a_missing_session_row_reports_no_fallback():
    assert rs._verification_fallback_used(None) is False


def test_a_missing_metrics_column_reports_no_fallback():
    """A row written before feature 012 has no column value; that is a data gap, not an error."""
    assert rs._verification_fallback_used(object()) is False


def test_empty_metrics_report_no_fallback():
    assert rs._verification_fallback_used(_FakeRow("")) is False


def test_persisted_fallback_metrics_are_read_back_as_true():
    assert rs._verification_fallback_used(_FakeRow(json.dumps({"fallback_used": True}))) is True


def test_persisted_real_verification_is_read_back_as_false():
    assert rs._verification_fallback_used(_FakeRow(json.dumps({"fallback_used": False}))) is False


def test_corrupt_metrics_degrade_to_no_fallback():
    assert rs._verification_fallback_used(_FakeRow("{not json")) is False


def test_metrics_that_are_not_an_object_degrade_to_no_fallback():
    """``[1, 2]`` parses as JSON but has no ``.get``; the endpoint must not 500 over it."""
    assert rs._verification_fallback_used(_FakeRow("[1, 2]")) is False


# ---------------------------------------------------------------------------
# _persist_verification_metrics
# ---------------------------------------------------------------------------
def test_persisting_without_a_row_is_a_no_op():
    assert rs._persist_verification_metrics(None, {"test_metrics": {"fallback_used": True}}) is None


def test_persisting_without_metrics_leaves_the_row_untouched():
    row = _FakeRow()

    rs._persist_verification_metrics(row, {"status": "COMPLETED"})

    assert row.verification_metrics_json is None


def test_persisting_metrics_writes_the_json_that_the_reader_expects():
    """The writer and the reader are two functions; this pins that they agree."""
    row = _FakeRow()

    rs._persist_verification_metrics(row, {"test_metrics": {"fallback_used": True, "reason": "x"}})

    assert json.loads(row.verification_metrics_json)["fallback_used"] is True
    assert rs._verification_fallback_used(row) is True


def test_a_row_that_rejects_assignment_does_not_break_the_session():
    """Metrics are bookkeeping; failing to store them must not fail the generation."""
    rs._persist_verification_metrics(_Unsettable(), {"test_metrics": {"fallback_used": True}})


# ---------------------------------------------------------------------------
# _persist_diagnostics
# ---------------------------------------------------------------------------
def test_diagnostics_delegate_to_the_single_writer(monkeypatch):
    """Feature 015 made one function the only writer; a local copy here would drift."""
    seen = {}

    def fake(session_id, final_state, **kwargs):
        seen["session_id"] = session_id
        seen["state"] = final_state
        return True

    monkeypatch.setattr(rs, "record_session_diagnostics", fake)

    assert rs._persist_diagnostics(SESSION_ID, {"status": "BLOCKED"}) is True
    assert seen["session_id"] == SESSION_ID
    assert seen["state"] == {"status": "BLOCKED"}


# ---------------------------------------------------------------------------
# broadcast_session_event
# ---------------------------------------------------------------------------
def test_a_broadcast_event_carries_a_string_id_and_the_event_name_twice():
    """The UI and the generic SSE client each read a different field; both must be there."""
    rs.broadcast_session_event(SESSION_ID, "phase_transition", {"currentPhase": "SCAFFOLDING"})

    event = rs.SESSION_EVENT_HISTORY[SESSION_ID][0]
    payload = json.loads(event["data"])

    assert event["id"] == "1"
    assert event["event"] == "phase_transition"
    assert payload["event"] == "phase_transition"
    assert payload["type"] == "phase_transition"
    assert payload["currentPhase"] == "SCAFFOLDING"


def test_event_ids_increase_within_a_session():
    rs.broadcast_session_event(SESSION_ID, "a", {})
    rs.broadcast_session_event(SESSION_ID, "b", {})

    assert [e["id"] for e in rs.SESSION_EVENT_HISTORY[SESSION_ID]] == ["1", "2"]


def test_an_explicit_event_field_is_not_overwritten():
    """Some callers set ``event`` themselves to distinguish a sub-type."""
    rs.broadcast_session_event(SESSION_ID, "build_log", {"event": "custom_kind"})

    assert json.loads(rs.SESSION_EVENT_HISTORY[SESSION_ID][0]["data"])["event"] == "custom_kind"


def test_a_subscriber_on_a_running_loop_is_notified_thread_safely():
    """The graph runs in an executor thread, so ``put_nowait`` from here is not safe.

    Notifying through the loop is what makes the stream work at all when generation is
    happening off the event-loop thread.
    """
    scheduled = []

    class _Loop:
        def is_running(self):
            return True

        def call_soon_threadsafe(self, fn, arg):
            scheduled.append((fn, arg))

    class _Queue:
        _loop = _Loop()

        def put_nowait(self, item):  # pragma: no cover - must not be called directly
            raise AssertionError("a running loop must be notified via call_soon_threadsafe")

    rs.SESSION_EVENT_SUBSCRIBERS[SESSION_ID] = [_Queue()]

    rs.broadcast_session_event(SESSION_ID, "phase_transition", {})

    assert len(scheduled) == 1


def test_a_subscriber_without_a_loop_is_written_to_directly():
    received = []

    class _Queue:
        _loop = None

        def put_nowait(self, item):
            received.append(item)

    rs.SESSION_EVENT_SUBSCRIBERS[SESSION_ID] = [_Queue()]

    rs.broadcast_session_event(SESSION_ID, "phase_transition", {"x": 1})

    assert len(received) == 1
    assert json.loads(received[0]["data"])["x"] == 1


def test_a_dead_subscriber_does_not_break_the_broadcast_to_the_living_one():
    """One disconnected browser tab must not stop the other tabs from updating."""
    received = []

    class _Dead:
        _loop = None

        def put_nowait(self, item):
            raise RuntimeError("queue closed")

    class _Live:
        _loop = None

        def put_nowait(self, item):
            received.append(item)

    rs.SESSION_EVENT_SUBSCRIBERS[SESSION_ID] = [_Dead(), _Live()]

    rs.broadcast_session_event(SESSION_ID, "phase_transition", {})

    assert len(received) == 1


# ---------------------------------------------------------------------------
# stream_session_events
# ---------------------------------------------------------------------------
def test_streaming_an_unknown_session_is_a_404(workspace):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(rs.stream_session_events("qe-no-such-session", None))

    assert excinfo.value.status_code == 404


def test_the_stream_replays_history_then_cleans_up_the_subscriber(workspace):
    """A late subscriber must receive the events it missed, and must be removed on close.

    The cleanup is the leak guard: every reconnect appends a queue, and a queue that is
    never removed accumulates for the life of the process.
    """
    _make_session(SESSION_ID)
    rs.broadcast_session_event(SESSION_ID, "phase_transition", {"n": 1})
    rs.broadcast_session_event(SESSION_ID, "build_log", {"n": 2})

    async def scenario():
        response = await rs.stream_session_events(SESSION_ID, None)
        stream = response.body_iterator
        first = await stream.__anext__()
        second = await stream.__anext__()
        await stream.aclose()
        return first, second

    first, second = asyncio.run(scenario())

    assert json.loads(first["data"])["n"] == 1
    assert json.loads(second["data"])["n"] == 2
    assert rs.SESSION_EVENT_SUBSCRIBERS[SESSION_ID] == [], "the closed stream leaked its queue"


def test_a_live_event_reaches_a_connected_stream_after_the_replay(workspace):
    """The whole point of the SSE endpoint: generation events arrive while the client waits.

    The first pull must elapse before the broadcast, or the event is delivered by the
    **history replay** instead of the live queue -- the generator body does not start until
    the first ``__anext__``, so an event broadcast earlier is simply part of the history by
    then. The keepalive here is what proves the generator is parked on the queue, making
    the live path the only one left that can deliver the second event.
    """
    _make_session(SESSION_ID)

    async def scenario():
        response = await rs.stream_session_events(SESSION_ID, None)
        stream = response.body_iterator
        idle = await asyncio.wait_for(stream.__anext__(), timeout=3.0)
        rs.broadcast_session_event(
            SESSION_ID, "phase_transition", {"currentPhase": "SANDBOX_BUILD"}
        )
        live = await asyncio.wait_for(stream.__anext__(), timeout=3.0)
        await stream.aclose()
        return idle, live

    idle, live = asyncio.run(scenario())

    assert idle == {"comment": "keepalive"}
    assert json.loads(live["data"])["currentPhase"] == "SANDBOX_BUILD"


def test_a_disconnected_client_is_unsubscribed(workspace):
    """The leak guard for a client that goes away mid-stream.

    A browser that closes the tab leaves the generator awaiting the queue. If that
    unwinding does not remove the subscriber, every reconnect adds another queue that is
    never released.
    """
    _make_session(SESSION_ID)

    async def scenario():
        response = await rs.stream_session_events(SESSION_ID, None)
        stream = response.body_iterator
        task = asyncio.create_task(stream.__anext__())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, StopAsyncIteration):
            pass
        await stream.aclose()
        return list(rs.SESSION_EVENT_SUBSCRIBERS.get(SESSION_ID, []))

    assert asyncio.run(scenario()) == []


def test_an_idle_stream_emits_a_keepalive(workspace):
    """Proxies close an idle SSE connection; the keepalive comment is what prevents that."""
    _make_session(SESSION_ID)

    async def scenario():
        response = await rs.stream_session_events(SESSION_ID, None)
        stream = response.body_iterator
        item = await asyncio.wait_for(stream.__anext__(), timeout=3.0)
        await stream.aclose()
        return item

    assert asyncio.run(scenario()) == {"comment": "keepalive"}


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------
def test_a_completed_session_is_listed_at_one_hundred_percent(workspace):
    """Successfully generating is not the same as verifying, so the row must carry evidence.

    ``list_sessions`` asks ``session_is_verified``: status COMPLETED, phase VERIFIED, and a
    real test result whose workspace fingerprint still matches what is on disk. This session
    has that evidence, so it is the one that lists at 100%.
    """
    ws = workspace / SESSION_ID
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "pom.xml").write_text("<project/>", encoding="utf-8")
    _make_session(
        SESSION_ID,
        status=SessionStatus.COMPLETED,
        phase=SessionPhase.VERIFIED,
        verification_metrics_json=json.dumps({
            "totalTests": 3,
            "passedTests": 3,
            "failedTests": 0,
            "allPassed": True,
            "fallback_used": False,
            "workspaceFingerprint": workspace_fingerprint(ws),
        }),
    )

    items = asyncio.run(rs.list_sessions(limit=10))

    listed = next(i for i in items if i.session_id == SESSION_ID)
    assert listed.completion_percentage == 100.0


def test_a_session_with_no_artifacts_is_listed_at_zero_percent(workspace):
    _make_session(SESSION_ID)

    items = asyncio.run(rs.list_sessions(limit=10))

    listed = next(i for i in items if i.session_id == SESSION_ID)
    assert listed.completion_percentage == 0.0


def test_listing_sessions_never_mutates_the_session_row(workspace):
    """The list used to promote a run whose lifecycle reached 100%; a read must not write.

    ``list_sessions`` used to set ``status = COMPLETED`` and ``current_lifecycle_phase =
    "COMPLETED"`` whenever the derived lifecycle hit 100%. Execution status is now owned by
    the writers (the pipeline and its finalisers) and the read endpoint only reports:
    "Reading progress must never mutate execution status". This session's artifacts build
    phases 1-4, but phase 5 is unverified without current evidence and phase 7 is not a
    HEALTHY deployment, so the derived figure is 4/7 and both stored fields stay untouched.
    """
    _make_session(
        SESSION_ID,
        status=SessionStatus.RUNNING,
        phase=SessionPhase.SANDBOX_BUILD,
        current_lifecycle_phase="SANDBOX_BUILD",
    )
    ws = workspace / SESSION_ID
    (ws / "src" / "main" / "java").mkdir(parents=True, exist_ok=True)
    (ws / "spec.md").write_text("# Spec", encoding="utf-8")
    (ws / "user_stories.json").write_text("[]", encoding="utf-8")
    (ws / "architecture.json").write_text("{}", encoding="utf-8")
    (ws / "schema.sql").write_text("CREATE TABLE t (id SERIAL);", encoding="utf-8")
    (ws / "pom.xml").write_text("<project/>", encoding="utf-8")
    (ws / "src" / "main" / "java" / "GlobalExceptionHandler.java").write_text(
        "@RestControllerAdvice class G {}", encoding="utf-8"
    )
    (ws / "docker-compose.yml").write_text("services: {}", encoding="utf-8")

    items = asyncio.run(rs.list_sessions(limit=10))

    listed = next(i for i in items if i.session_id == SESSION_ID)
    assert listed.completion_percentage == round(4 / 7 * 100.0, 1)
    assert listed.status == SessionStatus.RUNNING
    row = _row(SESSION_ID)
    assert row.status == SessionStatus.RUNNING, "reading the list mutated the execution status"
    assert row.current_lifecycle_phase == "SANDBOX_BUILD"


def test_a_failing_lifecycle_calculation_does_not_break_the_session_list(workspace, monkeypatch):
    """One unreadable session must not blank the whole index screen."""
    _make_session(SESSION_ID)

    def explode(session_id):
        raise RuntimeError("lifecycle unavailable")

    monkeypatch.setattr(lifecycle, "get_session_lifecycle", explode)

    items = asyncio.run(rs.list_sessions(limit=10))

    listed = next(i for i in items if i.session_id == SESSION_ID)
    assert listed.completion_percentage == 0.0


def test_the_limit_is_respected(workspace):
    for index in range(3):
        _make_session(f"qe-limit-{index}")

    items = asyncio.run(rs.list_sessions(limit=2))

    assert len(items) == 2


# ---------------------------------------------------------------------------
# quick_start_session
# ---------------------------------------------------------------------------
def test_quick_start_creates_a_requirements_session_without_running_it(workspace):
    payload = QuickStartSessionRequest(rawText="un servicio de pedidos", serviceName="orders")

    response = asyncio.run(rs.quick_start_session(payload))

    assert response.spec_name == "orders"
    assert response.status == SessionStatus.QUEUED
    assert response.lifecycle_mode == "GUIDED_STEP"
    assert response.pipeline_started is False, "autoRun was not requested"

    row = _row(response.session_id)
    assert row is not None
    assert row.current_lifecycle_phase == "REQUIREMENTS"


def test_quick_start_writes_the_prompt_into_the_workspace_spec(workspace):
    """The prompt is the only input the later stages get; losing it silently yields an
    empty specification that still looks like a successful quick start."""
    payload = QuickStartSessionRequest(rawText="un servicio de pedidos", serviceName="orders")

    response = asyncio.run(rs.quick_start_session(payload))

    spec = (workspace / response.session_id / "spec.md").read_text(encoding="utf-8")
    assert "orders" in spec
    assert "un servicio de pedidos" in spec


def test_quick_start_accepts_prompt_as_an_alias_and_sets_auto_pilot(workspace, monkeypatch):
    started = []
    monkeypatch.setattr(
        "app.services.pipeline_runner.run_pipeline",
        lambda session_id, **kwargs: started.append(session_id),
    )

    response = asyncio.run(
        rs.quick_start_session(QuickStartSessionRequest(prompt="pedidos", autoRun=True))
    )

    assert response.lifecycle_mode == "AUTO_PILOT"
    assert response.pipeline_started is True
    assert started == [response.session_id]


def test_quick_start_without_a_name_uses_a_stable_default(workspace):
    response = asyncio.run(rs.quick_start_session(QuickStartSessionRequest(rawText="algo")))

    assert response.spec_name == "app-service"


def test_quick_start_with_an_empty_name_falls_back_to_the_default(workspace):
    """Whitespace is not a name; ``.strip()`` must happen before the emptiness check."""
    response = asyncio.run(
        rs.quick_start_session(QuickStartSessionRequest(serviceName="   "))
    )

    assert response.spec_name == "app-service"


def test_quick_start_without_any_text_writes_no_spec_file(workspace):
    """An empty prompt must not leave a mislead   ing stub spec behind."""
    response = asyncio.run(rs.quick_start_session(QuickStartSessionRequest(serviceName="orders")))

    assert not (workspace / response.session_id / "spec.md").exists()


# ---------------------------------------------------------------------------
# get_session_by_id / cancel_session
# ---------------------------------------------------------------------------
def test_reading_an_unknown_session_is_a_404(workspace):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(rs.get_session_by_id("qe-absent"))

    assert excinfo.value.status_code == 404


def test_reading_a_session_surfaces_the_persisted_fallback_flag(workspace):
    """Feature 012's guarantee: the marking survives a process restart because it is a column."""
    _make_session(
        SESSION_ID,
        status=SessionStatus.COMPLETED,
        phase=SessionPhase.VERIFIED,
        verification_metrics_json=json.dumps({"fallback_used": True, "fallback_reason": "offline"}),
    )

    detail = asyncio.run(rs.get_session_by_id(SESSION_ID))

    assert detail.verification_fallback_used is True


def test_reading_a_session_without_metrics_reports_no_fallback(workspace):
    _make_session(SESSION_ID)

    detail = asyncio.run(rs.get_session_by_id(SESSION_ID))

    assert detail.verification_fallback_used is False


def test_cancelling_an_unknown_session_is_a_404(workspace):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(rs.cancel_session("qe-absent"))

    assert excinfo.value.status_code == 404


def test_cancelling_a_session_marks_it_cancelled_and_frees_its_slot(workspace, monkeypatch):
    """A cancelled session must not keep a place in the queue, nor ever claim a worker.

    Cancelling no longer reaches for ``release_slot``: an active worker releases its own
    slot in its ``finally`` when the cancellation signal unwinds it, and a *waiting*
    session is taken out of the queue by ``cancel_waiting`` and marked cancelled so
    ``acquire_slot`` refuses it. A real queue manager is used here so both halves of that
    contract are exercised rather than a mock call being asserted.
    """
    from app.services.queue_service import ConcurrencyQueueManager

    _make_session(SESSION_ID, status=SessionStatus.RUNNING)
    queue_manager = ConcurrencyQueueManager(max_concurrent=1)
    monkeypatch.setattr(rs, "queue_manager", queue_manager)
    asyncio.run(queue_manager.enqueue(SESSION_ID))
    assert SESSION_ID in queue_manager.waiting_queue

    asyncio.run(rs.cancel_session(SESSION_ID))

    assert _row(SESSION_ID).status == SessionStatus.CANCELLED
    assert SESSION_ID not in queue_manager.waiting_queue, (
        "a cancelled session must not hold a worker slot"
    )
    assert asyncio.run(queue_manager.acquire_slot(SESSION_ID)) is False, (
        "a cancelled session claimed a worker slot"
    )


# ---------------------------------------------------------------------------
# execute_generation_pipeline -- the outcome paths
# ---------------------------------------------------------------------------
def _blocking_stubs(monkeypatch, steps, diagnostics_calls=None):
    """Neutralise the queue, the mode decision and the diagnostics writer."""
    async def acquire(session_id):
        # ``acquire_slot`` answers whether the worker got a slot; the pipeline now
        # returns early when it does not. ``None`` is a refusal, not "no answer".
        return True

    async def release(session_id):
        return None

    monkeypatch.setattr(rs.queue_manager, "acquire_slot", acquire)
    monkeypatch.setattr(rs.queue_manager, "release_slot", release)
    monkeypatch.setattr(rs, "select_generation_mode", lambda *a, **k: _Mode())
    monkeypatch.setattr(rs, "generation_graph", _FakeGraph(steps=steps))
    if diagnostics_calls is not None:
        monkeypatch.setattr(
            rs,
            "record_session_diagnostics",
            lambda session_id, state, **kw: diagnostics_calls.append(session_id) or True,
        )


def test_a_completed_run_records_verified_and_reports_the_substituted_verification(workspace, monkeypatch):
    """The terminal event is the only proof a watcher gets. It must carry the fallback flag.

    A session can reach VERIFIED on a synthetic sandbox result under permissive mode; the
    completion event has to say so, or the UI reports an unverified build as verified.
    """
    _make_session(SESSION_ID)
    diagnostics = []
    _blocking_stubs(
        monkeypatch,
        [
            {"sandbox": {"logs": ["[INFO] BUILD SUCCESS"], "build_success": True,
                         "test_metrics": {"fallback_used": True, "fallback_reason": "image missing"},
                         "status": "COMPLETED"}},
        ],
        diagnostics,
    )

    asyncio.run(
        rs.execute_generation_pipeline(SESSION_ID, "spec-qe", "OrderService", {"serviceName": "x"})
    )

    row = _row(SESSION_ID)
    assert row.status == SessionStatus.COMPLETED
    assert row.phase == SessionPhase.VERIFIED
    assert diagnostics == [SESSION_ID], "a completed session must be diagnosed"
    assert rs._verification_fallback_used(row) is True

    completed = _payload(SESSION_ID, "session_completed")
    assert completed["verificationFallbackUsed"] is True
    assert completed["fallbackReason"] == "image missing"
    assert completed["downloadUrl"].endswith("/export")


def test_a_completed_run_with_a_real_verification_reports_no_fallback(workspace, monkeypatch):
    """The flag must be a *measurement*, not a constant. The negative case is the one that
    catches a flag hardcoded to True."""
    _make_session(SESSION_ID)
    _blocking_stubs(
        monkeypatch,
        [{"sandbox": {"logs": [], "build_success": True,
                      "test_metrics": {"fallback_used": False, "totalTests": 9, "passedTests": 9},
                      "status": "COMPLETED"}}],
    )

    asyncio.run(rs.execute_generation_pipeline(SESSION_ID, "spec-qe", "OrderService", {}))

    completed = _payload(SESSION_ID, "session_completed")
    assert completed["verificationFallbackUsed"] is False
    assert completed["totalTests"] == 9
    assert completed["passedTests"] == 9


def test_the_pipeline_streams_phase_transitions_logs_and_verification(workspace, monkeypatch):
    """Every event the monitor screen renders is produced here, in one pass.

    The node outputs below are **cumulative** on ``logs``, which is the real contract:
    every node does ``logs = state.get("logs", [])``, appends, and returns the same list,
    so ``accumulated_state.update`` sees the whole history each step. The streamer keeps a
    ``last_log_count`` cursor, and that cursor is only correct against a cumulative list --
    a node returning just its own new lines would silently drop every line after the first.
    """
    _make_session(SESSION_ID)
    _blocking_stubs(
        monkeypatch,
        [
            {"scaffolder": {"logs": ["scaffolding"]}},
            {"domain": {"logs": ["scaffolding", "domain model"]}},
            {"sandbox": {"logs": ["scaffolding", "domain model", "build"], "build_success": True,
                         "test_metrics": {"fallback_used": False}}},
            {"repair": {"logs": ["scaffolding", "domain model", "build", "repairing"],
                        "diff_summary": "Order.java: +2 -1", "repair_attempts": 1,
                        "status": "COMPLETED"}},
        ],
    )

    asyncio.run(rs.execute_generation_pipeline(SESSION_ID, "spec-qe", "OrderService", {}))

    types = _events(SESSION_ID)
    assert types.count("phase_transition") >= 4
    assert types.count("build_log") == 4
    assert "verification_result" in types
    assert "repair_iteration" in types
    assert "session_completed" in types

    transitions = [
        json.loads(e["data"])["currentPhase"]
        for e in rs.SESSION_EVENT_HISTORY[SESSION_ID]
        if e["event"] == "phase_transition"
    ]
    for expected in ("SCAFFOLDING", "CODE_GENERATION", "SANDBOX_BUILD", "SELF_REPAIR_LOOP"):
        assert expected in transitions

    repair = _payload(SESSION_ID, "repair_iteration")
    assert repair["iterationNumber"] == 1
    assert repair["diffSummary"] == "Order.java: +2 -1"
    assert repair["status"] == "REPAIRING"


def test_the_test_node_announces_test_synthesis(workspace, monkeypatch):
    """Each node maps to its own phase label; the monitor screen renders that mapping.

    ``test`` is the one node whose phase (TEST_SYNTHESIS) has no other producer, so a
    missing branch would leave the UI showing CODE_GENERATION for the whole test step.
    """
    _make_session(SESSION_ID)
    _blocking_stubs(monkeypatch, [{"test": {"logs": [], "status": "COMPLETED"}}])

    asyncio.run(rs.execute_generation_pipeline(SESSION_ID, "spec-qe", "OrderService", {}))

    transitions = [
        json.loads(e["data"])["currentPhase"]
        for e in rs.SESSION_EVENT_HISTORY[SESSION_ID]
        if e["event"] == "phase_transition"
    ]
    assert "TEST_SYNTHESIS" in transitions


def test_a_repair_beyond_the_limit_is_reported_as_blocked(workspace, monkeypatch):
    """Principle V visible in the stream: the last allowed attempt says BLOCKED, not REPAIRING."""
    _make_session(SESSION_ID)
    monkeypatch.setattr(rs.settings, "MAX_REPAIR_ATTEMPTS", 3)
    _blocking_stubs(
        monkeypatch,
        [{"repair": {"logs": [], "repair_attempts": 3, "status": "BLOCKED"}}],
    )

    asyncio.run(rs.execute_generation_pipeline(SESSION_ID, "spec-qe", "OrderService", {}))

    assert _payload(SESSION_ID, "repair_iteration")["status"] == "BLOCKED"


def test_a_blocked_run_is_persisted_and_diagnosed(workspace, monkeypatch):
    """A blocked session is the one most worth diagnosing; it must not be the path that skips it."""
    _make_session(SESSION_ID)
    diagnostics = []
    _blocking_stubs(
        monkeypatch,
        [{"sandbox": {"logs": [], "error": "tests failed", "status": "BLOCKED"}}],
        diagnostics,
    )

    asyncio.run(rs.execute_generation_pipeline(SESSION_ID, "spec-qe", "OrderService", {}))

    row = _row(SESSION_ID)
    assert row.status == SessionStatus.BLOCKED
    assert row.phase == SessionPhase.FAILED
    assert diagnostics == [SESSION_ID], "a blocked session must be diagnosed"

    blocked = _payload(SESSION_ID, "session_blocked")
    assert blocked["status"] == "BLOCKED"
    assert blocked["failureReason"] == "tests failed"


def test_a_crash_inside_the_graph_still_terminates_the_session(workspace, monkeypatch):
    """Without the outer handler the row stays RUNNING forever and the UI polls a dead session."""
    _make_session(SESSION_ID)
    diagnostics = []
    _blocking_stubs(monkeypatch, [], diagnostics)
    monkeypatch.setattr(rs, "generation_graph", _FakeGraph(explode=RuntimeError("graph exploded")))

    asyncio.run(rs.execute_generation_pipeline(SESSION_ID, "spec-qe", "OrderService", {}))

    row = _row(SESSION_ID)
    assert row.status == SessionStatus.BLOCKED
    assert "graph exploded" in row.error_message
    assert diagnostics == [], "a crashed run has no final state to diagnose"
    assert _payload(SESSION_ID, "session_blocked")["failureReason"] == "graph exploded"


def test_the_instruction_revision_is_recorded_when_the_set_loads(workspace, monkeypatch):
    class _InstructionSet:
        revision = "rev-42"

    monkeypatch.setattr(
        "app.orchestrator.stages.instructions.load_instruction_set",
        lambda: _InstructionSet(),
    )
    _make_session(SESSION_ID)
    _blocking_stubs(monkeypatch, [])

    asyncio.run(rs.execute_generation_pipeline(SESSION_ID, "spec-qe", "OrderService", {}))

    assert rs.SESSION_GENERATION_STATE[SESSION_ID]["instruction_set_revision"] == "rev-42"


def test_an_unloadable_instruction_set_does_not_break_the_offline_path(workspace, monkeypatch):
    """Deterministic sessions never read instructions, so a broken set must not fail them."""
    def explode():
        raise FileNotFoundError("no instruction set installed")

    monkeypatch.setattr("app.orchestrator.stages.instructions.load_instruction_set", explode)
    _make_session(SESSION_ID)
    _blocking_stubs(monkeypatch, [{"scaffolder": {"logs": [], "status": "COMPLETED"}}])

    asyncio.run(rs.execute_generation_pipeline(SESSION_ID, "spec-qe", "OrderService", {}))

    assert rs.SESSION_GENERATION_STATE[SESSION_ID]["instruction_set_revision"] == ""
    assert _row(SESSION_ID).status == SessionStatus.COMPLETED


def test_the_worker_slot_is_released_even_when_the_run_crashes(workspace, monkeypatch):
    """A leaked slot shrinks the queue's capacity for the life of the process."""
    _make_session(SESSION_ID)
    released = []

    async def acquire(session_id):
        return True

    async def release(session_id):
        released.append(session_id)

    monkeypatch.setattr(rs.queue_manager, "acquire_slot", acquire)
    monkeypatch.setattr(rs.queue_manager, "release_slot", release)
    monkeypatch.setattr(rs, "select_generation_mode", lambda *a, **k: _Mode())
    monkeypatch.setattr(rs, "generation_graph", _FakeGraph(explode=RuntimeError("boom")))

    asyncio.run(rs.execute_generation_pipeline(SESSION_ID, "spec-qe", "OrderService", {}))

    assert released == [SESSION_ID]


def test_the_generation_state_is_kept_for_inspection(workspace, monkeypatch):
    """``SESSION_GENERATION_STATE`` is what the step-by-step UI reads back."""
    _make_session(SESSION_ID)
    _blocking_stubs(monkeypatch, [{"scaffolder": {"logs": [], "status": "COMPLETED"}}])

    asyncio.run(rs.execute_generation_pipeline(SESSION_ID, "spec-qe", "OrderService", {}))

    assert rs.SESSION_GENERATION_STATE[SESSION_ID]["status"] == "COMPLETED"
    assert rs.SESSION_GENERATION_STATE[SESSION_ID]["session_id"] == SESSION_ID


# ---------------------------------------------------------------------------
