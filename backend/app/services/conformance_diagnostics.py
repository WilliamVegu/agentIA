"""The diagnostic channel: deterministic, model-free conformance diagnostics.

This module builds the **instrument**, not the optimizer. It exists first because
CoEvoSkills (COLM 2026) — reflective skill evolution for coding agents, +40.5pp —
ablates to **41.1** when its diagnostic verifier is replaced by an opaque
pass/fail oracle, against **71.1** with it and **42.4** with no evolution at all.
A loop fed only a binary verdict is indistinguishable from no loop. The channel
that carries the *structure* of a failure is therefore the load-bearing part.

It reuses the existing merge layer for both validator families rather than
re-deriving their union, so this cannot disagree with the gate that already
enforces them, and it inherits the attribution and strictest-severity rules for
free.

**Properties that matter for an optimizer input:**

* **Deterministic and model-free.** The same artifacts always produce the same
  report, so a curator's improvement cannot come from the judge drifting.
* **Rule-attributed.** A score says a session went badly; it does not say what to
  change. ``rule_histogram`` is the part a curator can act on.
* **Additive, not a gate.** Nothing here blocks or rejects anything. The gate
  keeps that job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple

from app.orchestrator.stages.compliance import (
    SEVERITY_BLOCKING,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    ComplianceViolation,
    check_dependency_allowlist,
    normalize_verdict,
)

#: Penalty per finding, identical to the weights in
#: ``security_service.evaluate_quality_gate``. Reusing the established weights
#: keeps this instrument commensurate with the quality gate the platform already
#: reports, so the two numbers cannot tell different stories about one session.
_SEVERITY_PENALTY: Dict[str, int] = {
    SEVERITY_CRITICAL: 30,
    # BLOCKING is a severity level of its own in this codebase and is treated as
    # the most severe for scoring purposes, matching its membership of
    # BLOCKING_SEVERITIES.
    SEVERITY_BLOCKING: 30,
    SEVERITY_HIGH: 15,
    SEVERITY_MEDIUM: 5,
    SEVERITY_LOW: 2,
}

#: Assumed weight for a severity this module does not know about. Deliberately
#: non-zero: an unrecognised severity is a gap in this table, and scoring it as
#: harmless would silently under-report.
_UNKNOWN_SEVERITY_PENALTY = 5


@dataclass(frozen=True)
class ConformanceReport:
    """A structured account of what is wrong with an artifact set."""

    #: 0-100, floored. The same scale as the platform's quality gate.
    score: int
    blocking: bool
    violations: Tuple[ComplianceViolation, ...] = ()
    #: severity -> count, for every severity actually observed.
    counts_by_severity: Dict[str, int] = field(default_factory=dict)
    #: rule_id -> count. The actionable signal: which rules recur.
    rule_histogram: Dict[str, int] = field(default_factory=dict)
    evaluated_artifact_count: int = 0

    @property
    def rule_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self.rule_histogram))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "blocking": self.blocking,
            "evaluated_artifact_count": self.evaluated_artifact_count,
            "counts_by_severity": dict(self.counts_by_severity),
            "rule_histogram": dict(self.rule_histogram),
            "violations": [v.to_dict() for v in self.violations],
        }


def score_for(violations: Tuple[ComplianceViolation, ...]) -> int:
    """The conformance score for a set of violations. Floors at zero."""
    penalty = sum(
        _SEVERITY_PENALTY.get(v.severity, _UNKNOWN_SEVERITY_PENALTY) for v in violations
    )
    return max(0, 100 - penalty)


def diagnose(artifacts: Mapping[str, str]) -> ConformanceReport:
    """Evaluate an artifact set and describe what is wrong with it.

    Both validator families are consulted through the shared merge layer, so this
    reports exactly what the stage gate would have reported.

    **Outside-family checks are included deliberately.** The dependency-allowlist
    rule is not part of ``normalize_verdict``; the stage runner calls it separately
    and passes the result in. A diagnostic that omitted it would report a clean
    score for a workspace the gate would have blocked — the instrument would
    overstate conformance, and an optimizer tuned against it would learn to prefer
    unbuildable dependencies. Credential checking, by contrast, already runs inside
    the merge layer and is not repeated here.

    Stage-scoped checks (out-of-scope artifacts, partial-candidate sets) are *not*
    applied: they compare a candidate against the accumulated set within a running
    stage, and a finished artifact set has no such context.
    """
    files = dict(artifacts)

    extra_violations: list = []
    if "pom.xml" in files:
        extra_violations.extend(check_dependency_allowlist(files["pom.xml"], artifact_path="pom.xml"))

    verdict = normalize_verdict(files, extra_violations=extra_violations)
    violations = verdict.violations

    counts_by_severity: Dict[str, int] = {}
    rule_histogram: Dict[str, int] = {}
    for violation in violations:
        counts_by_severity[violation.severity] = counts_by_severity.get(violation.severity, 0) + 1
        rule_histogram[violation.rule_id] = rule_histogram.get(violation.rule_id, 0) + 1

    return ConformanceReport(
        score=score_for(violations),
        blocking=verdict.local_blocking_count > 0
        or any(v.blocking for v in violations),
        violations=violations,
        counts_by_severity=counts_by_severity,
        rule_histogram=rule_histogram,
        evaluated_artifact_count=verdict.evaluated_artifact_count,
    )
