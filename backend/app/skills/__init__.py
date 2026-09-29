"""Skill documents (feature 014).

A skill is a markdown document with a fixed structure and a **protected region**
delimited by explicit slow-update markers. This package owns reading and validating
it, so that injection, the edit applier and the reflector all agree on where the
editable region ends.

The validation here is deliberately strict. The failure it prevents is silent: if a
**missing** marker were treated as an empty protected region, a typo would convert a
deliberate constraint into no constraint, and the applier would then edit a region
that was meant to be reserved for slow consolidation.
"""

from app.skills.document import (
    PROTECTED_END,
    PROTECTED_START,
    SkillDocument,
    SkillDocumentError,
    load_skill,
)
from app.skills.active import active_skill_name, load_active_skill  # noqa: F401

__all__ = [
    "PROTECTED_END",
    "PROTECTED_START",
    "SkillDocument",
    "SkillDocumentError",
    "active_skill_name",
    "load_active_skill",
    "load_skill",
]
