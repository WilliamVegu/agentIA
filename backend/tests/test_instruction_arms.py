"""The instruction arms must differ in exactly one thing.

If the arms differ anywhere but the Rules section, the comparison measures whatever
else changed. If they differ in nothing, it measures nothing. Both failure modes are
silent: the experiment still produces numbers.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from scripts.instruction_arms import (  # noqa: E402
    ARMS,
    CONTROL_DIR,
    MISMATCHED_SOURCE,
    PROHIBITION_RULES,
    STAGES,
    arm_revision,
    build_arm,
    placebo_rules,
)

_RULES_BLOCK = re.compile(r"## Rules\n(.*?)\n## Output contract", re.DOTALL)


def _build_all(tmp_path: Path) -> dict:
    return {arm: build_arm(arm, tmp_path / arm) for arm in ARMS}


def test_every_arm_loads_and_has_a_distinct_revision(tmp_path):
    """Distinct revisions are the loader's own proof that the arms differ."""
    dirs = _build_all(tmp_path)
    revisions = {arm: arm_revision(d) for arm, d in dirs.items()}

    assert len(set(revisions.values())) == len(ARMS), revisions


def test_only_the_rules_section_differs_from_control(tmp_path):
    """The single variable. Everything else must be byte-identical."""
    dirs = _build_all(tmp_path)

    for stage in STAGES:
        control = (dirs["control"] / f"{stage}.md").read_text(encoding="utf-8")
        head, _, _ = control.partition("## Rules\n")
        for arm in ARMS:
            if arm == "control":
                continue
            other = (dirs[arm] / f"{stage}.md").read_text(encoding="utf-8")
            other_head, _, _ = other.partition("## Rules\n")
            assert other_head == head, f"{arm}/{stage} changed something before Rules"

            control_tail = control.partition("\n## Output contract")[2]
            other_tail = other.partition("\n## Output contract")[2]
            assert other_tail == control_tail, f"{arm}/{stage} changed something after Rules"


def test_the_prohibition_arm_inverts_polarity_rather_than_adding_rules():
    """Every rule must be stated as a prohibition; a positive directive is a miscopy."""
    for stage, body in PROHIBITION_RULES.items():
        numbered = [line for line in body.splitlines() if re.match(r"^\d+\.", line)]
        assert numbered, stage
        assert all("not" in line or "never" in line for line in numbered), (
            f"{stage}: a rule reads as a positive directive, which is the polarity "
            f"this arm is supposed to invert"
        )


def test_the_placebo_is_length_matched_to_the_treatment(tmp_path):
    """An unconstrained text of a different length would confound polarity with budget."""
    dirs = _build_all(tmp_path)

    for stage in STAGES:
        prohibition = _RULES_BLOCK.search(
            (dirs["prohibition"] / f"{stage}.md").read_text(encoding="utf-8")
        ).group(1)
        placebo = _RULES_BLOCK.search(
            (dirs["placebo"] / f"{stage}.md").read_text(encoding="utf-8")
        ).group(1)
        assert abs(len(placebo) - len(prohibition)) <= max(64, len(prohibition) // 20), (
            f"{stage}: placebo {len(placebo)} vs prohibition {len(prohibition)}"
        )


def test_the_placebo_constrains_nothing(tmp_path):
    """It must not accidentally become a second treatment."""
    body = placebo_rules(PROHIBITION_RULES["service"])
    for word in ("must", "never", "shall", "ensure", "always"):
        assert word not in body.lower(), f"the placebo implies a constraint: {word!r}"


def test_the_mismatched_arm_uses_a_different_stages_rules(tmp_path):
    """The literature's actual control: a real rule set on the wrong subject."""
    dirs = _build_all(tmp_path)

    for stage, donor in MISMATCHED_SOURCE.items():
        assert donor != stage
        donor_rules = _RULES_BLOCK.search(
            (CONTROL_DIR / f"{donor}.md").read_text(encoding="utf-8")
        ).group(1)
        mismatched_rules = _RULES_BLOCK.search(
            (dirs["mismatched"] / f"{stage}.md").read_text(encoding="utf-8")
        ).group(1)
        assert mismatched_rules == donor_rules
