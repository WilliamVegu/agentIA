"""Collect recorded session outcomes as the training evidence (FR-003 / T005).

Reads the most recent sessions and returns one record per session. This is the
**training** side of the loop, and it is disjoint from the gate's evidence by
construction: these sessions already happened, under the *previous* skill, so they
cannot contain the candidate.

Two classifications matter:

* **No failures is not no sessions.** `NO_FAILURES` means the skill is working;
  `NO_SESSIONS` means there is nothing to learn from. The orchestrator treats them
  differently, and both stop before calling a model.
* **A fallback-marked session is a failure**, however its terminal status reads.
  Feature 012 established that a synthetic verification is not a success.

**A note on `build_exit_code`.** The session table does not store a build exit code.
The closest persisted signal is the verification metrics' pass flag, so the exit
code is **derived** from it: zero when the metrics report a pass, non-zero when they
report a failure, and `None` when no metrics were persisted. It is reported as
derived rather than presented as a recorded value.

**The diagnostics are the point (feature 015 retarget).** A verdict — exit code,
terminal status, artifact paths — says *that* a session went badly. It does not say
*what to change*, and a loop fed only a verdict is measurably worthless: CoEvoSkills
ablates to 41.1 with an opaque oracle against 71.1 with a diagnostic verifier and
42.4 with no loop at all. So every record now carries the session's recorded
``rule_histogram`` and per-stage attribution, read from the diagnostic store. That is
the signal the reflector can act on, and it was already being computed and discarded.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from app.models.diagnostics import read_diagnostic_record
from app.models.session import GenerationSessionDB, SessionLocal

#: Collection outcomes. Distinct because the orchestrator reports them differently.
COLLECTION_OK = "OK"
COLLECTION_NO_SESSIONS = "NO_SESSIONS"
COLLECTION_NO_FAILURES = "NO_FAILURES"

DEFAULT_LIMIT = 12


def _provenance_paths(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        records = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(records, list):
        return []
    paths = []
    for record in records:
        if isinstance(record, dict) and record.get("artifact_path"):
            paths.append(str(record["artifact_path"]))
    return paths


def _verification(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _derive_exit_code(metrics: Dict[str, Any]) -> Optional[int]:
    """Derive a build exit code from the persisted verification metrics.

    Derived, not recorded: the session table has no exit-code column. `None` when
    nothing was persisted, so an unknown outcome is never reported as a zero.
    """
    if "allPassed" not in metrics:
        return None
    return 0 if metrics.get("allPassed") else 1


def _diagnostics(session_id: str) -> Dict[str, Any]:
    """The session's recorded diagnostic evidence, or an empty mapping.

    Never raises: a session with no record (or an unreadable store) still yields an
    outcome record. It simply carries no rule attribution, which the aggregate
    reports as un-attributed rather than as clean.
    """
    try:
        record = read_diagnostic_record(session_id)
    except Exception:
        return {}
    if not record:
        return {}
    return {
        "evaluable": bool(record.get("evaluable")),
        "density": float(record.get("density") or 0.0),
        "rule_histogram": dict(record.get("rule_histogram") or {}),
        "counts_by_severity": dict(record.get("counts_by_severity") or {}),
        "findings_count": len(record.get("findings") or []),
        # Which stage first introduced each rule. The attribution that makes a
        # proposal targetable: "the controller keeps reaching into the repository"
        # is actionable, "the build failed" is not.
        "stages_with_findings": [
            {
                "stage": str(entry.get("stage")),
                "rules": dict(entry.get("rule_histogram") or {}),
            }
            for entry in (record.get("stages") or [])
            if isinstance(entry, dict) and entry.get("rule_histogram")
        ],
    }


def aggregate_rule_histogram(records: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    """Recurring rules across a set of outcome records, most frequent first.

    Insertion-ordered by descending count so the prompt's most relevant signal is at
    the top and the ordering is deterministic (ties broken by rule id).
    """
    totals: Dict[str, int] = {}
    for record in records:
        histogram = record.get("rule_histogram") or {}
        if not isinstance(histogram, dict):
            continue
        for rule_id, count in histogram.items():
            try:
                totals[str(rule_id)] = totals.get(str(rule_id), 0) + int(count)
            except (TypeError, ValueError):
                continue
    return dict(sorted(totals.items(), key=lambda item: (-item[1], item[0])))


def collect_outcomes(
    limit: int = DEFAULT_LIMIT,
    session_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Collect the most recent `limit` sessions, ordered deterministically.

    `session_ids` narrows the pool; production passes nothing and takes whatever is
    newest. Ordering is by session identifier so that a re-run collects the same set
    in the same order — the loop's reproducibility depends on it.
    """
    db = SessionLocal()
    try:
        query = db.query(GenerationSessionDB)
        if session_ids is not None:
            query = query.filter(GenerationSessionDB.id.in_(list(session_ids)))
        rows = query.all()
    finally:
        db.close()

    ordered = sorted(rows, key=lambda row: row.id or "")[: max(0, int(limit))]

    records: List[Dict[str, Any]] = []
    for row in ordered:
        metrics = _verification(getattr(row, "verification_metrics_json", None))
        status = getattr(row.status, "value", row.status)
        records.append({
            "session_id": row.id,
            "spec_id": row.spec_id,
            "artifact_paths": _provenance_paths(getattr(row, "artifact_provenance_json", None)),
            "build_exit_code": _derive_exit_code(metrics),
            "terminal_status": str(status),
            "verification_fallback_used": bool(metrics.get("fallback_used", False)),
            # The retarget: the rules that fired, not just that something did.
            **_diagnostics(row.id),
        })

    if not records:
        return {"status": COLLECTION_NO_SESSIONS, "records": [], "failures": []}

    failures = [record for record in records if _is_failure(record)]
    if not failures:
        return {"status": COLLECTION_NO_FAILURES, "records": records, "failures": []}

    return {"status": COLLECTION_OK, "records": records, "failures": failures}


def _is_failure(record: Dict[str, Any]) -> bool:
    """A session the skill failed to carry to a genuine, verified success."""
    if record.get("verification_fallback_used"):
        return True
    if record.get("terminal_status") != "COMPLETED":
        return True
    exit_code = record.get("build_exit_code")
    return exit_code is not None and exit_code != 0
