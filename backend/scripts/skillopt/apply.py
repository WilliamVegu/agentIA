"""Apply bounded edits to a COPY of a skill (FR-005 / T006).

Four operations — `append`, `insert_after`, `replace`, `delete` — capped at
**L_t = 4**. The cap is the textual analogue of a learning rate and is what keeps a
candidate comparable to its predecessor: an unbounded rewrite can erase useful rules
and cannot be attributed to any particular change.

Rejections are **per edit**, never per batch. One malformed proposal from a model
should not discard three good ones, and the rejection reason is the only signal an
operator gets about why an iteration underperformed.

**The original document is never modified here.** Application produces a candidate
in memory; the original changes only when a candidate is accepted, and then by
exactly the applied edit set. Editing in place would mean the skill had already
changed before the gate rejected it, and the "rejection" would be false.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.skills.document import SkillDocument

#: L_t — the maximum number of edits considered per candidate.
MAX_EDITS = 4

OPERATIONS = ("append", "insert_after", "replace", "delete")

REASON_PROTECTED_REGION = "target lies in the protected slow-update region"
REASON_TARGET_NOT_FOUND = "target text not found in the editable region"
REASON_UNKNOWN_OP = "unknown operation"
REASON_MISSING_FIELD = "missing required field"
REASON_CONTENT_FORBIDDEN = "content supplied for a delete"


@dataclass
class ApplyResult:
    candidate: SkillDocument
    applied: List[Dict[str, Any]] = field(default_factory=list)
    rejected: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def rejected_reasons(self) -> List[str]:
        return [entry["reason"] for entry in self.rejected]


def _in_protected_region(document: SkillDocument, target: str) -> bool:
    """Whether `target` occurs only inside the protected region.

    A target that appears in the editable region is editable even if the same text
    also appears in the protected region: the applier edits the first occurrence in
    the editable text, and that is the occurrence the operator can see.
    """
    if target in document.editable_text:
        return False
    return target in document.protected_text


def _reject(edit: Any, reason: str) -> Dict[str, Any]:
    return {"edit": edit, "reason": reason}


def apply_edits(document: SkillDocument, edits: List[Dict[str, Any]]) -> ApplyResult:
    """Apply at most MAX_EDITS edits to a copy of `document`."""
    candidate = SkillDocument(
        title=document.title,
        granularity=document.granularity,
        when_to_apply=document.when_to_apply,
        editable_text=document.editable_text,
        protected_text=document.protected_text,
        path=document.path,
    )
    result = ApplyResult(candidate=candidate)

    for edit in list(edits)[:MAX_EDITS]:
        if not isinstance(edit, dict):
            result.rejected.append(_reject(edit, REASON_UNKNOWN_OP))
            continue

        op = edit.get("op")
        target = edit.get("target")
        content = edit.get("content")

        if op not in OPERATIONS:
            result.rejected.append(_reject(edit, REASON_UNKNOWN_OP))
            continue

        if op == "delete" and content is not None:
            result.rejected.append(_reject(edit, REASON_CONTENT_FORBIDDEN))
            continue

        if op in ("insert_after", "replace", "delete") and not target:
            result.rejected.append(_reject(edit, REASON_MISSING_FIELD))
            continue

        if op in ("append", "insert_after", "replace") and content is None:
            result.rejected.append(_reject(edit, REASON_MISSING_FIELD))
            continue

        # Protected region check comes before the found check so that an edit aimed
        # at the protected region is reported as such rather than as "not found".
        if target and _in_protected_region(candidate, target):
            result.rejected.append(_reject(edit, REASON_PROTECTED_REGION))
            continue

        if op == "append":
            candidate.editable_text = candidate.editable_text.rstrip("\n") + "\n" + str(content) + "\n"
            result.applied.append(edit)
            continue

        if target not in candidate.editable_text:
            result.rejected.append(_reject(edit, REASON_TARGET_NOT_FOUND))
            continue

        if op == "insert_after":
            candidate.editable_text = candidate.editable_text.replace(
                target, f"{target}\n{content}", 1
            )
        elif op == "replace":
            candidate.editable_text = candidate.editable_text.replace(target, str(content), 1)
        elif op == "delete":
            candidate.editable_text = candidate.editable_text.replace(target, "", 1)
        result.applied.append(edit)

    return result
