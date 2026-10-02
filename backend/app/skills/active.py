"""Resolving the active skill (FR-002, T003).

The active pointer is a separate file naming the skill in use. **Its absence is the
normal state, not an error.**

This module is the only place that decides what "no active skill" means, and it
answers the same way for every way that condition can arise: no pointer, an empty
pointer, an unreadable pointer, or a pointer naming a document that does not exist.
All four yield ``None``.

That matters because this is the first code to read the skills directory on the
generation path. An injection point that raised on absence would break every
existing session the moment it shipped, and the directory is currently empty apart
from placeholders.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.skills.document import SKILLS_DIR, SkillDocument, load_skill, resolve_skill_path

ACTIVE_POINTER = SKILLS_DIR / "active.md"


def active_skill_name(pointer: Optional[Path] = None) -> Optional[str]:
    """The name the pointer names, or ``None`` when there is effectively no pointer."""
    target = Path(pointer) if pointer else ACTIVE_POINTER
    if not target.exists():
        return None
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError:
        return None
    # A pointer may be a bare name or a line with a comment; take the first token.
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return None


def load_active_skill(pointer: Optional[Path] = None) -> Optional[SkillDocument]:
    """Load the active skill, or ``None`` when there is none.

    Never raises for any of the absent-shaped conditions. A pointer that names a
    document which turns out to be **invalid** is also treated as absent rather than
    as a fatal error: a malformed skill should stop the skill from being injected,
    not stop generation from running.
    """
    name = active_skill_name(pointer)
    if not name:
        return None
    resolved = resolve_skill_path(name)
    if not resolved.exists():
        return None
    try:
        return load_skill(resolved)
    except Exception:
        return None
