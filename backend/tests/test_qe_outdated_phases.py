"""A phase can only be OUTDATED if it was actually built.

Reported from the UI: the banner "Se detectaron modificaciones upstream. Las fases
posteriores están marcadas como OUTDATED" appeared on a first pass through the
lifecycle, after nothing but a routine approval. "Sintetizar con IA" was blamed, but
that handler performs no invalidation at all -- the flag came from
`handleProceedToArchitecture`, which saves the requirements and then calls
`invalidateDownstream(session_id, 'STORIES')`.

That marked **every** phase after STORIES as outdated, unconditionally:

    downstream = [p.value for p in PHASE_ORDER[mod_idx + 1:]]

On a first pass those five phases had no artifacts, so none of them could even display
as OUTDATED -- the status view only shows that state for a COMPLETED phase. The flag
existed solely to raise the banner, and the banner's "Re-sincronizar" button re-runs
generation to DEVOPS_DEPLOY, spending model calls to repair a state that was correct.

The rule is now: *not built* is not *stale*.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.models.session import (  # noqa: E402
    GenerationSessionDB,
    SessionLocal,
    SessionPhase,
    SessionStatus,
)
from app.services import lifecycle_service as lc  # noqa: E402

SESSION_ID = "qe-outdated-session"

#: What each phase needs on disk to count as built. Mirrors the status view.
ARTIFACTS = {
    "spec.md": "# Feature Specification\n",
    "user_stories.json": "[]",
    "architecture.json": "{}",
    "schema.sql": "-- ddl\n",
    "docker-compose.yml": "services: {}\n",
    "security_audit_report.json": "{}",
}


@pytest.fixture
def session(tmp_path, monkeypatch):
    """A session row plus a redirected workspace."""
    monkeypatch.setattr(lc.settings, "WORKSPACE_DIR", str(tmp_path))
    workspace = tmp_path / SESSION_ID
    workspace.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == SESSION_ID).delete()
        db.add(GenerationSessionDB(
            id=SESSION_ID, spec_id="spec-qe", spec_name="note-service",
            status=SessionStatus.QUEUED, phase=SessionPhase.INITIALIZATION,
            current_lifecycle_phase="REQUIREMENTS", lifecycle_mode="GUIDED_STEP",
            repair_attempts=0,
        ))
        db.commit()
    finally:
        db.close()

    yield workspace

    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == SESSION_ID).delete()
        db.commit()
    finally:
        db.close()


def _outdated(session_row_ignored=None) -> list:
    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == SESSION_ID).first()
        import json

        return json.loads(sess.phase_progress_json or "{}").get("outdated_phases", [])
    finally:
        db.close()


# ---------------------------------------------------------------------------
# The reported bug
# ---------------------------------------------------------------------------
def test_a_first_pass_flags_nothing_outdated(session):
    """Requirements approved; no downstream phase has ever run.

    This is the exact sequence that produced the banner. It must produce no flags, and
    therefore no banner.
    """
    (session / "spec.md").write_text(ARTIFACTS["spec.md"], encoding="utf-8")
    (session / "user_stories.json").write_text(ARTIFACTS["user_stories.json"], encoding="utf-8")

    result = lc.mark_downstream_outdated(SESSION_ID, "STORIES")

    assert result == [], (
        "approving requirements marked unbuilt phases as outdated, which is the banner "
        "the user saw without having modified anything"
    )
    assert _outdated() == []


def test_the_helper_agrees_with_the_workspace(session):
    """Only phases with their artifacts present count as built."""
    assert lc.completed_phases(SESSION_ID) == set()

    (session / "spec.md").write_text("x", encoding="utf-8")
    (session / "user_stories.json").write_text("x", encoding="utf-8")
    assert lc.completed_phases(SESSION_ID) == {"REQUIREMENTS", "STORIES"}

    (session / "architecture.json").write_text("x", encoding="utf-8")
    assert lc.completed_phases(SESSION_ID) == {"REQUIREMENTS", "STORIES", "ARCHITECTURE"}


# ---------------------------------------------------------------------------
# Genuine staleness must still be reported
# ---------------------------------------------------------------------------
def test_editing_requirements_after_architecture_was_built_flags_it(session):
    """The case the banner exists for: a real upstream edit with real downstream work."""
    for name in ("spec.md", "user_stories.json", "architecture.json", "schema.sql"):
        (session / name).write_text("x", encoding="utf-8")

    result = lc.mark_downstream_outdated(SESSION_ID, "STORIES")

    assert "ARCHITECTURE" in result
    assert "DATA_MODEL" in result
    assert "REQUIREMENTS" not in result, "an upstream phase cannot be outdated by itself"
    assert "STORIES" not in result, "the modified phase is not downstream of itself"


def test_only_the_phases_after_the_modified_one_are_flagged(session):
    for name in ("spec.md", "user_stories.json", "architecture.json", "schema.sql"):
        (session / name).write_text("x", encoding="utf-8")

    result = lc.mark_downstream_outdated(SESSION_ID, "ARCHITECTURE")

    assert result == ["DATA_MODEL"], (
        "modifying architecture must flag only what derives from it"
    )


def test_a_later_modified_phase_does_not_flag_earlier_ones(session):
    for name in ("spec.md", "user_stories.json", "architecture.json", "schema.sql"):
        (session / name).write_text("x", encoding="utf-8")

    result = lc.mark_downstream_outdated(SESSION_ID, "DATA_MODEL")

    assert result == [], "nothing derives from the data model yet in this workspace"


def test_flags_for_artifacts_that_no_longer_exist_are_dropped(session):
    """A workspace reset must clear the banner, not leave it up with nothing behind it."""
    for name in ("spec.md", "user_stories.json", "architecture.json"):
        (session / name).write_text("x", encoding="utf-8")
    assert lc.mark_downstream_outdated(SESSION_ID, "STORIES") == ["ARCHITECTURE"]

    (session / "architecture.json").unlink()
    assert lc.mark_downstream_outdated(SESSION_ID, "STORIES") == []
    assert _outdated() == []


def test_a_completed_code_phase_needs_both_pom_and_src(session):
    (session / "pom.xml").write_text("x", encoding="utf-8")
    assert "CODE_TESTS" not in lc.completed_phases(SESSION_ID)

    (session / "src").mkdir(exist_ok=True)
    assert "CODE_TESTS" in lc.completed_phases(SESSION_ID)


def test_an_unknown_phase_is_a_no_op(session):
    (session / "architecture.json").write_text("x", encoding="utf-8")
    assert lc.mark_downstream_outdated(SESSION_ID, "NOT_A_PHASE") == []


def test_clearing_resets_the_flags(session):
    for name in ("spec.md", "user_stories.json", "architecture.json"):
        (session / name).write_text("x", encoding="utf-8")
    lc.mark_downstream_outdated(SESSION_ID, "STORIES")
    assert _outdated()

    lc.clear_outdated_phases(SESSION_ID)
    assert _outdated() == []
