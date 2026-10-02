"""MLflow LLM tracing.

The tracking UI's Traces page was empty and always had been. This module mirrors cost
records as MLflow *runs*, and a run is not a trace: a trace is a span tree of individual
calls, which requires instrumenting the calls. Nothing did, so nothing appeared, and an
operator reasonably read that as a broken mirror.
"""
import pytest


def test_a_second_enable_is_a_no_op(monkeypatch):
    """Autologging is process-wide, so the second call must short-circuit.

    It must not re-run `autolog()`. Re-running it is not free and, when the tracking target
    is not reachable from the current settings, it fails -- which would report tracing as
    off in a process where it is already on.
    """
    from app.cost import mlflow_sink

    monkeypatch.setattr(mlflow_sink, "_tracing_enabled", True)
    monkeypatch.setattr(
        mlflow_sink, "mlflow", None, raising=False
    )  # any re-import attempt would raise

    assert mlflow_sink.enable_tracing() is True
    assert mlflow_sink.tracing_enabled() is True


def test_a_failed_enable_says_why(monkeypatch):
    """An empty Traces page has to be explainable.

    When enabling cannot complete, the reason is recorded rather than swallowed: the whole
    complaint this addresses is a UI that showed nothing and said nothing.
    """
    from app.cost import mlflow_sink

    monkeypatch.setattr(mlflow_sink, "_tracing_enabled", False)
    monkeypatch.setattr(mlflow_sink, "_mirror_failures", [])
    monkeypatch.setattr(mlflow_sink, "settings", type("S", (), {
        "MLFLOW_TRACKING_URI": "http://127.0.0.1:1/not-a-server",
        "MLFLOW_EXPERIMENT": "agentia",
    })())

    assert mlflow_sink.enable_tracing() is False
    assert mlflow_sink.mirror_failures(), "a failure must be recorded with its reason"


def test_tracing_is_off_when_the_library_is_absent(monkeypatch):
    """Telemetry must never be a precondition for generating code.

    An absent library has to degrade to False, not to an exception at import -- which
    would take the API down for a feature that only draws charts.
    """
    import builtins
    import sys

    from app.cost import mlflow_sink

    monkeypatch.setattr(mlflow_sink, "_tracing_enabled", False)
    real_import = builtins.__import__

    def refuse(name, *args, **kwargs):
        if name == "mlflow" or name.startswith("mlflow."):
            raise ImportError("no mlflow on this host")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse)
    monkeypatch.delitem(sys.modules, "mlflow", raising=False)

    assert mlflow_sink.enable_tracing() is False
    assert mlflow_sink.tracing_enabled() is False
    assert any("unavailable" in f for f in mlflow_sink.mirror_failures()), (
        "a refused import must record why, so the empty Traces page is explainable"
    )


def test_health_reports_the_telemetry_state():
    """`/healthz` answers "why is Traces empty?" in one request."""
    from fastapi.testclient import TestClient

    from app.main import app

    body = TestClient(app).get("/healthz").json()

    assert body["status"] == "UP"
    assert "mlflow" in body
    assert set(body["mlflow"]) == {"tracing", "failures"}
    assert isinstance(body["mlflow"]["tracing"], bool)
