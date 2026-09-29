"""One-iteration tests (feature 014, T016-T017 / US4).

The whole loop, with a scripted model and an injected runner. What is asserted:

* one iteration completes and reports the four facts;
* **exactly one run row**, on every exit path including failure, because a crashed
  iteration that left no row is indistinguishable from one that never ran;
* `NO_FAILURES` and `NO_SESSIONS` stop **before calling a model** — calling one with
  an empty failure set would invent edits out of nothing;
* the rotation is deterministic;
* the original skill file changes only on acceptance.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.models.session import (  # noqa: E402
    GenerationSessionDB, SessionLocal, SessionPhase, SessionStatus,
)
from app.models.skillopt import read_runs  # noqa: E402
from scripts.run_skillopt import run_iteration  # noqa: E402
from scripts.skillopt.gate import (  # noqa: E402
    BASELINE_BLUEPRINTS,
    ExecutionResult,
    select_held_out,
)
from tests.fixtures import fake_model as fm  # noqa: E402

SESSION_IDS = ["t016-a", "t016-b", "t016-c", "t016-d"]

SKILL_TEXT = """# A Skill

## Granularity
task-level

## When to apply
Whenever.

## Rules
1. First rule.

<!-- SLOW_UPDATE_START -->
<!-- SLOW_UPDATE_END -->
"""


@pytest.fixture(autouse=True)
def clean_runs():
    before = {row["id"] for row in read_runs()}
    yield
    after = read_runs()
    db = SessionLocal()
    try:
        from app.models.skillopt import SkillOptRun
        for row in after:
            if row["id"] not in before:
                db.query(SkillOptRun).filter(SkillOptRun.id == row["id"]).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_sessions():
    db = SessionLocal()
    try:
        for sid in SESSION_IDS:
            db.query(GenerationSessionDB).filter(GenerationSessionDB.id == sid).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        for sid in SESSION_IDS:
            db.query(GenerationSessionDB).filter(GenerationSessionDB.id == sid).delete()
        db.commit()
    finally:
        db.close()


def _seed_failure(session_id="t016-a"):
    db = SessionLocal()
    try:
        db.add(GenerationSessionDB(
            id=session_id, spec_id=f"spec-{session_id}", spec_name="notes",
            status=SessionStatus.BLOCKED, phase=SessionPhase.FAILED,
            verification_metrics_json=json.dumps({"allPassed": False, "fallback_used": False}),
            artifact_provenance_json=json.dumps([
                {"artifact_path": "src/main/java/com/corp/notes/controller/NoteController.java"}
            ]),
        ))
        db.commit()
    finally:
        db.close()


def _seed_success(session_id="t016-b"):
    db = SessionLocal()
    try:
        db.add(GenerationSessionDB(
            id=session_id, spec_id=f"spec-{session_id}", spec_name="notes",
            status=SessionStatus.COMPLETED, phase=SessionPhase.VERIFIED,
            verification_metrics_json=json.dumps({"allPassed": True, "fallback_used": False}),
        ))
        db.commit()
    finally:
        db.close()


def _skill(tmp_path, body="1. First rule."):
    path = tmp_path / "skill.md"
    path.write_text(SKILL_TEXT.replace("1. First rule.", body), encoding="utf-8")
    return path


def _patch_model(monkeypatch, edits):
    model = fm.make_scripted_model(json.dumps(edits))
    import langchain_openai
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", lambda **kwargs: model)
    return model


def _runner(current_pass=frozenset(BASELINE_BLUEPRINTS), candidate_pass=frozenset(BASELINE_BLUEPRINTS)):
    """A scripted runner driven by explicit pass-sets.

    Named by blueprint rather than by index, so the outcome does not depend on which
    subset the rotation happened to hold out.
    """
    def _run(blueprint, skill_path):
        is_candidate = "candidate" in str(skill_path)
        passing = candidate_pass if is_candidate else current_pass
        return ExecutionResult(
            blueprint=blueprint,
            session_id=f"fresh-{blueprint}-{'cand' if is_candidate else 'cur'}",
            exit_code=0 if blueprint in passing else 1,
            fallback_used=False,
        )
    return _run


def _run(tmp_path, runner, monkeypatch, *, edits=None, iteration_id="iter-1", sessions=("t016-a",)):
    skill = _skill(tmp_path)
    _patch_model(monkeypatch, edits if edits is not None else [{"op": "append", "content": "2. New rule."}])
    return run_iteration(
        skill_path=skill,
        runner=runner,
        iteration_id=iteration_id,
        n_training=12,
        session_ids=list(sessions),
        # Explicit provider so the factory takes the real provider branch and the
        # patched class is what it constructs. Without one the factory short-circuits
        # to MOCK and returns no client, which would make this test assert nothing.
        provider="deepseek",
        api_key="sk-unit-test",
        output=lambda line: None,
    ), skill


# ---------------------------------------------------------------------------
# One full iteration
# ---------------------------------------------------------------------------
def test_one_iteration_reports_the_four_facts_and_writes_one_row(tmp_path, monkeypatch):
    _seed_failure()
    # The candidate passes everything; the current skill passes only one blueprint.
    result, _ = _run(tmp_path, _runner({"minimal"}, set(BASELINE_BLUEPRINTS)), monkeypatch)

    assert result["candidate_score"] == pytest.approx(1.0)
    assert result["current_score"] < 1.0
    assert result["decision"] == "ACCEPTED"
    assert result["edit_count"] == 1

    rows = read_runs(limit=5)
    assert len(rows) == 1, f"expected exactly one run row, found {len(rows)}"
    assert rows[0]["decision"] == "ACCEPTED"
    assert rows[0]["current_score"] == result["current_score"]
    assert rows[0]["candidate_score"] == pytest.approx(1.0)


def test_a_rejected_iteration_leaves_the_skill_unchanged(tmp_path, monkeypatch):
    _seed_failure()
    before = _skill(tmp_path).read_text(encoding="utf-8")
    skill = tmp_path / "skill.md"

    result, _ = _run(tmp_path, _runner(), monkeypatch)  # both pass all -> tie -> rejected

    assert result["decision"] == "REJECTED"
    assert skill.read_text(encoding="utf-8") == before, (
        "a rejected candidate modified the original skill"
    )
    assert len(read_runs(limit=5)) == 1


def test_an_accepted_iteration_writes_the_candidate(tmp_path, monkeypatch):
    _seed_failure()
    skill = tmp_path / "skill.md"
    _run(tmp_path, _runner(set(), set(BASELINE_BLUEPRINTS)), monkeypatch)

    assert "2. New rule." in skill.read_text(encoding="utf-8"), (
        "an accepted candidate was not written to the skill"
    )


# ---------------------------------------------------------------------------
# Nothing to learn from
# ---------------------------------------------------------------------------
def test_no_sessions_stops_without_calling_a_model(tmp_path, monkeypatch):
    model = _patch_model(monkeypatch, [])
    result, _ = _run(tmp_path, _runner(set(), set(BASELINE_BLUEPRINTS)), monkeypatch, sessions=())

    assert result["decision"] == "NO_SESSIONS"
    assert model.call_count == 0, "a model was called with no sessions to learn from"
    assert len(read_runs(limit=5)) == 1


def test_no_failures_stops_without_calling_a_model(tmp_path, monkeypatch):
    _seed_success()
    model = _patch_model(monkeypatch, [])
    result, _ = _run(tmp_path, _runner(set(), set(BASELINE_BLUEPRINTS)), monkeypatch, sessions=("t016-b",))

    assert result["decision"] == "NO_FAILURES"
    assert model.call_count == 0, "a model was called with nothing to learn from"
    assert len(read_runs(limit=5)) == 1


# ---------------------------------------------------------------------------
# Failure still leaves a record
# ---------------------------------------------------------------------------
def test_a_failing_iteration_leaves_exactly_one_row_carrying_the_error(tmp_path, monkeypatch):
    _seed_failure()

    with pytest.raises(Exception):
        # The malformed response is supplied through _run: patching beforehand would
        # be overwritten by _run's own patch, and the test would assert nothing.
        _run(tmp_path, _runner(set(), set(BASELINE_BLUEPRINTS)), monkeypatch,
             edits="this is not a JSON array of edits")

    rows = read_runs(limit=5)
    assert len(rows) == 1, "a failed iteration left no record, or more than one"
    assert rows[0]["decision"] == "ERROR"
    assert rows[0]["error"], "the failing run recorded no error"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
def test_the_rotation_is_deterministic_for_the_same_iteration(tmp_path, monkeypatch):
    _seed_failure()
    first, _ = _run(tmp_path, _runner(set(), set(BASELINE_BLUEPRINTS)), monkeypatch, iteration_id="same")
    second, _ = _run(tmp_path, _runner(set(), set(BASELINE_BLUEPRINTS)), monkeypatch, iteration_id="same")

    assert first["held_out_blueprints"] == second["held_out_blueprints"]


# ===========================================================================
# T017 — the opt-in real iteration (SC-007)
# ===========================================================================
REAL_SKILLOPT_ENV = "AGENTIA_RUN_REAL_SKILLOPT"
#: A SECOND, explicit acknowledgement is required, beyond the run flag.
#:
#: Why two: `app/config.py` calls `load_dotenv()`, so a key sitting in `backend/.env`
#: lands in `os.environ` and silently satisfies a key-presence check. A single flag
#: is therefore enough to spend money without the operator realising a key exists —
#: which is exactly what happened while this test was being written. Requiring an
#: acknowledgement whose only purpose is to say "I know this costs money" makes the
#: spend a deliberate act rather than a side effect of probing skip behaviour.
REAL_SPEND_ENV = "AGENTIA_ALLOW_REAL_SPEND"


def test_a_real_iteration_runs_end_to_end(tmp_path, monkeypatch):
    """One genuine iteration against a live model.

    **Opt-in**, because it is the only test in this feature that calls a provider
    and spends money (Constitution Principle VI forbids it in the default suite).

    It uses the **real** session runner, so the gate executes real generations.
    That is expensive: 2xM sessions plus one reflection call.

    If either the flag or the key is absent it skips, naming which one is missing,
    and SC-007 is reported as *not verified* rather than inferred from the scripted
    path — inferring it would be the substitution features 012 and 013 refused for
    their own opt-in criteria.
    """
    import os

    if os.environ.get(REAL_SKILLOPT_ENV) != "1":
        pytest.skip(
            f"set {REAL_SKILLOPT_ENV}=1 AND {REAL_SPEND_ENV}=1 to run a real "
            f"iteration, which spends real money"
        )

    if os.environ.get(REAL_SPEND_ENV) != "1":
        # A key may be present purely because backend/.env exists; this variable is
        # the operator saying they know that and accept the cost.
        pytest.skip(
            f"{REAL_SKILLOPT_ENV}=1 but {REAL_SPEND_ENV} is not set. A key may be "
            f"available from backend/.env without you realising, so this test "
            f"requires an explicit acknowledgement that it spends money."
        )

    # Read the key BEFORE any app import could have injected it from .env: if it is
    # absent from the inherited environment, the operator has not exported one and
    # this test must not reach a provider.
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip(f"{REAL_SKILLOPT_ENV}=1 but DEEPSEEK_API_KEY is not set")

    _seed_failure()

    from scripts.skillopt.real_runner import make_real_runner

    skill = _skill(tmp_path)
    summary = run_iteration(
        skill_path=skill,
        runner=make_real_runner(),
        iteration_id="real",
        n_training=12,
        session_ids=SESSION_IDS,
        provider="deepseek",
        api_key=api_key,
        output=lambda line: None,
    )

    assert summary["decision"] in ("ACCEPTED", "REJECTED"), (
        f"a real iteration reached no decision: {summary.get('error')}"
    )
    assert len(read_runs(limit=5)) == 1
