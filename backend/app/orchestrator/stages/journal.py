"""Correction-journal accumulation (task T015).

The journal is the session's record of what each generation stage did: its
outcome, how many model requests it consumed, and — for every rejected
response — the violation set that caused the rejection and the response itself.
It is retained in full when a session terminates in the human-intervention
state and must never be discarded on exhaustion (FR-011, FR-012).

BUDGETS (independent of the sandbox repair loop — FR-009)
---------------------------------------------------------
* at most 2 correction attempts per stage;
* at most 15 model requests per session (5 stages x (1 initial + 2 corrections)).

A third correction record, or a session total above 15, is a budget violation
and raises ``JournalBudgetError``. It is never silently dropped: a dropped record
would hide the very overrun the budget exists to bound.

CREDENTIAL POLICY
-----------------
The journal records provider and model *identifiers* only. It deliberately does
NOT scan retained model responses for credential-shaped strings, because FR-011
requires those responses to be retained verbatim and a non-compliant response
containing a secret is exactly the kind of response whose rejection must remain
auditable. Credential enforcement for generated artifacts happens at the gate
(FR-018), not by censoring the journal.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Generation modes (mirrors data-model.md §2 GenerationMode).
GENERATION_MODE_MODEL = "MODEL"
GENERATION_MODE_DETERMINISTIC = "DETERMINISTIC"
VALID_GENERATION_MODES: Tuple[str, ...] = (GENERATION_MODE_MODEL, GENERATION_MODE_DETERMINISTIC)

#: Stage outcomes (mirrors data-model.md §2 StageOutcome).
OUTCOME_SUCCEEDED = "SUCCEEDED"
OUTCOME_CORRECTED = "CORRECTED"
OUTCOME_EXHAUSTED = "EXHAUSTED"
OUTCOME_UNUSABLE_RESPONSE = "UNUSABLE_RESPONSE"

#: Hard budgets.
MAX_CORRECTION_ATTEMPTS = 2
MAX_REQUESTS_PER_SESSION = 15
STAGE_COUNT = 5

# Credential shapes. Applied ONLY to the identifier fields, never to retained
# responses — see the module docstring.
_CREDENTIAL_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"gsk_[0-9A-Za-z]{20,}"),
    re.compile(r"\bsk-[0-9A-Za-z_\-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)


class JournalBudgetError(RuntimeError):
    """Raised when a journal budget invariant would be violated."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assert_identifier_safe(field_name: str, value: Optional[str]) -> None:
    if not value:
        return
    for pattern in _CREDENTIAL_PATTERNS:
        if pattern.search(value):
            raise JournalBudgetError(
                f"refusing to record a credential-shaped value in the journal field "
                f"{field_name!r}. The journal records provider and model identifiers only "
                f"(FR-018, Constitution Principle VI)."
            )


def digest_request(request: str) -> str:
    """Stable digest of an issued request, used to detect identical retries."""
    return hashlib.sha256(request.encode("utf-8")).hexdigest()[:16]


def new_journal(
    session_id: str,
    generation_mode: str,
    instruction_set_revision: str = "",
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an empty journal for a session."""
    if generation_mode not in VALID_GENERATION_MODES:
        raise JournalBudgetError(
            f"unknown generation mode {generation_mode!r}; expected one of {VALID_GENERATION_MODES}"
        )
    _assert_identifier_safe("provider", provider)
    _assert_identifier_safe("model", model)
    if generation_mode == GENERATION_MODE_DETERMINISTIC and (provider or model):
        # A DETERMINISTIC session must not be misread as model-generated.
        raise JournalBudgetError(
            "a DETERMINISTIC session must not record a provider or model identifier; "
            "leave both unset rather than filling them with placeholders."
        )
    return {
        "session_id": session_id,
        "generation_mode": generation_mode,
        "instruction_set_revision": instruction_set_revision,
        "provider": provider,
        "model": model,
        "entries": [],
        "total_requests": 0,
    }


def build_correction_attempt(
    attempt_ordinal: int,
    request: str,
    response: str,
    verdict: Optional[Dict[str, Any]],
    outcome: str,
    previous_request_digest: Optional[str] = None,
) -> Dict[str, Any]:
    """Build one ``CorrectionAttemptRecord``.

    :raises JournalBudgetError: if ``attempt_ordinal`` exceeds the cap. A third
        record is a budget violation and must fail loudly rather than be
        appended (T015).
    """
    if attempt_ordinal < 1 or attempt_ordinal > MAX_CORRECTION_ATTEMPTS:
        raise JournalBudgetError(
            f"correction attempt ordinal {attempt_ordinal} is outside 1..{MAX_CORRECTION_ATTEMPTS}. "
            f"A third correction attempt is a budget violation and must not be recorded."
        )
    request_digest = digest_request(request)
    return {
        "attempt_ordinal": attempt_ordinal,
        "request_digest": request_digest,
        "response": response,
        "verdict": verdict,
        "outcome": outcome,
        "timestamp": _now_iso(),
        # Flagged, not suppressed: an identical request yielding an identical
        # rejection means the correction feedback was not actually incorporated.
        "duplicate_of_previous_request": bool(
            previous_request_digest and previous_request_digest == request_digest
        ),
    }


def record_stage_entry(
    journal: Dict[str, Any],
    stage: str,
    outcome: str,
    request_count: int,
    duration_ms: float = 0.0,
    initial_verdict: Optional[Dict[str, Any]] = None,
    correction_attempts: Optional[Sequence[Dict[str, Any]]] = None,
    persisted_artifact_paths: Optional[Sequence[str]] = None,
    corrections_used: int = 0,
) -> Dict[str, Any]:
    """Append one ``StageJournalEntry`` and roll the session request total.

    ``corrections_used`` records how many *correction requests were issued*,
    which is not the same as ``len(correction_attempts)``: a correction that
    succeeds is not a rejected attempt, so it produces no
    ``CorrectionAttemptRecord``, yet the stage still needed a correction and must
    be reported as ``CORRECTED`` rather than ``SUCCEEDED``.

    :raises JournalBudgetError: if the entry would push the session above the
        request budget.
    """
    attempts = list(correction_attempts or [])
    if len(attempts) > MAX_CORRECTION_ATTEMPTS:
        raise JournalBudgetError(
            f"stage {stage!r} recorded {len(attempts)} correction attempts; the cap is "
            f"{MAX_CORRECTION_ATTEMPTS} per stage."
        )
    if corrections_used > MAX_CORRECTION_ATTEMPTS:
        raise JournalBudgetError(
            f"stage {stage!r} issued {corrections_used} correction requests; the cap is "
            f"{MAX_CORRECTION_ATTEMPTS} per stage."
        )
    if request_count < 0:
        raise JournalBudgetError(f"stage {stage!r} reported a negative request count")

    projected = journal.get("total_requests", 0) + request_count
    if projected > MAX_REQUESTS_PER_SESSION:
        raise JournalBudgetError(
            f"recording stage {stage!r} would take the session to {projected} model requests, "
            f"above the documented budget of {MAX_REQUESTS_PER_SESSION} "
            f"(5 stages x (1 initial + {MAX_CORRECTION_ATTEMPTS} corrections))."
        )

    entry = {
        "stage": stage,
        "outcome": outcome,
        "initial_verdict": initial_verdict,
        "correction_attempts": attempts,
        "corrections_used": corrections_used,
        "persisted_artifact_paths": list(persisted_artifact_paths or []),
        "request_count": request_count,
        "duration_ms": float(duration_ms),
    }
    journal.setdefault("entries", []).append(entry)
    journal["total_requests"] = projected
    return entry


def total_requests(journal: Dict[str, Any]) -> int:
    return int(journal.get("total_requests", 0))


def assert_within_budget(journal: Dict[str, Any]) -> None:
    """Fail loudly if the recorded total is above the documented budget."""
    if total_requests(journal) > MAX_REQUESTS_PER_SESSION:
        raise JournalBudgetError(
            f"session {journal.get('session_id')!r} recorded {total_requests(journal)} model "
            f"requests, above the budget of {MAX_REQUESTS_PER_SESSION}."
        )


def duplicate_request_flags(journal: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Entries whose correction request repeated the previous request verbatim."""
    flagged: List[Dict[str, Any]] = []
    for entry in journal.get("entries", []):
        seen: Optional[str] = None
        for attempt in entry.get("correction_attempts", []):
            if attempt.get("duplicate_of_previous_request"):
                flagged.append({"stage": entry.get("stage"), **attempt})
            seen = attempt.get("request_digest")
        if seen is None:
            continue
    return flagged


def stage_entry(journal: Dict[str, Any], stage: str) -> Optional[Dict[str, Any]]:
    for entry in journal.get("entries", []):
        if entry.get("stage") == stage:
            return entry
    return None


def outcome_for_request_count(request_count: int, corrections_used: int) -> str:
    """Derive the stage outcome from how many requests were spent.

    Under the stage-execution contract a DETERMINISTIC stage spends zero
    requests and always succeeds; a MODEL stage spends one initial request, plus
    one per correction, and succeeds on the response that passes.
    """
    if request_count == 0:
        return OUTCOME_SUCCEEDED
    if corrections_used == 0:
        return OUTCOME_SUCCEEDED
    return OUTCOME_CORRECTED
