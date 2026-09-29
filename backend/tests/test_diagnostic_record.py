"""The durable session diagnostic record (feature 015, US1).

Three requirements carry this file, and each closes a way the record could lie:

* **Determinism** — a record that drifts would let a later "improvement" be the
  instrument moving rather than the system.
* **Three states** — *evaluated and clean*, *evaluated with findings*, and *not
  evaluable* must never be conflated. An empty artifact set scores 100 with no
  findings, so unless it is flagged it is indistinguishable from success, and
  "nothing to evaluate" would be reported as "verified clean".
* **Exclusion of unverified sessions** — a build that fell back to a synthetic
  result must be marked, because counting it would reward changes that make
  verification less likely to run. This is the failure feature 012 exists for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.models.diagnostics import (  # noqa: E402
    read_diagnostic_record,
    read_diagnostic_records,
    write_diagnostic_record,
)
from app.models.session import SessionLocal, engine  # noqa: E402
from app.services.conformance_diagnostics import diagnose  # noqa: E402
from tests.fixtures import fake_model as fm  # noqa: E402

CORPUS_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "baseline_blueprints"
SESSION_IDS = ["t015-a", "t015-b", "t015-c", "t015-d", "t015-e"]


def _blueprint(name: str = "minimal") -> dict:
    return json.loads((CORPUS_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def clean_records():
    db = SessionLocal()
    try:
        from app.models.diagnostics import SessionDiagnosticRecord
        for sid in SESSION_IDS:
            db.query(SessionDiagnosticRecord).filter(
                SessionDiagnosticRecord.session_id == sid
            ).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        from app.models.diagnostics import SessionDiagnosticRecord
        for sid in SESSION_IDS:
            db.query(SessionDiagnosticRecord).filter(
                SessionDiagnosticRecord.session_id == sid
            ).delete()
        db.commit()
    finally:
        db.close()


def _write(session_id, report, **overrides):
    payload = dict(
        score=report.score,
        raw_penalty=report.raw_penalty,
        density=report.density,
        artifact_count=report.evaluated_artifact_count,
        evaluable=report.evaluable,
        counts_by_severity=report.counts_by_severity,
        rule_histogram=report.rule_histogram,
        findings=[v.to_dict() for v in report.violations],
    )
    payload.update(overrides)
    return write_diagnostic_record(session_id, **payload)


# ---------------------------------------------------------------------------
# T006 — the table is created on the engine actually in use
# ---------------------------------------------------------------------------
def test_a_write_succeeds_on_whatever_engine_the_session_is_bound_to():
    """Feature 014's run records were silently swallowed by getting this wrong:
    create_all bound the import-time engine, the suite rebound SessionLocal, and
    every write failed into a best-effort path that reported success."""
    report = diagnose(fm.compliant_artifacts("CONTROLLER", _blueprint()))

    assert _write("t015-a", report) is True, (
        "the write reported failure; the table was not created on the engine the "
        "session is actually bound to"
    )
    assert read_diagnostic_record("t015-a") is not None


# ---------------------------------------------------------------------------
# T007 — the record names the defect
# ---------------------------------------------------------------------------
def test_the_record_names_the_rule_the_artifact_and_the_severity():
    report = diagnose(fm.violating_artifacts("LAYER_ISOLATION", _blueprint()))
    _write("t015-a", report)

    record = read_diagnostic_record("t015-a")

    assert record["rule_histogram"], "the record carried no rule histogram"
    assert "PRINCIPLE_I_LAYER_ISOLATION" in record["rule_histogram"]
    findings = record["findings"]
    assert findings, "the record carried no findings"
    first = findings[0]
    for field in ("rule_id", "artifact_path", "severity"):
        assert first.get(field), f"a finding is missing {field}"


# ---------------------------------------------------------------------------
# T008 — determinism
# ---------------------------------------------------------------------------
def test_two_records_over_identical_artifacts_are_identical():
    blueprint = _blueprint()
    artifacts = fm.violating_artifacts("CONTRACT_IMMUTABILITY", blueprint)

    _write("t015-a", diagnose(artifacts))
    _write("t015-b", diagnose(artifacts))

    first = read_diagnostic_record("t015-a")
    second = read_diagnostic_record("t015-b")
    first.pop("session_id"), second.pop("session_id")
    first.pop("recorded_at"), second.pop("recorded_at")

    assert first == second, (
        "two records over byte-identical artifacts disagreed; a later improvement "
        "could not be told apart from the instrument drifting"
    )


# ---------------------------------------------------------------------------
# T009 — three states, never conflated
# ---------------------------------------------------------------------------
def test_nothing_to_evaluate_is_not_recorded_as_clean():
    report = diagnose({})

    assert report.evaluable is False, (
        "an artifact set with nothing in it reported as evaluable; an empty set "
        "scores 100 with no findings and would read as verified clean"
    )
    assert report.evaluated_artifact_count == 0


def test_a_clean_set_is_evaluable_and_scores_full():
    report = diagnose(fm.compliant_artifacts("CONTROLLER", _blueprint()))

    assert report.evaluable is True
    assert report.score == 100
    assert report.rule_histogram == {}


def test_a_set_with_findings_is_evaluable_and_flagged():
    report = diagnose(fm.violating_artifacts("LAYER_ISOLATION", _blueprint()))

    assert report.evaluable is True
    assert report.score < 100
    assert report.rule_histogram


def test_the_three_states_are_distinguishable_after_round_trip():
    _write("t015-a", diagnose({}))                                  # not evaluable
    _write("t015-b", diagnose(fm.compliant_artifacts("CONTROLLER", _blueprint())))
    _write("t015-c", diagnose(fm.violating_artifacts("LAYER_ISOLATION", _blueprint())))

    empty = read_diagnostic_record("t015-a")
    clean = read_diagnostic_record("t015-b")
    dirty = read_diagnostic_record("t015-c")

    assert empty["evaluable"] is False
    assert clean["evaluable"] is True and clean["rule_histogram"] == {}
    assert dirty["evaluable"] is True and dirty["rule_histogram"] != {}


# ---------------------------------------------------------------------------
# T010 — unverified sessions are marked
# ---------------------------------------------------------------------------
def test_an_unverified_session_is_marked_whatever_it_scored():
    report = diagnose(fm.compliant_artifacts("CONTROLLER", _blueprint()))
    _write("t015-a", report, unverified=True)

    record = read_diagnostic_record("t015-a")

    assert record["unverified"] is True, (
        "a session whose build fell back to a synthetic result was not marked; "
        "counting it would report a success the platform never achieved"
    )
    assert record["score"] == 100, "the marking must not alter the measured score"


def test_a_verified_session_is_not_marked():
    _write("t015-b", diagnose(fm.compliant_artifacts("CONTROLLER", _blueprint())))
    assert read_diagnostic_record("t015-b")["unverified"] is False


# ---------------------------------------------------------------------------
# T012 — per-stage attribution (FR-006, SC-002)
# ---------------------------------------------------------------------------
def test_findings_are_attributed_to_the_stage_that_introduced_them():
    from app.services.conformance_diagnostics import stage_attribution

    journal = {"entries": [
        {"stage": "SCAFFOLDER", "outcome": "CLEAN", "request_count": 1,
         "initial_verdict": {"passed": True, "violations": []}},
        {"stage": "CONTROLLER", "outcome": "CORRECTED", "request_count": 2,
         "initial_verdict": {"passed": False, "violations": [
             {"rule_id": "PRINCIPLE_I_LAYER_ISOLATION", "severity": "HIGH",
              "artifact_path": "NoteController.java", "message": "x"},
         ]}},
    ]}

    attributed = stage_attribution(journal)
    by_stage = {entry["stage"]: entry for entry in attributed}

    assert by_stage["SCAFFOLDER"]["rule_histogram"] == {}
    assert by_stage["CONTROLLER"]["rule_histogram"] == {"PRINCIPLE_I_LAYER_ISOLATION": 1}, (
        "the violation was not attributed to the stage that introduced it"
    )
    assert by_stage["CONTROLLER"]["counts_by_severity"] == {"HIGH": 1}


def test_attribution_reads_a_missing_or_empty_journal_without_raising():
    from app.services.conformance_diagnostics import stage_attribution

    assert stage_attribution(None) == []
    assert stage_attribution({}) == []
    assert stage_attribution({"entries": []}) == []
    # A malformed entry must not abort attribution of the well-formed ones.
    assert stage_attribution({"entries": ["not a mapping", {"stage": "DOMAIN"}]}) == [
        {"stage": "DOMAIN", "outcome": None, "request_count": None,
         "rule_histogram": {}, "counts_by_severity": {}, "passed": None}
    ]


def test_a_stage_with_no_verdict_is_not_reported_as_passed():
    """No verdict is a third state, not a pass.

    The store actually held this shape: five EXHAUSTED stages, every one reported
    ``passed``, every rule histogram empty. Rendering "no verdict was produced" as
    "the first candidate passed" makes a session in which every stage was rejected
    read as a clean one -- the conflation FR-004 forbids, one level down, and the
    exact input an optimizer would otherwise learn nothing from.
    """
    from app.services.conformance_diagnostics import stage_attribution

    attributed = stage_attribution({"entries": [
        # A stage whose candidate never parsed: no initial_verdict at all.
        {"stage": "SCAFFOLDER", "outcome": "EXHAUSTED", "request_count": 3},
        # An explicit verdict, for contrast: these two ARE passes and failings.
        {"stage": "DOMAIN", "outcome": "CLEAN", "request_count": 1,
         "initial_verdict": {"passed": True, "violations": []}},
        {"stage": "TEST", "outcome": "CORRECTED", "request_count": 2,
         "initial_verdict": {"passed": False, "violations": [
             {"rule_id": "R", "severity": "HIGH", "artifact_path": "a.java"}]}},
    ]})

    by_stage = {entry["stage"]: entry for entry in attributed}
    assert by_stage["SCAFFOLDER"]["passed"] is None, (
        "a stage that produced no verdict was reported as if it had passed"
    )
    assert by_stage["DOMAIN"]["passed"] is True
    assert by_stage["TEST"]["passed"] is False


# ---------------------------------------------------------------------------
# T014 — findings survive a run that fails after producing artifacts
# ---------------------------------------------------------------------------
def test_a_blocked_session_still_records_what_was_found():
    """A blocked session is the one most worth diagnosing, so the failing path
    must not be the path that skips recording."""
    from app.api.routes_session import _persist_diagnostics

    blueprint = _blueprint()
    final_state = {
        "status": "BLOCKED",
        "error": "tests failed after 5 attempts",
        "generated_files": fm.violating_artifacts("LAYER_ISOLATION", blueprint),
        "test_metrics": {"allPassed": False, "fallback_used": False},
        "generation_journal": {"entries": [
            {"stage": "CONTROLLER", "outcome": "EXHAUSTED", "request_count": 3,
             "initial_verdict": {"passed": False, "violations": [
                 {"rule_id": "PRINCIPLE_I_LAYER_ISOLATION", "severity": "HIGH",
                  "artifact_path": "NoteController.java", "message": "x"}]}},
        ]},
    }

    assert _persist_diagnostics("t015-d", final_state) is True

    record = read_diagnostic_record("t015-d")
    assert record is not None, "a blocked session produced no diagnostic record"
    assert "PRINCIPLE_I_LAYER_ISOLATION" in record["rule_histogram"], (
        "the findings produced before the failure were discarded"
    )
    assert record["stages"], "per-stage attribution was not recorded"
    assert any(s["stage"] == "CONTROLLER" for s in record["stages"])


def test_a_session_with_no_artifacts_records_as_not_evaluable_not_as_clean():
    """A blocked session that produced nothing must be distinguishable from one
    that produced nothing *wrong*."""
    from app.api.routes_session import _persist_diagnostics

    final_state = {"status": "BLOCKED", "error": "runtime unavailable",
                   "generated_files": {}, "test_metrics": {"fallback_used": True}}

    assert _persist_diagnostics("t015-c", final_state) is True

    record = read_diagnostic_record("t015-c")
    assert record["evaluable"] is False, "nothing to evaluate was recorded as clean"
    assert record["unverified"] is True, "a synthetic verification was not marked"


# ---------------------------------------------------------------------------
# Schema evolution: an existing table must keep working
# ---------------------------------------------------------------------------
def test_a_table_created_before_a_column_existed_is_repaired(tmp_path):
    """create_all creates missing TABLES, never missing COLUMNS.

    This was found by running the report against a real database that already had
    the table from before the `task` label existed -- the report crashed with
    `no such column`. The suite could not catch it because the test database is
    built fresh from the model every run, so no test ever saw an older table.
    """
    from sqlalchemy import create_engine, text
    from app.models import diagnostics as diag

    stale = create_engine(f"sqlite:///{(tmp_path / 'stale.db').as_posix()}")

    # A table shaped the way an earlier version of the model left it: the
    # session_id key and a score, but none of the columns added since.
    with stale.connect() as conn:
        conn.execute(text(
            "CREATE TABLE session_diagnostic_records ("
            " session_id TEXT PRIMARY KEY, score INTEGER NOT NULL)"
        ))
        conn.commit()

    diag.ensure_schema(stale)

    with stale.connect() as conn:
        columns = {row[1] for row in conn.execute(
            text("PRAGMA table_info(session_diagnostic_records)"))}

    for expected in ("task", "density", "evaluable", "unverified", "stages_json"):
        assert expected in columns, (
            f"the column {expected!r} was not added to the existing table; a real "
            f"database would keep failing at query time"
        )


def test_ensure_schema_is_idempotent(tmp_path):
    from sqlalchemy import create_engine
    from app.models import diagnostics as diag

    fresh = create_engine(f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}")
    diag.ensure_schema(fresh)
    diag.ensure_schema(fresh)   # must not raise on a second call


# ---------------------------------------------------------------------------
# The stage-runner exhaustion path: evidence must survive it
# ---------------------------------------------------------------------------
# The first real generation run (docs/agentia_first_baseline.tex) followed this
# exact shape: every stage spent its whole correction budget, the first four were
# accepted on their third attempt, and TEST never converged. The session then
# terminated BLOCKED -- and a blocked session is the one most worth diagnosing.
#
# The concern was that the artifacts from the four accepted stages were lost on
# that path, leaving the diagnostic record with artifact_count=0. These tests
# reproduce the shape deterministically (scripted model, no provider, no cost) and
# assert that the evidence reaches the record.
VIOLATION = "PROHIBITED_ANNOTATION"


def _script_responses(monkeypatch, responses):
    """Point the factory at a scripted fake; no network, no provider."""
    from app.services.llm_factory import LLMFactory

    model = fm.make_scripted_model(*responses)
    monkeypatch.setattr(LLMFactory, "get_chat_model", staticmethod(lambda **kwargs: model))
    return model


def _real_baseline_pattern(blueprint):
    """SCAFFOLDER/DOMAIN/SERVICE/CONTROLLER pass on attempt 3; TEST exhausts.

    Two rejecting responses then an accepted one is what "passed on the third
    attempt" means: the initial candidate and the first correction were both
    rejected, and the second correction was the one that satisfied the gate.
    """
    responses = []
    for stage in ("SCAFFOLDER", "DOMAIN", "SERVICE", "CONTROLLER"):
        responses.append(fm.canonical_json_response(fm.violating_artifacts(VIOLATION, blueprint)))
        responses.append(fm.canonical_json_response(fm.violating_artifacts(VIOLATION, blueprint)))
        responses.append(fm.canonical_json_response(fm.compliant_artifacts(stage, blueprint)))
    responses.extend(
        [fm.canonical_json_response(fm.violating_artifacts(VIOLATION, blueprint))] * 3
    )
    return responses


def _model_state(blueprint, workspace, session_id):
    return {
        "session_id": session_id,
        "blueprint": blueprint,
        "workspace_path": str(workspace),
        "generated_files": {},
        "logs": [],
        "generation_mode": "MODEL",
        "llm_provider": "deepseek",
        "llm_model": "deepseek-flash",
        "llm_api_key": "sk-fake-key-for-tests",
    }


def test_stage_exhaustion_preserves_the_artifacts_earlier_stages_persisted(
    monkeypatch, tmp_path
):
    """The stage boundary's exhaustion path must not discard prior artifacts."""
    from app.orchestrator.stages.runner import STAGE_ORDER, run_stages

    blueprint = _blueprint("minimal")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    model = _script_responses(monkeypatch, _real_baseline_pattern(blueprint))

    result = run_stages(
        _model_state(blueprint, workspace, "t015-a"), stages=STAGE_ORDER,
        api_key="sk-fake-key-for-tests",
    )

    assert model.call_count == 15, "the scripted pattern no longer matches the real run"
    assert result["status"] == "BLOCKED"
    persisted = result["generated_files"]
    assert len(persisted) == 7, (
        f"the artifacts the four accepted stages persisted were lost on the "
        f"exhaustion path; got {sorted(persisted)}"
    )
    # TEST never had a candidate accepted, so nothing of its own may appear.
    assert not any(path.startswith("src/test/") for path in persisted)

    journal = result["generation_journal"]
    outcomes = {e["stage"]: e["outcome"] for e in journal["entries"]}
    assert outcomes["TEST"] == "EXHAUSTED"
    assert all(
        outcomes[stage] == "CORRECTED"
        for stage in ("SCAFFOLDER", "DOMAIN", "SERVICE", "CONTROLLER")
    ), f"the pattern did not reproduce: {outcomes}"


def test_a_test_stage_exhaustion_records_the_prior_artifacts_and_their_rules(
    monkeypatch, tmp_path
):
    """A blocked session must carry evidence, not artifact_count=0."""
    from app.api.routes_session import _persist_diagnostics
    from app.orchestrator.stages.runner import STAGE_ORDER, run_stages

    blueprint = _blueprint("minimal")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _script_responses(monkeypatch, _real_baseline_pattern(blueprint))

    result = run_stages(
        _model_state(blueprint, workspace, "t015-b"), stages=STAGE_ORDER,
        api_key="sk-fake-key-for-tests",
    )
    assert _persist_diagnostics("t015-b", result) is True

    record = read_diagnostic_record("t015-b")
    assert record is not None
    assert record["artifact_count"] == 7, (
        "the blocked session recorded no artifacts even though four stages persisted"
    )
    assert record["evaluable"] is True, "nothing to evaluate, on a session that produced artifacts"

    by_stage = {entry["stage"]: entry for entry in record["stages"]}
    assert by_stage["TEST"]["outcome"] == "EXHAUSTED"
    corrected = [e for e in record["stages"] if e["outcome"] == "CORRECTED"]
    assert len(corrected) == 4
    assert any(entry["rule_histogram"] for entry in corrected), (
        "the rules that rejected each stage's first candidate were not attributed; "
        "the record would show a session that failed with no reason for the failure"
    )


def test_the_graph_accumulator_preserves_artifacts_when_a_stage_exhausts(
    monkeypatch, tmp_path
):
    """The production accumulator (`stream` + update) must preserve them too.

    routes_session does not read the graph's returned state directly: it folds
    each node's output into its own accumulator. That accumulator is the state the
    diagnostic record is finally written from, so it is the one that matters.
    """
    from app.orchestrator.graph import generation_graph

    blueprint = _blueprint("minimal")
    workspace = tmp_path / "ws_graph"
    workspace.mkdir()
    model = _script_responses(monkeypatch, _real_baseline_pattern(blueprint))

    class _Unverifiable:
        fallback_used = True
        is_success = False
        fallback_reason = "test: the container runtime is not consulted"
        duration_ms = 0

    async def _fake_sandbox(*args, **kwargs):
        return _Unverifiable()

    monkeypatch.setattr(
        "app.orchestrator.nodes.sandbox_node.run_docker_sandbox", _fake_sandbox
    )

    initial = _model_state(blueprint, workspace, "t015-c")
    initial["repair_attempts"] = 0
    initial["max_repair_attempts"] = 3

    accumulated = dict(initial)
    nodes = []
    for step in generation_graph.stream(initial):
        node_name = list(step.keys())[0]
        nodes.append(node_name)
        accumulated.update(step[node_name])

    assert model.call_count == 15
    assert nodes[-1] == "sandbox", f"the graph did not reach the sandbox: {nodes}"
    assert len(accumulated["generated_files"]) == 7, (
        "the production accumulator lost the artifacts of the four accepted stages"
    )


def test_the_sequential_pipeline_terminates_and_records_a_stage_exhaustion(
    monkeypatch, tmp_path
):
    """The Auto-Pilot path must not leave a blocked session non-terminal.

    This is the exhaustion-path defect. `pipeline_runner._execute_pipeline_steps`
    returned early when the generation stages blocked, setting only an in-memory
    status. The session row stayed in its pre-run state forever and **no
    diagnostic record was written at all** -- so the one session most worth
    diagnosing left no evidence, and SC-001 ("every session reaching a terminal
    state carries a record") was false for this whole execution path.

    The artifacts were never the thing that was lost: the four accepted stages'
    artifacts were in the returned state and on disk. Nothing recorded them.
    """
    import threading

    import app.services.pipeline_runner as pipeline_runner
    from app.models.orchestrator import LifecyclePhase
    from app.models.session import GenerationSessionDB, SessionPhase, SessionStatus

    session_id = "t015-e"
    blueprint = _blueprint("minimal")
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    # Keep the cost recorder off the real store; this test is not about cost.
    monkeypatch.setattr(settings, "COST_STORE_PATH", str(tmp_path / "cost.db"), raising=False)
    _script_responses(monkeypatch, _real_baseline_pattern(blueprint))

    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
        db.add(GenerationSessionDB(
            id=session_id, spec_id="spec-t015-e", spec_name="notes-service",
            status=SessionStatus.QUEUED, phase=SessionPhase.INITIALIZATION,
            current_lifecycle_phase="INITIAL", lifecycle_mode="GUIDED_STEP",
            repair_attempts=0,
        ))
        db.commit()
    finally:
        db.close()

    pipeline_runner._pause_events[session_id] = threading.Event()
    pipeline_runner._stop_events[session_id] = threading.Event()

    try:
        pipeline_runner._execute_pipeline_steps(
            session_id, LifecyclePhase.DEVOPS_DEPLOY,
            stop_on_gate=True, auto_deploy=False,
            api_key="sk-fake-key-for-tests", provider="deepseek",
        )

        db = SessionLocal()
        try:
            row = db.query(GenerationSessionDB).filter(
                GenerationSessionDB.id == session_id
            ).first()
            assert row.status == SessionStatus.BLOCKED, (
                "a stage-exhausted session was left non-terminal; it will read as "
                "still running forever"
            )
            assert row.phase == SessionPhase.FAILED
            assert "budget exhausted" in (row.error_message or "")
        finally:
            db.close()

        record = read_diagnostic_record(session_id)
        assert record is not None, (
            "the sequential pipeline blocked a session and recorded no diagnostic "
            "at all; the evidence vanished on exactly the path that needed it"
        )
        assert record["artifact_count"] == 7, (
            "the four accepted stages persisted artifacts, and the record does not "
            "carry them"
        )
        assert record["evaluable"] is True
    finally:
        for store in (pipeline_runner._pause_events, pipeline_runner._stop_events,
                      pipeline_runner._pipeline_statuses, pipeline_runner._session_credentials):
            store.pop(session_id, None)
        db = SessionLocal()
        try:
            db.query(GenerationSessionDB).filter(
                GenerationSessionDB.id == session_id
            ).delete()
            db.commit()
        finally:
            db.close()


def test_a_session_that_blocked_before_the_sandbox_is_not_verified():
    """No metrics means verification never ran, and that is not a pass.

    The first real baseline's report counted one "verified" session whose build
    never ran: it blocked during generation, so no verification metrics were ever
    persisted, and deriving `unverified` from `fallback_used` alone left it False.
    The report then quoted that session's score as the corpus's only conformance
    number -- a number from a workspace nobody compiled.
    """
    from app.api.routes_session import _persist_diagnostics

    final_state = {
        "status": "BLOCKED",
        "error": "[TEST] correction budget exhausted after 2 correction attempts",
        "generated_files": fm.compliant_artifacts("CONTROLLER", _blueprint()),
        "generation_journal": {"entries": []},
        # No "test_metrics" key at all: the sandbox was never reached.
    }

    assert _persist_diagnostics("t015-d", final_state) is True

    record = read_diagnostic_record("t015-d")
    assert record["evaluable"] is True, "the artifacts were produced and are evaluable"
    assert record["unverified"] is True, (
        "a session that never reached the sandbox was reported as verified; its "
        "conformance score would then enter the corpus as measured evidence"
    )
