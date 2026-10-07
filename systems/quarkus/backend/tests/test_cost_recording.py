"""Cost recording tests (feature 013).

T001 wrote the first test in this file **before** any of the recording
implementation existed, so that every later task is checked against a recorded
value rather than an absence. It is the red anchor for the feature.

The test that matters most here is
``test_a_call_through_the_stage_boundary_is_recorded_end_to_end``. It drives a
call **through the real stage boundary** rather than through a hand-built
recording context. Without that case, the seam wiring could be deleted and the
whole suite would stay green while production recorded nothing.

No test in this file makes a network call (Constitution Principle VI). The fake
client is injected by patching the provider class the factory instantiates, so
the **real** factory runs, establishes the recording wrapper, and records.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.orchestrator.stages import journal as journal_mod  # noqa: E402
from app.orchestrator.stages.runner import run_stage  # noqa: E402
from app.services.llm_factory import LLMFactory  # noqa: E402
from tests.fixtures import fake_model as fm  # noqa: E402

CORPUS_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "baseline_blueprints"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _blueprint(name: str = "minimal") -> dict:
    return json.loads((CORPUS_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _model_state(workspace: Path, session_id: str, **extra) -> dict:
    state = {
        "session_id": session_id,
        "blueprint": _blueprint(),
        "workspace_path": str(workspace),
        "generated_files": {},
        "logs": [],
        "generation_mode": journal_mod.GENERATION_MODE_MODEL,
        "llm_provider": "deepseek",
        "llm_model": "deepseek-flash",
        "llm_api_key": "sk-fake-key-for-tests",
        "instruction_set_revision": "cost-tracing-test",
    }
    state.update(extra)
    return state


@pytest.fixture
def cost_store(tmp_path, monkeypatch):
    """Point the cost store at a throwaway file for the duration of one test."""
    store_path = tmp_path / "cost_store.db"
    monkeypatch.setattr(settings, "COST_STORE_PATH", str(store_path), raising=False)
    return store_path


def _inject_fake_through_the_real_factory(monkeypatch, model) -> None:
    """Make the **real** ``LLMFactory.get_chat_model`` return ``model``.

    Patching the provider class rather than ``LLMFactory.get_chat_model`` is
    deliberate: the recording wrapper is applied inside the factory, so a test
    that replaced the factory wholesale would bypass it and could never prove the
    end-to-end path.
    """
    import langchain_openai

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", lambda **kwargs: model)


def _read_calls(session_id: str) -> list:
    from app.cost.store import read_call_records
    return read_call_records(session_id)


def _read_session_record(session_id: str):
    from app.cost.store import read_session_cost_record
    return read_session_cost_record(session_id)


# ===========================================================================
# T001 — the red anchor: end-to-end recording through the stage boundary
# ===========================================================================
def test_a_call_through_the_stage_boundary_is_recorded_end_to_end(monkeypatch, tmp_path, cost_store):
    """T001's anchor. Fails until the recording wrapper and the store exist.

    This is the ONLY end-to-end case that exercises the real seam. It is what
    makes a silent production bypass visible: if the context wiring is removed,
    no call is recorded and this test — not merely a unit test of the wrapper —
    goes red.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    session_id = "t001-e2e"

    model = fm.make_usage_reporting_model(
        fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", _blueprint())),
        input_tokens=1200,
        output_tokens=340,
        cache_hit_input_tokens=200,
    )
    _inject_fake_through_the_real_factory(monkeypatch, model)

    run_stage(_model_state(workspace, session_id), "DOMAIN")

    records = _read_calls(session_id)
    assert records, (
        "no call was recorded end to end. Either the recording wrapper is not "
        "applied, or the stage boundary does not establish the recording context."
    )
    assert len(records) == 1
    record = records[0]
    assert record["session_id"] == session_id
    assert record["stage"] == "DOMAIN"
    assert record["provider"] == "deepseek"
    assert record["model"] == "deepseek-flash"
    assert record["input_tokens"] == 1200, "the recorded input token count is wrong"
    assert record["output_tokens"] == 340
    assert record["latency_ms"] >= 0
    assert record["usage_known"] is True
    assert record["priced"] is True
    assert record["cost_usd"] is not None and record["cost_usd"] > 0


# ===========================================================================
# T014 — per-call recording
# ===========================================================================
def test_the_fake_still_reports_no_usage_by_default():
    """The extension is additive: the default response reports nothing.

    This is what keeps the existing suite on the unknown-usage path, and it is why
    a usage-reporting double had to be added for the token path to be testable.
    """
    plain = fm.make_scripted_model("hello")
    assert plain.usage_metadata is None
    assert plain.invoke("x").usage_metadata is None
    reporting = fm.make_usage_reporting_model("hello", input_tokens=10, output_tokens=5)
    assert reporting.invoke("x").usage_metadata["input_tokens"] == 10


def test_every_invocation_is_recorded_including_a_correction(monkeypatch, tmp_path, cost_store):
    """One record per call, and a retry is a real call that really cost money."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    blueprint = _blueprint()
    violating = fm.violating_artifacts("PROHIBITED_ANNOTATION", blueprint)
    compliant = fm.compliant_artifacts("DOMAIN", blueprint)

    model = fm.make_usage_reporting_model(
        fm.canonical_json_response(violating),
        fm.canonical_json_response(compliant),
        input_tokens=800, output_tokens=200,
    )
    _inject_fake_through_the_real_factory(monkeypatch, model)

    run_stage(_model_state(workspace, "t014-correction"), "DOMAIN")

    records = _read_calls("t014-correction")
    assert len(records) == 2, "the correction attempt was not recorded as a separate call"
    assert model.call_count == 2
    for record in records:
        assert record["input_tokens"] == 800
        assert record["output_tokens"] == 200
        assert record["cost_usd"] is not None


def test_required_fields_are_present(monkeypatch, tmp_path, cost_store):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    model = fm.make_usage_reporting_model(
        fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", _blueprint())),
        input_tokens=1200, output_tokens=340, cache_hit_input_tokens=200,
    )
    _inject_fake_through_the_real_factory(monkeypatch, model)

    run_stage(_model_state(workspace, "t014-fields"), "DOMAIN")

    record = _read_calls("t014-fields")[0]
    for field in ("call_id", "session_id", "stage", "provider", "model", "timestamp",
                  "latency_ms", "input_tokens", "output_tokens", "usage_known",
                  "cache_basis_known", "peak", "priced", "cost_usd", "pricing_basis"):
        assert field in record, f"the call record is missing {field}"
    assert record["stage"] == "DOMAIN"
    assert record["session_id"] == "t014-fields"


def test_unknown_usage_is_recorded_not_dropped_and_not_zero(monkeypatch, tmp_path, cost_store):
    """A response reporting no usage yields a record, explicitly marked."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    # make_scripted_model reports NO usage -- the default fixture.
    model = fm.make_scripted_model(
        fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", _blueprint()))
    )
    _inject_fake_through_the_real_factory(monkeypatch, model)

    run_stage(_model_state(workspace, "t014-unknown"), "DOMAIN")

    records = _read_calls("t014-unknown")
    assert records, "an unknown-usage call was dropped entirely"
    record = records[0]
    assert record["usage_known"] is False
    assert record["input_tokens"] is None, "unknown usage was recorded as a zero token count"
    assert record["output_tokens"] is None
    assert record["cost_usd"] is None, "unknown usage produced a cost of zero"


def test_a_deterministic_session_records_nothing(monkeypatch, tmp_path, cost_store):
    """An offline session is not a zero-cost model session."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    state = _model_state(workspace, "t014-offline")
    state["generation_mode"] = journal_mod.GENERATION_MODE_DETERMINISTIC

    run_stage(state, "DOMAIN")

    assert _read_calls("t014-offline") == [], (
        "a deterministic session recorded model calls it never made"
    )


def test_no_credential_is_recorded(monkeypatch, tmp_path, cost_store):
    """The wrapper sits directly beside the API key -- the easiest place to leak it."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    secret = "sk-t014-must-not-leak-0000000000"
    model = fm.make_usage_reporting_model(
        fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", _blueprint())),
        input_tokens=100, output_tokens=50,
    )
    _inject_fake_through_the_real_factory(monkeypatch, model)

    run_stage(_model_state(workspace, "t014-cred", llm_api_key=secret), "DOMAIN")

    serialized = json.dumps(_read_calls("t014-cred"))
    assert secret not in serialized, "the API key reached the cost record"
    assert secret not in json.dumps(_read_session_record.__doc__ or "")


# ===========================================================================
# T015 — async on a sync-only client (SC-010)
# ===========================================================================
@pytest.mark.anyio
async def test_ainvoke_on_a_sync_only_client_is_recorded(monkeypatch, tmp_path, cost_store):
    """The fake implements only ``invoke``; calling async through the wrapper must
    not raise, and must still RECORD.

    Asserting only "does not raise" would let the delegated recording silently
    disappear, which is a second form of the silent-spend problem this feature
    closes. So both halves are asserted.
    """
    from app.cost.recording import RecordingChatClient

    model = fm.make_usage_reporting_model("hello", input_tokens=700, output_tokens=140)
    assert not hasattr(model, "ainvoke"), "the fixture now has ainvoke; this test is moot"

    from app.cost import recording
    with recording.recording_context("t015", "DOMAIN"):
        wrapped = LLMFactory._maybe_wrap(model, "deepseek", "deepseek-flash")
        assert isinstance(wrapped, RecordingChatClient), "the wrapper was not applied"
        response = await wrapped.ainvoke("prompt")

    assert response.content == "hello"
    records = _read_calls("t015")
    assert len(records) == 1, (
        "the async call on a sync-only client was not recorded -- a silent pass-through"
    )
    assert records[0]["input_tokens"] == 700
    assert records[0]["output_tokens"] == 140
    assert records[0]["stage"] == "DOMAIN"
    assert records[0]["session_id"] == "t015"


@pytest.mark.anyio
async def test_ainvoke_delegates_to_the_sync_entry_point(monkeypatch, tmp_path, cost_store):
    """The documented behaviour: the sync implementation actually runs."""
    model = fm.make_scripted_model("delegated")
    from app.cost import recording
    with recording.recording_context("t015b", "DOMAIN"):
        wrapped = LLMFactory._maybe_wrap(model, "deepseek", "deepseek-flash")
        await wrapped.ainvoke("payload")

    assert model.calls == ["payload"], "the async call did not reach the sync implementation"


# ===========================================================================
# T021 — SC-001's literal form: ten real DeepSeek sessions
# ===========================================================================
REAL_COST_ENV = "AGENTIA_RUN_REAL_COST_TRACING"


def test_ten_real_sessions_produce_priced_records(monkeypatch, tmp_path, cost_store):
    """Ten sessions against the real provider produce records with non-zero tokens.

    **Opt-in and gated**, because this is the only test in the feature that spends
    money and makes a live provider call (Constitution Principle VI forbids it in
    the default suite).

    It uses the REAL factory with no patching, so the whole path is exercised:
    stage boundary -> context -> factory -> wrapper -> provider -> store.

    If the key is absent, this skips, and SC-001's literal form is reported as
    **not verified** rather than inferred from the fake path — inferring it would
    be the same substitution feature 012 refused for its own success criterion.
    """
    import os

    if os.environ.get(REAL_COST_ENV) != "1":
        pytest.skip(f"set {REAL_COST_ENV}=1 and provide DEEPSEEK_API_KEY to spend real tokens")

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY is not set; a real measurement needs a real key")

    blueprint = _blueprint()
    scripted = fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", blueprint))

    for index in range(10):
        workspace = tmp_path / f"real-{index}"
        workspace.mkdir()
        session_id = f"real-{index:02d}"
        state = _model_state(workspace, session_id, llm_api_key=api_key)
        # The provider returns its own content; the fake only supplies the request
        # shape, so a real response is used here rather than a scripted one.
        run_stage(state, "DOMAIN")

        records = _read_calls(session_id)
        assert records, f"session {session_id} recorded no call"
        for record in records:
            assert record["usage_known"] is True, "the provider reported no usage"
            assert record["input_tokens"] > 0, "a real call recorded zero input tokens"
            assert record["output_tokens"] >= 0
            assert record["priced"] is True, (
                f"the model was absent from the pricing table: {record['model']}"
            )
            assert record["pricing_basis"] in (
                "peak/cache-aware", "off_peak/cache-aware",
                "peak/cache-miss-assumed", "off_peak/cache-miss-assumed",
            ), f"unexpected pricing basis: {record['pricing_basis']}"
            assert record["cost_usd"] is not None and record["cost_usd"] > 0

