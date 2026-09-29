"""The skill document: parsing, validation, and the protected region (FR-001).

Format, per contracts/skill-document.md:

    # Title
    ## Granularity      (task-level | event-driven)
    ## When to apply
    ## Rules            (numbered)
    <!-- SLOW_UPDATE_START -->
    <!-- SLOW_UPDATE_END -->

The protected region exists so that a future slow/meta update can consolidate a
skill without a fast local edit overwriting it. Nothing writes there in v1, but it
is honoured from the start so that adding the slow update later needs no change to
the edit contract.

**Validation is strict on purpose.** A document missing either marker is rejected
rather than treated as having an empty protected region. Treating it as empty would
silently unprotect the region, and the applier — which rejects edits targeting that
region — would then have nothing to reject.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

PROTECTED_START = "<!-- SLOW_UPDATE_START -->"
PROTECTED_END = "<!-- SLOW_UPDATE_END -->"

#: Directories searched when a skill is named rather than pathed.
SKILLS_DIR = Path(__file__).resolve().parents[1] / "resources" / "skills"

_REQUIRED_SECTIONS = ("## Granularity", "## When to apply", "## Rules")


class SkillDocumentError(RuntimeError):
    """The document is missing, unreadable, or not a valid skill."""


@dataclass
class SkillDocument:
    """A parsed skill. ``editable_text`` is what an edit may touch."""

    title: str
    granularity: str
    when_to_apply: str
    editable_text: str
    protected_text: str = ""
    path: Optional[Path] = None
    _preamble: str = field(default="", repr=False)

    # -- convenience --------------------------------------------------------
    @property
    def rules(self) -> List[str]:
        """The numbered rules in the editable text, in order."""
        found = []
        for line in self.editable_text.splitlines():
            match = re.match(r"^\s*\d+\.\s+(.*)$", line)
            if match:
                found.append(match.group(1).strip())
        return found

    def approximate_tokens(self) -> int:
        """Rough token count (words + punctuation), enough to bound the document."""
        return len(self.render().split())

    def render(self) -> str:
        """Serialise back to markdown, protected region included."""
        body = self.editable_text.rstrip("\n")
        return (
            f"{body}\n\n"
            f"{PROTECTED_START}\n"
            f"{self.protected_text}"
            f"{PROTECTED_END}\n"
        )

    def write(self, path: Optional[Path] = None) -> Path:
        target = Path(path) if path else self.path
        if target is None:
            raise SkillDocumentError("no path to write the skill to")
        target.write_text(self.render(), encoding="utf-8")
        return target


def _split_on_protected(text: str, source: str) -> tuple[str, str]:
    """Return (editable, protected). Raises when the markers are absent or disordered."""
    if PROTECTED_START not in text or PROTECTED_END not in text:
        missing = [
            name
            for name, marker in (("SLOW_UPDATE_START", PROTECTED_START),
                                 ("SLOW_UPDATE_END", PROTECTED_END))
            if marker not in text
        ]
        raise SkillDocumentError(
            f"{source}: missing {', '.join(missing)}. A document without both markers "
            f"is rejected rather than treated as having an empty protected region: "
            f"treating it as empty would silently unprotect the region."
        )

    start_index = text.index(PROTECTED_START)
    end_index = text.index(PROTECTED_END)
    if start_index > end_index:
        raise SkillDocumentError(
            f"{source}: SLOW_UPDATE markers are in the wrong order (END precedes START)"
        )

    editable = text[:start_index]
    protected = text[start_index + len(PROTECTED_START):end_index]
    return editable, protected


def parse_skill(text: str, source: str = "<string>", path: Optional[Path] = None) -> SkillDocument:
    """Parse and validate a skill document."""
    if not text.strip():
        raise SkillDocumentError(f"{source}: the document is empty")

    editable, protected = _split_on_protected(text, source)

    title_match = re.search(r"^#\s+(.+)$", editable, re.MULTILINE)
    if not title_match:
        raise SkillDocumentError(f"{source}: no title (a line beginning '# ')")
    title = title_match.group(1).strip()

    for section in _REQUIRED_SECTIONS:
        if section not in editable:
            raise SkillDocumentError(f"{source}: missing required section {section!r}")

    granularity_match = re.search(
        r"^##\s+Granularity\s*\n+(.+)$", editable, re.MULTILINE
    )
    granularity = granularity_match.group(1).strip() if granularity_match else ""

    when_match = re.search(
        r"^##\s+When to apply\s*\n+(.*?)(?=^##\s|\Z)", editable, re.MULTILINE | re.DOTALL
    )
    when_to_apply = when_match.group(1).strip() if when_match else ""

    return SkillDocument(
        title=title,
        granularity=granularity,
        when_to_apply=when_to_apply,
        editable_text=editable,
        protected_text=protected,
        path=path,
    )


def load_skill(path) -> SkillDocument:
    """Load a skill from a path. Raises SkillDocumentError when it is not valid."""
    resolved = Path(path)
    if not resolved.exists():
        raise SkillDocumentError(f"skill not found: {resolved}")
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillDocumentError(f"cannot read {resolved}: {exc}") from exc
    return parse_skill(text, source=str(resolved), path=resolved)


def resolve_skill_path(name_or_path) -> Path:
    """Resolve a skill by filename or by name without the extension."""
    candidate = Path(name_or_path)
    if candidate.exists():
        return candidate
    if candidate.suffix != ".md":
        named = SKILLS_DIR / f"{candidate.name}.md"
        if named.exists():
            return named
    if not candidate.is_absolute():
        under_skills = SKILLS_DIR / candidate.name
        if under_skills.exists():
            return under_skills
    return candidate
