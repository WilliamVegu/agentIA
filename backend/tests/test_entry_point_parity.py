"""Entry-point parity: both generation routes must reach the model (feature 011 follow-up).

The readiness report found ``POST /sessions`` building its state by calling
``select_generation_mode()`` **with no arguments**, and passing no ``llm_api_key``.
With no key and no provider that function returns DETERMINISTIC for every request,
so the route emitted offline templates while ``/quick-start`` emitted model output.

Nothing in either response distinguished them. Both are HTTP 202 with a session id,
and the two products differ completely -- which makes this exactly the class of
defect this repository keeps finding: not a crash, but a surface that reports the
wrong thing.

Two seams are asserted separately, because they fail independently:

1. the **route** must pass the caller's credentials to the worker, and
2. the **worker** must use them for the mode decision *and* place the key in the
   generation state, because ``run_stage`` builds the model client from
   ``state["llm_api_key"]``.

A session that decided MODEL and then failed every stage for want of a key would be
a worse failure than staying deterministic: it looks configured.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import app.api.routes_session as rs  # noqa: E402
from app.models.session import (  # noqa: E402
    GenerationSessionDB,
    SessionLocal,
    SessionPhase,
    SessionStatus,
)

SESSION_ID = "entry-point-parity"


class _Mode:
    mode = "deterministic"
    provider = "offline"
    model = "mock"
    reason = "test"


class _Blueprint:
    serviceName = "OrderService"

    def model_dump(self):
        return {"serviceName": "OrderService"}


class _CapturingGraph:
    """Records the initial state the entry point hands the graph."""

    def __init__(self):
        self.initial_state = None

    def stream(self, initial_state):
        self.initial_state = initial_state
        return iter([])


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(rs.settings, "WORKSPACE_DIR", str(tmp_path))
    return tmp_path


def _make_session(session_id):
    db = SessionLocal()
    try:
        db.add(
            GenerationSessionDB(
                id=session_id,
                spec_id="spec-parity",
                spec_name="OrderService",
                status=SessionStatus.QUEUED,
                phase=SessionPhase.INITIALIZATION,
                current_lifecycle_phase="INITIAL",
                lifecycle_mode="GUIDED_STEP",
                repair_attempts=0,
            )
        )
        db.commit()
    finally:
        db.close()


def test_create_session_hands_the_callers_credentials_to_the_worker(workspace, monkeypatch):
    """Seam 1: the route must pass the header credentials on to the worker.

    Without this the worker has nothing to decide with, and the mode decision
    inside it necessarily returns DETERMINISTIC.
    """
    captured = {}

    async def fake_worker(**kwargs):
        captured.update(kwargs)

    async def fake_enqueue(session_id):
        return 0

    monkeypatch.setattr(rs, "get_specification", lambda spec_id: _Blueprint())
    monkeypatch.setattr(rs, "execute_generation_pipeline", fake_worker)
    monkeypatch.setattr(rs.queue_manager, "enqueue", fake_enqueue)

    asyncio.run(
        rs.create_generation_session(
            payload=rs.CreateSessionRequest(specId="spec-1"),
            x_llm_api_key="sk-caller",
            x_llm_provider="deepseek",
        )
    )

    assert captured["api_key"] == "sk-caller", "the worker never received the key"
    assert captured["provider"] == "deepseek"


def test_the_worker_decides_the_mode_with_the_credentials_and_states_the_key(workspace, monkeypatch):
    """Seam 2: use the credentials, and put the key where ``run_stage`` reads it."""
    _make_session(SESSION_ID)
    seen = {}

    def spy_mode_decision(api_key=None, provider=None, model_name=None, **kwargs):
        seen.update(api_key=api_key, provider=provider)
        return _Mode()

    async def acquire(session_id):
        return True

    async def release(session_id):
        return None

    capturing = _CapturingGraph()
    monkeypatch.setattr(rs.queue_manager, "acquire_slot", acquire)
    monkeypatch.setattr(rs.queue_manager, "release_slot", release)
    monkeypatch.setattr(rs, "select_generation_mode", spy_mode_decision)
    monkeypatch.setattr(rs, "generation_graph", capturing)

    asyncio.run(
        rs.execute_generation_pipeline(
            SESSION_ID, "spec-parity", "OrderService", __import__("integration.reliability_fixtures",fromlist=["ledger_draft"]).ledger_draft(),
            api_key="sk-threaded", provider="deepseek",
        )
    )

    assert seen["api_key"] == "sk-threaded", "the mode decision ignored the caller's key"
    assert seen["provider"] == "deepseek"
    assert capturing.initial_state is not None
    assert capturing.initial_state["llm_api_key"] == "sk-threaded"
