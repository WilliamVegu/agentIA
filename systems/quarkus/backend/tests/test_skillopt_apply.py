"""Applier tests (feature 014, T013 / US3).

The applier is where a plausible proposal becomes a concrete candidate, so its
rejection rules are the difference between a bounded optimisation and unconstrained
self-editing.

Two rules carry the weight:

* **The protected region is not editable.** It is reserved for slow consolidation;
  a fast local edit overwriting it would collapse the distinction the region exists
  to preserve.
* **A target that is not found is rejected, not fuzzily matched.** Relocating an
  edit would make the candidate differ from the proposed edit set, so the logged
  edits would no longer describe what was tested.

And one property makes rejection meaningful: **the original document is never
modified by application.**
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.skills.document import load_skill  # noqa: E402
from scripts.skillopt.apply import (  # noqa: E402
    MAX_EDITS,
    REASON_CONTENT_FORBIDDEN,
    REASON_PROTECTED_REGION,
    REASON_TARGET_NOT_FOUND,
    REASON_UNKNOWN_OP,
    apply_edits,
)

BASE = """# A Skill

## Granularity
task-level

## When to apply
Whenever.

## Rules
1. First rule.
2. Second rule.
3. Third rule.

<!-- SLOW_UPDATE_START -->
slow consolidated content
<!-- SLOW_UPDATE_END -->
"""


@pytest.fixture
def skill(tmp_path):
    path = tmp_path / "skill.md"
    path.write_text(BASE, encoding="utf-8")
    return load_skill(path)


# ---------------------------------------------------------------------------
# The four operations
# ---------------------------------------------------------------------------
def test_append_adds_to_the_end_of_the_editable_region(skill):
    result = apply_edits(skill, [{"op": "append", "content": "4. Fourth rule."}])

    assert "4. Fourth rule." in result.candidate.render()
    assert result.candidate.render().index("4. Fourth rule.") < result.candidate.render().index("SLOW_UPDATE_START")


def test_insert_after_places_content_immediately_after_the_target(skill):
    result = apply_edits(skill, [{"op": "insert_after", "target": "1. First rule.",
                                  "content": "1b. Inserted rule."}])

    rendered = result.candidate.render()
    assert "1b. Inserted rule." in rendered
    assert rendered.index("1. First rule.") < rendered.index("1b. Inserted rule.")
    assert rendered.index("1b. Inserted rule.") < rendered.index("2. Second rule.")


def test_replace_swaps_the_target(skill):
    result = apply_edits(skill, [{"op": "replace", "target": "2. Second rule.",
                                  "content": "2. Replaced rule."}])

    rendered = result.candidate.render()
    assert "2. Replaced rule." in rendered
    assert "2. Second rule." not in rendered


def test_delete_removes_the_target(skill):
    result = apply_edits(skill, [{"op": "delete", "target": "3. Third rule."}])

    assert "3. Third rule." not in result.candidate.render()
    assert "2. Second rule." in result.candidate.render()


# ---------------------------------------------------------------------------
# Rejection rules
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("op", ["replace", "delete", "insert_after"])
def test_an_edit_targeting_the_protected_region_is_rejected(skill, op):
    edit = {"op": op, "target": "slow consolidated content"}
    if op == "insert_after":
        edit["content"] = "x"
    if op == "replace":
        edit["content"] = "x"

    result = apply_edits(skill, [edit])

    assert result.applied == []
    assert len(result.rejected) == 1
    assert result.rejected[0]["reason"] == REASON_PROTECTED_REGION
    assert "slow consolidated content" in result.candidate.render(), (
        "the protected region was modified"
    )


def test_a_target_that_is_not_found_is_rejected(skill):
    result = apply_edits(skill, [{"op": "replace", "target": "text that is absent",
                                  "content": "x"}])

    assert result.applied == []
    assert result.rejected[0]["reason"] == REASON_TARGET_NOT_FOUND


def test_an_unknown_operation_is_rejected(skill):
    result = apply_edits(skill, [{"op": "rewrite_everything", "content": "x"}])
    assert result.rejected[0]["reason"] == REASON_UNKNOWN_OP


def test_content_supplied_for_delete_is_rejected(skill):
    result = apply_edits(skill, [{"op": "delete", "target": "3. Third rule.",
                                  "content": "ignored?"}])
    assert result.rejected[0]["reason"] == REASON_CONTENT_FORBIDDEN


def test_a_missing_required_field_is_rejected(skill):
    result = apply_edits(skill, [{"op": "insert_after", "content": "x"}])
    assert len(result.rejected) == 1


# ---------------------------------------------------------------------------
# Batch behaviour
# ---------------------------------------------------------------------------
def test_one_bad_edit_does_not_abort_the_batch(skill):
    result = apply_edits(skill, [
        {"op": "replace", "target": "1. First rule.", "content": "1. Kept."},
        {"op": "replace", "target": "absent text", "content": "x"},
        {"op": "append", "content": "4. Also kept."},
    ])

    assert len(result.applied) == 2, "a good edit was discarded because another failed"
    assert len(result.rejected) == 1
    assert "1. Kept." in result.candidate.render()
    assert "4. Also kept." in result.candidate.render()


def test_the_edit_budget_is_capped(skill):
    edits = [{"op": "append", "content": f"extra {n}"} for n in range(MAX_EDITS + 3)]
    result = apply_edits(skill, edits)

    assert MAX_EDITS == 4, "the documented budget is L_t = 4"
    assert len(result.applied) + len(result.rejected) == MAX_EDITS, (
        "the applier exceeded the edit budget"
    )


def test_the_original_document_is_never_modified(skill):
    before = skill.path.read_text(encoding="utf-8")
    apply_edits(skill, [{"op": "append", "content": "4. Fourth rule."}])
    after = skill.path.read_text(encoding="utf-8")

    assert after == before, "application modified the original skill file"


def test_every_edit_rejected_leaves_the_candidate_equal_to_the_original(skill):
    result = apply_edits(skill, [{"op": "replace", "target": "absent", "content": "x"}])

    assert result.candidate.render() == skill.render(), (
        "an all-rejected batch still changed the candidate; the gate would then "
        "compare identical documents and the tie rule would be doing the work"
    )
