"""The telemetry mirror's absence must be a non-event (feature 013, FR-005).

``cost/mlflow_sink.py`` mirrors each recorded call to a telemetry destination. It
is deliberately **not** on any critical path: ``backend/cost_tracking.db`` is the
system of record, and the report reads only that. The property these tests pin
down is the one that makes the destination optional *by construction* rather than
by luck:

* a missing library, an unreachable server, or a rejected write must **not**
  raise into a generation session;
* the local store must be written **regardless**, so a telemetry outage never
  costs data;
* a credential must never be forwarded, because the recording site sits directly
  beside the API key.

On this host ``mlflow`` is not installed at all, so the absent path is not a
hypothetical — it is the one that actually runs. The tests simulate absence
explicitly anyway, so they keep testing it on a host where it *is* installed.

No provider calls, no network.
"""

from __future__ import annotations

import os
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.cost import mlflow_sink, recording  # noqa: E402
from tests.fixtures import fake_model as fm  # noqa: E402


@pytest.fixture
def without_the_library(monkeypatch):
    """Make ``import mlflow`` fail, whatever this host actually has installed."""
    # The documented way to simulate an absent module: a None entry in
    # sys.modules makes the import raise ImportError deterministically.
    monkeypatch.setitem(sys.modules, "mlflow", None)
    mlflow_sink._reset_failures()
    yield
    mlflow_sink._reset_failures()


@pytest.fixture
def cost_store(tmp_path, monkeypatch):
    """Point the system of record at a throwaway file for one test."""
    store_path = tmp_path / "cost_store.db"
    monkeypatch.setattr(settings, "COST_STORE_PATH", str(store_path), raising=False)
    return store_path


# ---------------------------------------------------------------------------
# Absence is a non-event
# ---------------------------------------------------------------------------
def test_the_absent_library_returns_false_and_does_not_raise(without_the_library):
    result = mlflow_sink.mirror_call_record(
        {"call_id": "c1", "session_id": "t013-mirror", "input_tokens": 10}
    )

    assert result is False, "a skipped mirror must report that it was skipped"
    reasons = mlflow_sink.mirror_failures()
    assert reasons, "the skip was silent; a missing destination left no trace"
    assert "unavailable" in reasons[-1]


def test_a_mirror_that_raises_is_a_non_event(monkeypatch):
    """An unreachable or rejecting destination must not propagate either."""

    class _ExplodingMlflow(types.ModuleType):
        def set_experiment(self, name):
            self.experiment = name      # the mirror groups runs; the double records it

        def set_tracking_uri(self, uri):
            raise RuntimeError("connection refused")

    monkeypatch.setitem(sys.modules, "mlflow", _ExplodingMlflow("mlflow"))
    mlflow_sink._reset_failures()
    try:
        assert mlflow_sink.mirror_session_cost_record({"session_id": "t013-mirror"}) is False
        assert any("connection refused" in reason for reason in mlflow_sink.mirror_failures())
    finally:
        mlflow_sink._reset_failures()


def test_a_session_cost_record_is_mirrored_through_the_same_non_event_path(
    without_the_library,
):
    """Both mirror entry points share the behaviour; neither raises."""
    assert mlflow_sink.mirror_session_cost_record({"session_id": "t013-mirror"}) is False


# ---------------------------------------------------------------------------
# An unreachable destination must fail fast, not block the caller
# ---------------------------------------------------------------------------
def test_an_unreachable_destination_is_bounded_rather_than_left_at_the_library_default(
    monkeypatch,
):
    """The defect this pins: "best-effort" that blocks for minutes is not best-effort.

    MLflow's defaults are a 120-second HTTP timeout with up to 5 retries, and the mirror
    is called from ``RecordingChatClient.invoke`` -- the critical path of every LLM call.
    A dead tracking server therefore stalled generation sessions, which is the opposite of
    the module's stated contract. With no operator override, the send must be bounded.
    """
    monkeypatch.delenv("MLFLOW_HTTP_REQUEST_TIMEOUT", raising=False)
    monkeypatch.delenv("MLFLOW_HTTP_REQUEST_MAX_RETRIES", raising=False)

    sent = {}

    class _RecordingMlflow(types.ModuleType):
        def set_experiment(self, name):
            self.experiment = name      # the mirror groups runs; the double records it

        def set_tracking_uri(self, uri):
            sent["uri"] = uri

        @contextmanager
        def start_run(self, run_name=None):
            # Read at the moment of the call, which is when MLflow itself reads them.
            sent["timeout"] = os.environ.get("MLFLOW_HTTP_REQUEST_TIMEOUT")
            sent["retries"] = os.environ.get("MLFLOW_HTTP_REQUEST_MAX_RETRIES")
            yield

        def log_metric(self, key, value):
            return None

        def set_tags(self, tags):
            return None

    monkeypatch.setitem(sys.modules, "mlflow", _RecordingMlflow("mlflow"))
    mlflow_sink._reset_failures()
    try:
        assert mlflow_sink.mirror_call_record({"session_id": "t013-bounded"}) is True
    finally:
        mlflow_sink._reset_failures()

    assert sent["retries"] == "0", "a dead destination must not be retried"
    assert int(sent["timeout"]) <= 10, "a dead destination must not hold the caller for long"


def test_an_operator_override_of_the_transport_bound_is_respected(monkeypatch):
    """``setdefault``, not assignment: a real deployment with a healthy server may want
    long retries, and the mirror must not silently overrule an explicit setting."""
    monkeypatch.setenv("MLFLOW_HTTP_REQUEST_TIMEOUT", "45")
    monkeypatch.setenv("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "3")

    from app.cost import mlflow_sink as sink

    sink._bound_the_transport()

    assert os.environ["MLFLOW_HTTP_REQUEST_TIMEOUT"] == "45"
    assert os.environ["MLFLOW_HTTP_REQUEST_MAX_RETRIES"] == "3"


# ---------------------------------------------------------------------------
# The system of record is unaffected
# ---------------------------------------------------------------------------
def test_the_local_store_is_written_even_when_the_mirror_is_absent(
    without_the_library, cost_store
):
    """A telemetry outage must not cost a record: the mirror runs *after* the write."""
    from app.cost.store import read_call_records

    response = fm.FakeResponse(
        content="ok",
        usage_metadata={"input_tokens": 1200, "output_tokens": 300},
    )

    with recording.recording_context("t013-mirror", "DOMAIN"):
        recording._record_call("deepseek", "deepseek-flash", 42.0, response)

    stored = read_call_records("t013-mirror")
    assert len(stored) == 1, (
        "the mirror's absence prevented the local store from being written; the "
        "destination is supposed to be optional, not load-bearing"
    )
    assert stored[0]["input_tokens"] == 1200
    assert stored[0]["output_tokens"] == 300
    # And the mirror really was consulted: its absence was recorded, not skipped
    # silently before the attempt.
    assert mlflow_sink.mirror_failures(), "the mirror was never attempted"


# ---------------------------------------------------------------------------
# A credential never reaches the destination
# ---------------------------------------------------------------------------
def test_the_mirror_never_forwards_a_credential(monkeypatch):
    """Identifiers only. The recording site sits directly beside the API key."""
    sent_metrics: list = []
    sent_tags: dict = {}

    class _CapturingMlflow(types.ModuleType):
        def set_experiment(self, name):
            self.experiment = name      # the mirror groups runs; the double records it

        def set_tracking_uri(self, uri):
            return None

        @contextmanager
        def start_run(self, run_name=None):
            yield

        def log_metric(self, key, value):
            sent_metrics.append((key, value))

        def set_tags(self, tags):
            sent_tags.update(tags)

    monkeypatch.setitem(sys.modules, "mlflow", _CapturingMlflow("mlflow"))

    forwarded = mlflow_sink.mirror_call_record({
        "call_id": "c1",
        "session_id": "t013-mirror",
        "stage": "DOMAIN",
        "provider": "deepseek",
        "model": "deepseek-flash",
        "latency_ms": 42,
        "input_tokens": 1200,
        # A credential-shaped field, exactly the kind that sits beside this code.
        "api_key": "sk-probe-must-never-be-forwarded",
        "llm_api_key": "sk-probe-must-never-be-forwarded",
    })

    assert forwarded is True, "the capturing destination was not reached"
    flattened = repr(sent_metrics) + repr(sent_tags)
    assert "sk-probe" not in flattened, (
        "a credential was forwarded to the telemetry destination"
    )
    assert sent_tags.get("session_id") == "t013-mirror"
    assert any(key == "input_tokens" for key, _ in sent_metrics)


class _RunHandle:
    """Minimal context manager for `with mlflow.start_run():`."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_mirror_groups_runs_in_a_named_experiment(monkeypatch):
    """Reported from the UI: "mlflow shows no input from project, only default".

    The data was all present (535 runs, $2.31) but every run landed in `Default`, so
    the experiment list showed one entry that looked empty of project content. The
    mirror now names its experiment, and `MLFLOW_EXPERIMENT` overrides it.
    """
    import sys
    import types

    from app.cost import mlflow_sink

    seen = {}

    class _Fake(types.ModuleType):
        def set_tracking_uri(self, uri):
            seen["uri"] = uri

        def set_experiment(self, name):
            seen["experiment"] = name

        def start_run(self, run_name=None):
            seen["run_name"] = run_name
            return _RunHandle()

        def log_metric(self, key, value):
            pass

        def set_tags(self, tags):
            seen.setdefault("tags", {}).update(tags)

    monkeypatch.setitem(sys.modules, "mlflow", _Fake("mlflow"))
    mlflow_sink._reset_failures()

    assert mlflow_sink.mirror_call_record({"session_id": "sess-1", "stage": "DOMAIN"}) is True
    assert seen["experiment"] == "agentia"
    assert seen["run_name"] == "sess-1-DOMAIN", (
        "a session's per-stage runs must be distinguishable by name"
    )


def test_the_experiment_name_is_configurable(monkeypatch):
    import sys
    import types

    from app.config import settings
    from app.cost import mlflow_sink

    seen = {}
    monkeypatch.setattr(settings, "MLFLOW_EXPERIMENT", "custom-exp")

    class _Fake(types.ModuleType):
        def set_tracking_uri(self, uri): pass
        def set_experiment(self, name): seen["experiment"] = name
        def start_run(self, run_name=None):
            return _RunHandle()
        def log_metric(self, key, value): pass
        def set_tags(self, tags): pass

    monkeypatch.setitem(sys.modules, "mlflow", _Fake("mlflow"))
    mlflow_sink._reset_failures()

    mlflow_sink.mirror_call_record({"session_id": "s"})
    assert seen["experiment"] == "custom-exp"
