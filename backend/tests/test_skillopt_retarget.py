"""The reflector is fed diagnostics, not a verdict (feature 015 retarget).

Feature 014's loop was fed `build_exit_code`, `terminal_status` and artifact paths.
That is the opaque pass/fail oracle CoEvoSkills ablates to 41.1 against 71.1 for a
diagnostic verifier -- a loop fed only a verdict performs no better than no loop.
These tests pin the retarget: the rules that fired, and the stage that introduced
each one, reach the prompt.

Model-free: nothing here calls a provider.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.models.diagnostics import write_diagnostic_record  # noqa: E402
from app.models.session import (  # noqa: E402
    GenerationSessionDB,
    SessionLocal,
    SessionPhase,
    SessionStatus,
)
from app.skills.document import load_skill  # noqa: E402
from scripts.skillopt.collect import (  # noqa: E402
    aggregate_rule_histogram,
    collect_outcomes,
)
from scripts.skillopt.reflect import build_prompt  # noqa: E402

RETARGET_SESSION = "t015-retarget"

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


@pytest.fixture
def session_with_diagnostics():
    """A blocked session carrying a real rule histogram and stage attribution."""
    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == RETARGET_SESSION).delete()
        db.add(GenerationSessionDB(
            id=RETARGET_SESSION, spec_id="spec-t015-retarget", spec_name="notes-service",
            status=SessionStatus.BLOCKED, phase=SessionPhase.FAILED, repair_attempts=0,
        ))
        db.commit()
    finally:
        db.close()

    write_diagnostic_record(
        RETARGET_SESSION,
        task="minimal",
        score=70,
        raw_penalty=30,
        density=10.0,
        artifact_count=3,
        evaluable=True,
        counts_by_severity={"HIGH": 1},
        rule_histogram={"PRINCIPLE_I_LAYER_ISOLATION": 1},
        findings=[{
            "rule_id": "PRINCIPLE_I_LAYER_ISOLATION",
            "artifact_path": "src/main/java/com/corp/notes/controller/NoteController.java",
            "severity": "HIGH",
        }],
        stages=[{
            "stage": "CONTROLLER", "outcome": "CORRECTED", "request_count": 2,
            "rule_histogram": {"PRINCIPLE_I_LAYER_ISOLATION": 1},
            "counts_by_severity": {"HIGH": 1}, "passed": False,
        }],
    )
    yield RETARGET_SESSION

    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == RETARGET_SESSION).delete()
        db.commit()
    finally:
        db.close()


def test_a_collected_record_carries_the_rule_histogram(session_with_diagnostics):
    result = collect_outcomes(limit=5, session_ids=[session_with_diagnostics])
    record = next(r for r in result["records"] if r["session_id"] == session_with_diagnostics)

    assert record["rule_histogram"] == {"PRINCIPLE_I_LAYER_ISOLATION": 1}, (
        "the collector still reports only a verdict; the rule that fired is missing"
    )
    assert record["counts_by_severity"] == {"HIGH": 1}
    assert record["findings_count"] == 1
    assert record["stages_with_findings"] == [
        {"stage": "CONTROLLER", "rules": {"PRINCIPLE_I_LAYER_ISOLATION": 1}}
    ]
    # And the older verdict signals survive: this is additive, not a replacement.
    assert record["terminal_status"] == "BLOCKED"
    assert "build_exit_code" in record


def test_a_session_without_a_diagnostic_record_still_collects():
    """A record with no attribution is reported as unattributed, not as clean."""
    result = collect_outcomes(limit=5, session_ids=["t015-does-not-exist"])

    for record in result["records"]:
        assert record["rule_histogram"] == {}
        assert record["evaluable"] is False


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def test_recurring_rules_are_aggregated_most_frequent_first():
    failures = [
        {"rule_histogram": {"A": 2, "B": 1}},
        {"rule_histogram": {"A": 1, "C": 5}},
        {"rule_histogram": {}},
    ]

    assert list(aggregate_rule_histogram(failures).items()) == [("C", 5), ("A", 3), ("B", 1)]


def test_aggregation_is_deterministic_on_ties():
    """Ties break by rule id, so a re-run builds the same prompt."""
    first = aggregate_rule_histogram([{"rule_histogram": {"B": 1, "A": 1}}])
    second = aggregate_rule_histogram([{"rule_histogram": {"A": 1, "B": 1}}])

    assert list(first.items()) == list(second.items()) == [("A", 1), ("B", 1)]


# ---------------------------------------------------------------------------
# What the model actually sees
# ---------------------------------------------------------------------------
def test_the_prompt_carries_the_recurring_rules_and_the_stage(tmp_path):
    skill_path = tmp_path / "skill.md"
    skill_path.write_text(SKILL_TEXT, encoding="utf-8")
    skill = load_skill(skill_path)
    failures = [{
        "session_id": "s1",
        "terminal_status": "BLOCKED",
        "build_exit_code": 1,
        "verification_fallback_used": False,
        "rule_histogram": {"PRINCIPLE_I_LAYER_ISOLATION": 2},
        "stages_with_findings": [
            {"stage": "CONTROLLER", "rules": {"PRINCIPLE_I_LAYER_ISOLATION": 2}}
        ],
    }]

    prompt = build_prompt(skill, failures)

    assert "DIAGNOSTIC EVIDENCE" in prompt
    assert "PRINCIPLE_I_LAYER_ISOLATION" in prompt, (
        "the rule that fired did not reach the prompt; the retarget is inert"
    )
    assert "CONTROLLER" in prompt, "the stage attribution did not reach the prompt"
    assert "{{DIAGNOSTICS}}" not in prompt, "an unsubstituted placeholder reached the model"


def test_the_prompt_says_so_when_nothing_was_attributed(tmp_path):
    """A no-verdict session must not be silently dropped or read as clean."""
    skill_path = tmp_path / "skill.md"
    skill_path.write_text(SKILL_TEXT, encoding="utf-8")
    skill = load_skill(skill_path)
    failures = [{
        "session_id": "s1",
        "terminal_status": "BLOCKED",
        "build_exit_code": None,
        "rule_histogram": {},
        "stages_with_findings": [],
    }]

    prompt = build_prompt(skill, failures)

    assert "No rule attribution was recorded" in prompt
    assert "unparseable" in prompt
