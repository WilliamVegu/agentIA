"""Instruction-set loading and revisioning (task T011).

The five generation stages are driven by repository-stored, versioned system
instructions. This module resolves them, validates them, and computes the
instruction-set revision that is stamped onto every generated artifact.

Revision scheme: content-addressed (see contracts/instruction-document.md §2).
The authoritative revision is a SHA-256 digest over the canonicalized map of
stage name -> instruction content. It is deliberately NOT a git commit SHA
(session workspaces are exported and executed without repository history) and
deliberately NOT the human-readable ``VERSION`` label (a hand-maintained label
can drift from the content it names).

``manifest.json`` is EXCLUDED from the digest, so editing the manifest cannot
change the revision recorded against generated artifacts.

Failure policy: loading fails loudly. It never degrades to the deterministic
implementation, because a silent degradation would let a session report success
while emitting pre-migration output, corrupting every SC-001 measurement without
raising an error. This is invariant 11 of contracts/stage-execution.md.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Mapping, Tuple

#: The five generation stages, in execution order.
STAGE_ORDER: Tuple[str, ...] = ("SCAFFOLDER", "DOMAIN", "SERVICE", "CONTROLLER", "TEST")

#: The four level-2 sections every instruction document must carry, in order.
REQUIRED_SECTIONS: Tuple[str, ...] = (
    "Technology contract",
    "Rules",
    "Output contract",
    "Prohibitions",
)

#: Resolved from this file's location: backend/app/resources/instructions.
#: This directory is deliberately distinct from backend/app/resources/skills/,
#: which the skill-injection feature owns.
INSTRUCTIONS_DIR = Path(__file__).resolve().parents[2] / "resources" / "instructions"
MANIFEST_NAME = "manifest.json"
VERSION_NAME = "VERSION"

# Credential shapes. These are assignment-shaped or fixed-prefix patterns, so
# prose such as "do not include API keys" does not match. A match means the
# instruction set is unsafe to load (FR-018, Constitution Principle VI).
_CREDENTIAL_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"gsk_[0-9A-Za-z]{20,}"),
    re.compile(r"\bsk-[0-9A-Za-z_\-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*[\"'][0-9A-Za-z_\-]{16,}[\"']"),
)


class InstructionSetError(RuntimeError):
    """Raised when the instruction set cannot be safely loaded.

    Always fatal: callers must not catch this and fall back to the deterministic
    path. See the module docstring.
    """


@dataclass(frozen=True)
class InstructionSet:
    """A fully resolved, validated instruction set."""

    documents: Mapping[str, str]
    revision: str
    version_label: str = ""
    section_index: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)

    def for_stage(self, stage: str) -> str:
        try:
            return self.documents[stage]
        except KeyError as exc:  # pragma: no cover - guarded at load time
            raise InstructionSetError(f"no instruction document for stage {stage!r}") from exc


def normalize_content(text: str) -> str:
    """Canonicalize instruction content before hashing.

    Line endings are unified and trailing blank lines removed so that a
    checkout with different line-ending settings yields the same revision.
    """
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    return unified.rstrip("\n") + "\n"


def compute_set_revision(documents: Mapping[str, str]) -> str:
    """Digest the canonicalized stage -> content map.

    Stages are visited in sorted order so the digest is independent of mapping
    insertion order.
    """
    digest = hashlib.sha256()
    for stage in sorted(documents):
        digest.update(stage.encode("utf-8"))
        digest.update(b"\0")
        digest.update(normalize_content(documents[stage]).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def _detect_credential(stage: str, content: str) -> None:
    for pattern in _CREDENTIAL_PATTERNS:
        match = pattern.search(content)
        if match:
            raise InstructionSetError(
                f"instruction document for stage {stage!r} appears to contain a credential "
                f"(pattern {pattern.pattern!r}). Refusing to load: instructions are committed "
                f"to the repository and must never carry secrets (FR-018, Constitution VI)."
            )


def _section_headings(content: str) -> Tuple[str, ...]:
    return tuple(re.findall(r"^##\s+(.+?)\s*$", normalize_content(content), re.MULTILINE))


def _validate_sections(stage: str, content: str) -> Tuple[str, ...]:
    headings = _section_headings(content)
    if headings != REQUIRED_SECTIONS:
        raise InstructionSetError(
            f"instruction document for stage {stage!r} has sections {headings!r}; "
            f"exactly {REQUIRED_SECTIONS!r} in that order are required. The revision digest "
            f"and the model payload both depend on this shape "
            f"(contracts/instruction-document.md §3)."
        )
    return headings


def _read_manifest(instructions_dir: Path) -> Dict[str, str]:
    manifest_path = instructions_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise InstructionSetError(f"instruction manifest not found at {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InstructionSetError(f"instruction manifest is not valid JSON: {exc}") from exc

    stages = manifest.get("stages")
    if not isinstance(stages, dict) or not stages:
        raise InstructionSetError(f"instruction manifest at {manifest_path} has no usable 'stages' mapping")
    return stages


def _read_version_label(instructions_dir: Path) -> str:
    """The human-readable label is reporting-only, so a missing VERSION warns
    rather than fails. It is never the identifier recorded in provenance."""
    version_path = instructions_dir / VERSION_NAME
    if not version_path.is_file():
        return ""
    for line in version_path.read_text(encoding="utf-8").splitlines():
        if line.lower().startswith("label:"):
            return line.split(":", 1)[1].strip()
    return ""


def load_instruction_set(instructions_dir: Path | None = None) -> InstructionSet:
    """Resolve, validate, and digest the instruction set.

    :raises InstructionSetError: if any document is missing, the manifest and
        the directory disagree about which documents exist, a document does not
        carry the required section shape, or a document appears to contain a
        credential.
    """
    directory = Path(instructions_dir) if instructions_dir is not None else INSTRUCTIONS_DIR

    if not directory.is_dir():
        raise InstructionSetError(f"instruction directory not found at {directory}")

    manifest_stages = _read_manifest(directory)

    declared = set(manifest_stages)
    expected = set(STAGE_ORDER)

    if declared != expected:
        raise InstructionSetError(
            f"instruction manifest declares stages {sorted(declared)} but the feature has "
            f"five stages {sorted(expected)}. A partially-loaded or concurrently-edited set "
            f"must never be vended as a mixed revision."
        )

    documents: Dict[str, str] = {}
    section_index: Dict[str, Tuple[str, ...]] = {}

    for stage in STAGE_ORDER:
        filename = manifest_stages[stage]
        path = directory / filename
        if not path.is_file():
            raise InstructionSetError(
                f"instruction document for stage {stage!r} is missing: expected {path}. "
                f"Refusing to continue rather than silently falling back to the deterministic "
                f"implementation (invariant 11, contracts/stage-execution.md)."
            )
        content = normalize_content(path.read_text(encoding="utf-8"))

        # An instruction file present on disk but absent from the manifest means
        # the set is not fully described, which is the "inconsistent set" case.
        section_index[stage] = _validate_sections(stage, content)
        _detect_credential(stage, content)
        documents[stage] = content

    # Reverse check: a stray instruction-named markdown file would mean the
    # directory contains documents the revision does not account for.
    accounted = {manifest_stages[s] for s in STAGE_ORDER}
    strays = sorted(
        p.name
        for p in directory.glob("*.md")
        if p.name not in accounted
    )
    if strays:
        raise InstructionSetError(
            f"instruction directory contains markdown not declared in the manifest: {strays}. "
            f"The set would be incompletely described, so the revision could not be trusted."
        )

    return InstructionSet(
        documents=documents,
        revision=compute_set_revision(documents),
        version_label=_read_version_label(directory),
        section_index=section_index,
    )
