"""QE coverage: the lifecycle state machine (``services/lifecycle_service.py``).

Every phase gate, every completion percentage and every "siguiente acción" the UI shows
comes out of this module. It sat at 76.4% -- and the uncovered surface turned out to be
**unreachable**, which is the finding this file is built around.

Two real defects were found by these tests failing, and both are now fixed in the module:

1. **Duplicated definitions.** ``mark_downstream_outdated`` and ``clear_outdated_phases``
   were each defined TWICE (lines 325/351 and 437/478). Python binds the name to the last
   definition, so the first pair was dead code -- ~55 statements no test could ever reach.
   They were not merely redundant: the shadowed ``mark_downstream_outdated`` *returned*
   ``None`` and *overwrote* the outdated set, while the live one *returns* the accumulated
   list. A caller reading the first signature would have branched on the wrong value. The
   dead pair is removed; ``test_each_progress_function_is_defined_once`` stops it coming back.

2. **A blocking reason that was computed and discarded.** Both BLOCKED paths assigned a
   local ``blocked_reason``, but ``PhaseState`` is built from ``reason``. Nothing ever read
   ``blocked_reason``, so a session stopped by the 3-attempt limit -- or by a failed quality
   gate -- reached the UI as ``BLOCKED`` with ``blockingReason: null``. The operator saw the
   stop but not the cause. Both paths now assign ``reason``, and the tests below assert the
   *content* of the message rather than only the status.

The phase rules themselves are tested against a real SQLite row and a real workspace
directory, because the module's whole job is that DB + filesystem agreement.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import app.services.lifecycle_service as lifecycle  # noqa: E402
from app.models.orchestrator import (  # noqa: E402
    LifecyclePhase,
    PhaseStatus,
    PipelineExecutionMode,
    PipelineRunStatus,
)
from app.models.session import (  # noqa: E402
    GenerationSessionDB,
    SessionLocal,
    SessionPhase,
    SessionStatus,
)


class _QualityGate:
    def __init__(self, status="APPROVED", can_export=True, message="ok"):
        self.status = status
        self.canExport = can_export
        self.summaryMessage = message


class _Audit:
    def __init__(self, gate=None, vulnerabilities=(), violations=()):
        self.qualityGate = gate or _QualityGate()
        self.vulnerabilities = list(vulnerabilities)
        self.violations = list(violations)


@pytest.fixture
def session(tmp_path, monkeypatch):
    """A real DB row plus a real workspace directory, per test."""
    session_id = "qe-lifecycle-session"
    ws = tmp_path / session_id
    ws.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(lifecycle.settings, "WORKSPACE_DIR", str(tmp_path))
    # Neither probe should touch a socket or the pipeline registry in a unit test.
    monkeypatch.setattr(
        lifecycle, "get_deployment_status", lambda sid, host_port=8080: _stub_deploy()
    )
    monkeypatch.setattr(lifecycle, "audit_workspace", lambda *a, **k: _Audit())

    yield session_id, ws

    db = SessionLocal()
    db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
    db.commit()
    db.close()


def _stub_deploy():
    from app.models.devops import DeploymentStatus, LocalDeploymentSession

    return LocalDeploymentSession(sessionId="stub", status=DeploymentStatus.IDLE)


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


def _complete_through_phase_4(ws: Path):
    """Lay down the artifacts phases 1-4 are detected by."""
    (ws / "spec.md").write_text("# Spec", encoding="utf-8")
    (ws / "user_stories.json").write_text(json.dumps([{"id": "US1"}]), encoding="utf-8")
    (ws / "architecture.json").write_text("{}", encoding="utf-8")
    (ws / "schema.sql").write_text("CREATE TABLE t (id SERIAL);", encoding="utf-8")


def _complete_phase_5(ws: Path):
    (ws / "pom.xml").write_text("<project/>", encoding="utf-8")
    (ws / "src" / "main" / "java").mkdir(parents=True, exist_ok=True)
    (ws / "src" / "main" / "java" / "App.java").write_text("class App {}", encoding="utf-8")
    from app.services.verification_policy import workspace_fingerprint
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, ws.name)
        if row.status not in (SessionStatus.BLOCKED, SessionStatus.CANCELLED):
            row.status = SessionStatus.COMPLETED
            row.verification_metrics_json = json.dumps({"sourceDeliveryReady": True, "sourceDeliveryFingerprint": workspace_fingerprint(ws)})
            db.commit()


# ---------------------------------------------------------------------------
# The defect: two definitions of the same function
# ---------------------------------------------------------------------------
def test_each_progress_function_is_defined_once():
    """Regression guard for the shadowing defect described in the module docstring.

    Two definitions of one name is legal Python and silently discards the first. There is
    no test that can reach the shadowed body, so the only way to catch a re-introduction
    is to check the source.
    """
    source = inspect.getsource(lifecycle)
    for name in ("mark_downstream_outdated", "clear_outdated_phases"):
        assert source.count(f"def {name}(") == 1, (
            f"{name} is defined more than once; the earlier definition is dead code and "
            "the two versions will drift apart"
        )


def test_the_live_mark_downstream_outdated_returns_the_accumulated_set(session):
    """Pins the surviving signature: a list of the outdated phase values.

    The removed duplicate returned ``None`` and replaced the set instead of extending it.
    A caller branching on the return value would have misread a successful mark as a
    no-op, so the return type is part of the contract.
    """
    session_id, ws = session
    _make_session(session_id)
    _complete_through_phase_4(ws)

    result = lifecycle.mark_downstream_outdated(session_id, LifecyclePhase.STORIES)

    assert isinstance(result, list), "the removed definition returned None"

    # Only phases that have actually been BUILT can be stale. This fixture lays down the
    # artifacts for phases 1-4, so ARCHITECTURE and DATA_MODEL are flagged and the three
    # beyond them are not: they have no artifacts, so there is nothing to be stale.
    #
    # This assertion previously expected all five. That was the reported bug -- clicking
    # "Aprobar y Diseñar Arquitectura" flagged every downstream phase unconditionally, so
    # the banner announced "upstream modifications detected" after nothing but a routine
    # approval, and its Re-sincronizar button re-ran generation for a correct state.
    assert set(result) == {
        LifecyclePhase.ARCHITECTURE.value,
        LifecyclePhase.DATA_MODEL.value,
    }
    assert LifecyclePhase.CODE_TESTS.value not in result, (
        "an unbuilt phase was marked outdated"
    )

    # …and building a phase makes it eligible again.
    _complete_phase_5(ws)
    grown = lifecycle.mark_downstream_outdated(session_id, LifecyclePhase.STORIES)
    assert LifecyclePhase.CODE_TESTS.value in grown


# ---------------------------------------------------------------------------
# No session row at all
# ---------------------------------------------------------------------------
def test_an_unknown_session_gets_a_fresh_initial_state(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle.settings, "WORKSPACE_DIR", str(tmp_path))

    state = lifecycle.get_session_lifecycle("qe-does-not-exist")

    assert state.current_phase == LifecyclePhase.INITIAL
    assert state.completion_percentage == 0.0
    assert state.phases == []
    assert state.can_advance is True
    assert state.next_target_phase == LifecyclePhase.REQUIREMENTS
    assert "Iniciar" in state.next_recommended_action


# ---------------------------------------------------------------------------
# Phase 1 and 2 detection
# ---------------------------------------------------------------------------
def test_a_session_with_a_spec_id_but_no_spec_file_is_in_progress(session):
    """The spec was ingested but not written to the workspace: started, not finished."""
    session_id, _ = session
    _make_session(session_id, spec_id="spec-present")

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.phases[0].status == PhaseStatus.IN_PROGRESS
    assert state.completion_percentage == 0.0


def test_a_dict_shaped_stories_file_is_counted_by_its_stories_key(session):
    """``{"stories": [...]}`` and ``[...]`` are both written by the pipeline, at different times."""
    session_id, ws = session
    _make_session(session_id)
    (ws / "spec.md").write_text("# Spec", encoding="utf-8")
    (ws / "user_stories.json").write_text(
        json.dumps({"stories": [{"id": "US1"}, {"id": "US2"}, {"id": "US3"}]}), encoding="utf-8"
    )

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.phases[1].artifact_summary["storiesCount"] == 3


def test_a_corrupt_stories_file_still_counts_as_one_story(session):
    """The phase *is* complete -- the file exists. Reporting zero would tell the operator
    the opposite of what the filesystem says, so the count degrades, not the status."""
    session_id, ws = session
    _make_session(session_id)
    (ws / "spec.md").write_text("# Spec", encoding="utf-8")
    (ws / "user_stories.json").write_text("{not json at all", encoding="utf-8")

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.phases[1].status == PhaseStatus.COMPLETED
    assert state.phases[1].artifact_summary["storiesCount"] == 1


def test_phase_two_is_enterable_once_phase_one_is_complete(session):
    """The gate opens *before* the artifact exists: that is how the user starts phase 2.

    Contrast with the test above: there, phase 1 is unfinished so phase 2 is locked. Here
    phase 1 is complete and the stories have not been generated yet, which is the normal
    state in which the operator is meant to press the button -- so ``can_enter`` must be
    true and no blocking reason may be attached.
    """
    session_id, ws = session
    _make_session(session_id)
    (ws / "spec.md").write_text("# Spec", encoding="utf-8")

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.phases[0].status == PhaseStatus.COMPLETED
    assert state.phases[1].status == PhaseStatus.NOT_STARTED
    assert state.phases[1].can_enter is True
    assert state.phases[1].blocking_reason is None


def test_phase_two_is_locked_until_phase_one_completes(session):
    session_id, _ = session
    _make_session(session_id, spec_id="")

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.phases[1].status == PhaseStatus.NOT_STARTED
    assert state.phases[1].can_enter is False
    assert "Fase 1" in state.phases[1].blocking_reason


# ---------------------------------------------------------------------------
# Phase 5: the 3-attempt constitutional limit
# ---------------------------------------------------------------------------
def test_a_blocked_repair_loop_blocks_phase_five_and_the_whole_session(session):
    """Principle V: three failed repairs stop the pipeline and wait for a human.

    ``can_advance`` is what the UI reads to decide whether to offer the next step, so a
    BLOCKED phase that still allowed advancing would silently defeat the limit.
    """
    session_id, ws = session
    _make_session(
        session_id, status=SessionStatus.BLOCKED, repair_attempts=3
    )
    _complete_through_phase_4(ws)
    _complete_phase_5(ws)

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.phases[4].status == PhaseStatus.BLOCKED
    assert state.phases[4].can_enter is True
    assert "3 auto-reparaciones" in state.phases[4].blocking_reason
    assert state.can_advance is False


def test_two_failed_repairs_do_not_block_phase_five(session):
    """The boundary is 3 attempts, not "any failure"."""
    session_id, ws = session
    _make_session(session_id, status=SessionStatus.RUNNING, repair_attempts=2)
    _complete_through_phase_4(ws)
    _complete_phase_5(ws)

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.phases[4].status == PhaseStatus.COMPLETED
    assert state.can_advance is True


# ---------------------------------------------------------------------------
# Phase 6: the quality gate
# ---------------------------------------------------------------------------
def test_a_blocked_quality_gate_blocks_phase_six_and_reports_why(session):
    session_id, ws = session
    _make_session(session_id)
    _complete_through_phase_4(ws)
    _complete_phase_5(ws)
    lifecycle.audit_workspace = lambda *a, **k: _Audit(
        gate=_QualityGate(status="BLOCKED", can_export=False, message="secrets found in App.java")
    )

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.phases[5].status == PhaseStatus.BLOCKED
    assert "secrets found in App.java" in state.phases[5].blocking_reason
    assert state.can_advance is False
    assert state.phases[6].can_enter is False


def test_a_quality_gate_that_raises_leaves_the_phase_not_started(session):
    """A crashed audit is not a passed audit.

    The module swallows the exception; the risk is that the swallow is written as a pass.
    """
    session_id, ws = session
    _make_session(session_id)
    _complete_through_phase_4(ws)
    _complete_phase_5(ws)

    def explode(*args, **kwargs):
        raise RuntimeError("sast engine unavailable")

    lifecycle.audit_workspace = explode

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.phases[5].status == PhaseStatus.NOT_STARTED
    assert state.phases[5].status != PhaseStatus.COMPLETED


def test_the_quality_gate_verdict_and_finding_count_reach_the_summary(session):
    session_id, ws = session
    _make_session(session_id)
    _complete_through_phase_4(ws)
    _complete_phase_5(ws)
    lifecycle.audit_workspace = lambda *a, **k: _Audit(
        gate=_QualityGate(status="APPROVED"),
        vulnerabilities=[1, 2],
        violations=[3],
    )

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.phases[5].artifact_summary["qualityGate"] == "APPROVED"
    assert state.phases[5].artifact_summary["findingsCount"] == 3


def test_phase_six_is_locked_while_phase_five_is_unfinished(session):
    session_id, ws = session
    _make_session(session_id)
    _complete_through_phase_4(ws)

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.phases[5].status == PhaseStatus.NOT_STARTED
    assert state.phases[5].can_enter is False
    assert "Fase 5" in state.phases[5].blocking_reason


# ---------------------------------------------------------------------------
# Phase 7: deploy
# ---------------------------------------------------------------------------
def test_a_compose_file_completes_phase_seven_and_surfaces_the_deploy_status(session):
    session_id, ws = session
    _make_session(session_id)
    _complete_through_phase_4(ws)
    _complete_phase_5(ws)
    (ws / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
    from _support import source_delivery
    source_delivery(session_id, ws)

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.phases[6].status == PhaseStatus.COMPLETED
    assert "deploymentStatus" in state.phases[6].artifact_summary
    assert state.completion_percentage == 100.0


# ---------------------------------------------------------------------------
# Outdated propagation
# ---------------------------------------------------------------------------
def test_outdated_phases_are_read_from_the_progress_json(session):
    session_id, ws = session
    _make_session(
        session_id,
        phase_progress_json=json.dumps({"outdated_phases": [LifecyclePhase.ARCHITECTURE.value]}),
    )
    _complete_through_phase_4(ws)

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.is_outdated is True
    assert state.phases[2].status == PhaseStatus.OUTDATED
    assert state.phases[3].status == PhaseStatus.COMPLETED, "only the named phase is outdated"


def test_a_corrupt_progress_json_reads_as_no_outdated_phases(session):
    """A corrupt row must not take down the whole lifecycle endpoint."""
    session_id, ws = session
    _make_session(session_id, phase_progress_json="{not json")
    _complete_through_phase_4(ws)

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.is_outdated is False
    assert state.phases[2].status == PhaseStatus.COMPLETED


def test_marking_downstream_outdated_accumulates_across_calls(session):
    """Editing phase 2 and then phase 3 must not un-mark phase 3's own downstream set."""
    session_id, ws = session
    _make_session(session_id)
    _complete_through_phase_4(ws)

    first = lifecycle.mark_downstream_outdated(session_id, LifecyclePhase.STORIES)
    second = lifecycle.mark_downstream_outdated(session_id, LifecyclePhase.ARCHITECTURE)

    assert set(second) >= set(first), "the second call discarded the first call's flags"
    assert LifecyclePhase.ARCHITECTURE.value in second
    assert LifecyclePhase.DATA_MODEL.value in second


def test_marking_the_last_phase_outdated_has_no_downstream(session):
    session_id, _ = session
    _make_session(session_id)

    assert lifecycle.mark_downstream_outdated(session_id, LifecyclePhase.DEVOPS_DEPLOY) == []


def test_marking_an_unknown_phase_is_a_no_op(session):
    """``INITIAL`` and ``COMPLETED`` are not in PHASE_ORDER; they must not raise."""
    session_id, _ = session
    _make_session(session_id)

    assert lifecycle.mark_downstream_outdated(session_id, LifecyclePhase.INITIAL) == []


def test_marking_a_session_that_does_not_exist_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle.settings, "WORKSPACE_DIR", str(tmp_path))

    assert lifecycle.mark_downstream_outdated("qe-ghost", LifecyclePhase.STORIES) == []


def test_marking_accepts_a_plain_string_phase(session):
    """The API receives JSON, so the phase arrives as a string as often as an enum."""
    session_id, ws = session
    _make_session(session_id)
    _complete_through_phase_4(ws)

    result = lifecycle.mark_downstream_outdated(session_id, "STORIES")

    assert LifecyclePhase.ARCHITECTURE.value in result


def test_marking_starts_from_clean_when_the_progress_json_is_corrupt(session):
    session_id, ws = session
    _make_session(session_id, phase_progress_json="{broken")
    _complete_through_phase_4(ws)

    result = lifecycle.mark_downstream_outdated(session_id, LifecyclePhase.STORIES)

    assert LifecyclePhase.ARCHITECTURE.value in result


def test_clearing_a_session_that_does_not_exist_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle.settings, "WORKSPACE_DIR", str(tmp_path))

    assert lifecycle.clear_outdated_phases("qe-ghost") is None


def test_clearing_removes_every_outdated_flag(session):
    session_id, ws = session
    _make_session(session_id, phase_progress_json=json.dumps({"outdated_phases": ["ARCHITECTURE"]}))
    _complete_through_phase_4(ws)

    lifecycle.clear_outdated_phases(session_id)

    state = lifecycle.get_session_lifecycle(session_id)
    assert state.is_outdated is False
    assert state.phases[2].status == PhaseStatus.COMPLETED


def test_clearing_a_corrupt_progress_json_still_writes_a_clean_record(session):
    """Re-sync on a corrupt row must leave valid JSON behind, not fail and leave it corrupt."""
    session_id, _ = session
    _make_session(session_id, phase_progress_json="{broken")

    lifecycle.clear_outdated_phases(session_id)

    db = SessionLocal()
    try:
        row = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        assert json.loads(row.phase_progress_json)["outdated_phases"] == []
    finally:
        db.close()


# ---------------------------------------------------------------------------
# transition_phase
# ---------------------------------------------------------------------------
def test_force_bypasses_the_prerequisite_guard(session):
    """The "force re-sync" control in the UI relies on this; without it the operator is
    locked out of a phase they explicitly asked to revisit."""
    session_id, _ = session
    _make_session(session_id)

    state = lifecycle.transition_phase(session_id, LifecyclePhase.DEVOPS_DEPLOY, force=True)

    assert state.current_phase == LifecyclePhase.DEVOPS_DEPLOY


def test_transitioning_an_unknown_session_returns_the_fresh_state(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle.settings, "WORKSPACE_DIR", str(tmp_path))

    state = lifecycle.transition_phase("qe-ghost", LifecyclePhase.REQUIREMENTS, force=True)

    assert state.current_phase == LifecyclePhase.INITIAL


def test_transitioning_to_a_phase_outside_the_order_is_allowed(session):
    """``INITIAL`` and ``COMPLETED`` are legal lifecycle values but have no guard entry."""
    session_id, _ = session
    _make_session(session_id)

    state = lifecycle.transition_phase(session_id, LifecyclePhase.INITIAL)

    assert state.current_phase == LifecyclePhase.INITIAL


# ---------------------------------------------------------------------------
# Degraded enum values and pipeline status
# ---------------------------------------------------------------------------
def test_an_unrecognised_lifecycle_phase_falls_back_to_initial(session):
    """A row written by an older version must not 500 the endpoint."""
    session_id, _ = session
    _make_session(session_id, current_lifecycle_phase="LEGACY_PHASE_NAME")

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.current_phase == LifecyclePhase.INITIAL


def test_an_unrecognised_lifecycle_mode_falls_back_to_guided_step(session):
    session_id, _ = session
    _make_session(session_id, lifecycle_mode="TURBO_MODE")

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.active_mode == PipelineExecutionMode.GUIDED_STEP


@pytest.mark.parametrize(
    "session_status,expected",
    [
        (SessionStatus.RUNNING, PipelineRunStatus.RUNNING),
        (SessionStatus.PAUSED, PipelineRunStatus.PAUSED),
        (SessionStatus.CANCELLED, PipelineRunStatus.CANCELLED),
        (SessionStatus.COMPLETED, PipelineRunStatus.COMPLETED),
    ],
)
def test_the_session_status_is_mirrored_into_the_pipeline_status(session, session_status, expected):
    """The monitor shows one status; the pipeline registry may know nothing (fresh process)."""
    session_id, _ = session
    _make_session(session_id, status=session_status)

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.pipeline_status == expected


def test_a_cancelled_session_cannot_advance_and_says_so(session):
    session_id, _ = session
    _make_session(session_id, status=SessionStatus.CANCELLED)

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.can_advance is False
    assert "cancelado" in state.next_recommended_action


def test_a_paused_session_says_it_can_be_resumed(session):
    session_id, _ = session
    _make_session(session_id, status=SessionStatus.PAUSED)

    state = lifecycle.get_session_lifecycle(session_id)

    assert "pausado" in state.next_recommended_action.lower()


def test_the_next_target_is_the_first_unfinished_phase(session):
    session_id, ws = session
    _make_session(session_id)
    (ws / "spec.md").write_text("# Spec", encoding="utf-8")
    (ws / "user_stories.json").write_text("[]", encoding="utf-8")

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.next_target_phase == LifecyclePhase.ARCHITECTURE
    assert "3." in state.next_recommended_action


def test_a_partially_complete_session_reports_a_partial_percentage(session):
    """The percentage divides by the seven canonical phases, not by the phases attempted.

    A denominator that shrank with progress would report 100% for a half-built service.
    """
    session_id, ws = session
    _make_session(session_id)
    (ws / "spec.md").write_text("# Spec", encoding="utf-8")
    (ws / "user_stories.json").write_text("[]", encoding="utf-8")
    (ws / "architecture.json").write_text("{}", encoding="utf-8")

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.completion_percentage == round(3 / 7 * 100.0, 1)


def test_a_fully_complete_session_reports_completion(session):
    session_id, ws = session
    _make_session(session_id)
    _complete_through_phase_4(ws)
    _complete_phase_5(ws)
    (ws / "src" / "main" / "java" / "GlobalExceptionHandler.java").write_text(
        "@RestControllerAdvice class GlobalExceptionHandler {}", encoding="utf-8"
    )
    (ws / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
    from _support import source_delivery
    source_delivery(session_id, ws)

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.completion_percentage == 100.0
    assert state.next_target_phase == LifecyclePhase.COMPLETED
    assert "completamente sintetizado" in state.next_recommended_action


# ---------------------------------------------------------------------------
# get_project_overview
# ---------------------------------------------------------------------------
def test_the_overview_reports_a_mysql_schema_as_mysql(session):
    """The engine label drives which DDL the operator is told to run, so it must be read
    from the script rather than defaulted."""
    session_id, ws = session
    _make_session(session_id)
    with SessionLocal() as db:
        db.get(GenerationSessionDB, session_id).database_engine = 'MYSQL'
        db.commit()
    (ws / "schema.sql").write_text(
        "CREATE TABLE t (id INT AUTO_INCREMENT PRIMARY KEY);", encoding="utf-8"
    )

    overview = lifecycle.get_project_overview(session_id)

    assert overview.database_engine == "MYSQL"


def test_the_overview_falls_back_to_a_generic_name_without_a_session(session):
    session_id, _ = session
    _make_session(session_id, spec_name="")

    overview = lifecycle.get_project_overview(session_id)

    assert overview.spec_name == "Microservicio"


def test_the_overview_counts_zero_stories_for_a_corrupt_file(session):
    session_id, ws = session
    _make_session(session_id)
    (ws / "user_stories.json").write_text("{broken", encoding="utf-8")

    overview = lifecycle.get_project_overview(session_id)

    assert overview.user_stories_count == 0


def test_an_unreadable_schema_file_does_not_break_the_overview(session):
    """The schema is parsed for the entity count and engine label. A read failure there must
    degrade to the defaults rather than 500 the home screen -- the artifacts are on disk and
    a partially written one is a normal state, not an exceptional one."""
    session_id, ws = session
    _make_session(session_id)
    (ws / "schema.sql").mkdir(parents=True, exist_ok=True)

    overview = lifecycle.get_project_overview(session_id)

    assert overview.entities_count == 0
    assert overview.database_engine == "POSTGRESQL"


def test_the_overview_reports_a_pending_verdict_when_the_audit_cannot_run(session):
    """"Could not audit" must not render as "audited and clean"."""
    session_id, _ = session
    _make_session(session_id)

    def explode(*args, **kwargs):
        raise RuntimeError("sast unavailable")

    lifecycle.audit_workspace = explode

    overview = lifecycle.get_project_overview(session_id)

    assert overview.security_audit_verdict == "PENDING"


def test_tests_are_only_reported_passed_when_phase_five_completed(session):
    session_id, ws = session
    _make_session(session_id)
    _complete_through_phase_4(ws)

    overview = lifecycle.get_project_overview(session_id)

    assert overview.tests_passed is False
