"""Skill document loader tests (feature 014, T002).

The loader is the first thing everything else depends on: injection needs the
document's text, the applier needs to know where its editable region ends, and the
reflector needs the current skill. So its strictness is tested directly.

The rule with teeth is the marker check. Treating a **missing** `SLOW_UPDATE`
marker as an empty protected region would silently unprotect that region, and the
applier would then happily edit it — a typo converting a deliberate constraint into
no constraint. A malformed document must be rejected at load instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.skills.document import SkillDocument, SkillDocumentError, load_skill  # noqa: E402

SKILLS_DIR = REPO_ROOT / "backend" / "app" / "resources" / "skills"
SEED = SKILLS_DIR / "layer_architecture.md"

VALID = """# A Skill

## Granularity
task-level

## When to apply
Whenever the thing happens.

## Rules
1. First rule.
2. Second rule.

<!-- SLOW_UPDATE_START -->
slow content
<!-- SLOW_UPDATE_END -->
"""


def _write(tmp_path: Path, text: str, name: str = "skill.md") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The seed document
# ---------------------------------------------------------------------------
def test_the_seed_skill_loads():
    """T001 authored a 0-byte placeholder; T002 must be able to read it."""
    document = load_skill(SEED)

    assert document.title == "Layer Architecture"
    assert document.granularity == "task-level"
    assert "When to apply" in document.when_to_apply or document.when_to_apply
    assert len(document.rules) >= 5, "the seed should carry a usable rule set"
    assert "repository" in document.editable_text.lower()


def test_the_seed_is_short_enough_to_inject():
    """A skill that dwarfs the instruction it accompanies is not a skill."""
    document = load_skill(SEED)
    assert document.approximate_tokens() < 600, (
        f"the seed is {document.approximate_tokens()} tokens; it should be of the "
        f"order of 250"
    )


# ---------------------------------------------------------------------------
# The protected region
# ---------------------------------------------------------------------------
def test_the_protected_region_is_excluded_from_the_editable_text(tmp_path):
    path = _write(tmp_path, VALID)
    document = load_skill(path)

    assert "slow content" not in document.editable_text, (
        "the protected region leaked into the editable text"
    )
    assert "First rule." in document.editable_text


def test_the_protected_region_is_preserved_on_serialisation(tmp_path):
    path = _write(tmp_path, VALID)
    document = load_skill(path)

    rendered = document.render()

    assert "slow content" in rendered, "serialisation dropped the protected region"
    assert "<!-- SLOW_UPDATE_START -->" in rendered
    assert "<!-- SLOW_UPDATE_END -->" in rendered


def test_editing_the_editable_text_does_not_touch_the_protected_region(tmp_path):
    path = _write(tmp_path, VALID)
    document = load_skill(path)

    document.editable_text = document.editable_text + "\n3. Third rule.\n"
    rendered = document.render()

    assert "Third rule." in rendered
    assert "slow content" in rendered


# ---------------------------------------------------------------------------
# Strict rejection — the rule with teeth
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("missing", ["START", "END"])
def test_a_missing_marker_is_rejected(tmp_path, missing):
    """Treating a missing marker as an empty region would silently unprotect it."""
    text = VALID.replace(f"<!-- SLOW_UPDATE_{missing} -->\n", "").replace(
        f"<!-- SLOW_UPDATE_{missing} -->", ""
    )
    path = _write(tmp_path, text)

    with pytest.raises(SkillDocumentError, match="SLOW_UPDATE"):
        load_skill(path)


def test_markers_in_the_wrong_order_are_rejected(tmp_path):
    text = """# A Skill

## Granularity
task-level

## When to apply
Whenever.

## Rules
1. First rule.

<!-- SLOW_UPDATE_END -->
<!-- SLOW_UPDATE_START -->
"""
    with pytest.raises(SkillDocumentError, match="order"):
        load_skill(_write(tmp_path, text))


@pytest.mark.parametrize(
    "section",
    ["## Granularity", "## When to apply", "## Rules"],
)
def test_a_missing_required_section_is_rejected(tmp_path, section):
    lines = [line for line in VALID.splitlines() if not line.startswith(section)]
    with pytest.raises(SkillDocumentError, match="section"):
        load_skill(_write(tmp_path, "\n".join(lines) + "\n"))


def test_an_empty_file_is_rejected(tmp_path):
    """An empty file is a load error, not a skill with no rules."""
    with pytest.raises(SkillDocumentError):
        load_skill(_write(tmp_path, ""))


def test_a_missing_file_is_rejected(tmp_path):
    with pytest.raises(SkillDocumentError):
        load_skill(tmp_path / "does-not-exist.md")


def test_a_document_with_no_title_is_rejected(tmp_path):
    with pytest.raises(SkillDocumentError):
        load_skill(_write(tmp_path, VALID.replace("# A Skill\n", "")))
