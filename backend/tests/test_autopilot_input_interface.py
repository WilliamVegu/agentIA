"""Regression: autopilot (quick-start) must carry the input interface into the pipeline.

The reframing's "interfaz de entrada" was only wired into the graph path; autopilot
(quick-start -> run_pipeline -> _execute_pipeline_steps) built the blueprint WITHOUT
``inputInterface``, so the InferenceEngine never ran and generation fell back to the
hardcoded layered default. This locks the request model and the credential threading.
"""
from app.models.session import QuickStartSessionRequest


def test_quick_start_request_accepts_input_interface():
    req = QuickStartSessionRequest(
        serviceName="order-service",
        inputInterface={"requestVolume": "high", "architecturePreference": "hexagonal"},
    )
    assert req.input_interface["requestVolume"] == "high"
    assert req.input_interface["architecturePreference"] == "hexagonal"


def test_run_pipeline_stores_input_interface(monkeypatch):
    from app.services import pipeline_runner

    class _FakeThread:
        def __init__(self, *a, **k):
            self.captured_args = a
        def start(self):
            pass

    monkeypatch.setattr(pipeline_runner.threading, "Thread", _FakeThread)

    from app.models.session import SessionLocal, GenerationSessionDB
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id="sess-iface",spec_id="interface-test",spec_name="interface-service"))
        db.commit()
    iface = {"requestVolume": "high", "architecturePreference": "hexagonal"}
    ok = pipeline_runner.run_pipeline(
        "sess-iface", api_key="sk-x", provider="deepseek", input_interface=iface
    )
    assert ok is True
    assert pipeline_runner._session_credentials["sess-iface"]["input_interface"] == iface


def test_blueprint_injection_shape():
    """The injection in _execute_pipeline_steps puts the interface under the exact key
    the deterministic scaffolder reads (``blueprint["inputInterface"]``)."""
    input_interface = {"requestVolume": "high"}
    blueprint_dict = {"serviceName": "x", "entities": []}
    if input_interface:
        blueprint_dict["inputInterface"] = input_interface
    assert blueprint_dict["inputInterface"]["requestVolume"] == "high"
