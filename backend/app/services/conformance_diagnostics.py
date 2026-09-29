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

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

from app.orchestrator.stages.compliance import (
    ATTRIBUTION_ACCUMULATED,
    SEVERITY_BLOCKING,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    ComplianceViolation,
    check_dependency_allowlist,
    normalize_verdict,
)

#: Rule ids this module owns -- checks that live outside both validator families
#: because they compare artifacts against each other rather than against a rule set.
RULE_DEPENDENCY_NOT_ALLOWED = "DEPENDENCY_NOT_ALLOWED"
RULE_SCHEMA_ENTITY_MISMATCH = "SCHEMA_ENTITY_MISMATCH"
#: A table exists but is missing a column an entity explicitly maps, or lacks the
#: primary key an @Id requires. The table-name check above cannot see either.
RULE_SCHEMA_COLUMN_MISMATCH = "SCHEMA_COLUMN_MISMATCH"

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


#: The normalisation basis for the size-comparable measure: severity-weighted
#: penalty per this many artifacts.
_MEASURE_BASIS = 100


@dataclass(frozen=True)
class ConformanceReport:
    """A structured account of what is wrong with an artifact set."""

    #: 0-100, floored. The same scale as the platform's quality gate. This is a
    #: RAW weighted count and therefore grows with the size of the artifact set:
    #: do NOT compare it across sets of different sizes. Use ``density`` instead.
    score: int
    blocking: bool
    violations: Tuple[ComplianceViolation, ...] = ()
    #: severity -> count, for every severity actually observed.
    counts_by_severity: Dict[str, int] = field(default_factory=dict)
    #: rule_id -> count. The actionable signal: which rules recur.
    rule_histogram: Dict[str, int] = field(default_factory=dict)
    evaluated_artifact_count: int = 0
    #: Whether a verdict was actually produced. False when no artifact was
    #: examined. This is the third state FR-004 requires: an empty set scores 100
    #: with no findings, which is indistinguishable from *clean* unless it is
    #: flagged, and reporting "nothing to evaluate" as "evaluated and clean" is
    #: precisely the conflation the requirement forbids.
    evaluable: bool = False
    #: The unnormalised severity-weighted penalty behind ``score``.
    raw_penalty: int = 0
    #: The SIZE-COMPARABLE measure: severity-weighted penalty per 100 artifacts.
    #:
    #: Why this exists rather than normalising ``score`` itself: dividing the
    #: score by size would compress it toward 100 and destroy the little dynamic
    #: range the signal has, while ``score`` already has consumers reading its
    #: absolute value. Reporting the density alongside keeps both properties --
    #: existing meanings are unchanged, and size can no longer be mistaken for
    #: quality, because sets carrying findings at the same rate measure the same
    #: at any size (FR-007, SC-009).
    density: float = 0.0
    #: The severity-weighted penalty the baseline already accounts for. Retained so
    #: a reader can see what was forgiven and by how much.
    baseline_penalty: int = 0
    #: **The decision metric.** Absolute severity-weighted penalty of the findings
    #: the baseline does not account for. No denominator, so it cannot be moved by
    #: generating less code OR more files -- only by not introducing a finding.
    new_penalty: int = 0
    #: The minimum artifact count at which a comparison is considered covered. A set
    #: below it has too little surface for the measure to mean anything: a single
    #: file with no findings is not evidence of a clean service.
    size_floor: Optional[int] = None
    #: False when ``evaluated_artifact_count`` is below ``size_floor``. Reported
    #: rather than enforced, so no existing rate silently changes meaning.
    size_floor_met: bool = True
    #: The subset of ``violations`` the baseline does not account for. Carried so a
    #: consumer can name what is new instead of only scoring it.
    new_violations: Tuple[ComplianceViolation, ...] = ()

    @property
    def rule_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self.rule_histogram))

    @property
    def new_rule_ids(self) -> Tuple[str, ...]:
        """Rule ids with at least one finding beyond the baseline."""
        return tuple(sorted({v.rule_id for v in self.new_violations}))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "blocking": self.blocking,
            "evaluated_artifact_count": self.evaluated_artifact_count,
            "counts_by_severity": dict(self.counts_by_severity),
            "rule_histogram": dict(self.rule_histogram),
            "evaluable": self.evaluable,
            "raw_penalty": self.raw_penalty,
            "density": self.density,
            "baseline_penalty": self.baseline_penalty,
            "new_penalty": self.new_penalty,
            "size_floor": self.size_floor,
            "size_floor_met": self.size_floor_met,
            "violations": [v.to_dict() for v in self.violations],
        }


def penalty_for(violations: Tuple[ComplianceViolation, ...]) -> int:
    """The severity-weighted penalty for a set of violations."""
    return sum(
        _SEVERITY_PENALTY.get(v.severity, _UNKNOWN_SEVERITY_PENALTY) for v in violations
    )


def score_for(violations: Tuple[ComplianceViolation, ...]) -> int:
    """The raw conformance score. Floors at zero. NOT comparable across sizes."""
    return max(0, 100 - penalty_for(violations))


def measure_for(violations: Tuple[ComplianceViolation, ...], artifact_count: int) -> float:
    """The size-comparable conformance measure: penalty per 100 artifacts.

    **Retained for continuity, not for decisions.** Every ratio built from findings
    is gameable in one direction or the other: a raw count rewards emitting less
    code, and a per-artifact density -- this function -- rewards emitting *more*,
    because extra files dilute it. Neither is a safe objective, and this one was
    adopted precisely to fix the raw count's flaw, which means it moved the
    exploit rather than removing it.

    The decision metric is :func:`new_penalty`: an absolute penalty over a frozen
    baseline, with no denominator to game. See the module docstring on
    :data:`BaselineSnapshot`.

    When nothing was evaluated there is no exposure to normalise against, so the
    raw penalty is returned rather than dividing by zero: a set with no artifacts
    and findings present must not read as clean.
    """
    penalty = penalty_for(violations)
    if artifact_count <= 0:
        return float(penalty)
    return round(penalty * _MEASURE_BASIS / artifact_count, 2)


#: A frozen reference set of findings: ``rule_id -> permitted count``.
#:
#: **Why the objective is baseline-relative rather than a ratio.** A ratio needs a
#: denominator, and with findings in the numerator every candidate denominator is
#: exploitable: count findings and generating less code wins; divide by artifacts
#: and generating *more* files wins. Removing the denominator removes the exploit.
#: What remains is the absolute severity-weighted penalty of the violations the
#: baseline does not already account for -- which cannot be reduced by changing the
#: size of the artifact set at all, only by not introducing a finding.
BaselineSnapshot = Mapping[str, int]


def baseline_from_histogram(histogram: Mapping[str, int]) -> Dict[str, int]:
    """Freeze a rule histogram as a baseline. Each count is a permitted allowance."""
    return {rule: int(count) for rule, count in histogram.items() if int(count) > 0}


def violations_beyond_baseline(
    violations: Tuple[ComplianceViolation, ...],
    baseline: Optional[BaselineSnapshot],
) -> Tuple[ComplianceViolation, ...]:
    """The violations exceeding the baseline's per-rule allowance.

    The allowance is consumed in iteration order, so the result is deterministic for
    a given violation tuple. An absent or empty baseline permits nothing, which is
    the conservative direction: an unknown baseline must not silently forgive a
    finding.
    """
    if not baseline:
        return tuple(violations)

    remaining = dict(baseline)
    beyond: list = []
    for violation in violations:
        allowed = remaining.get(violation.rule_id, 0)
        if allowed > 0:
            remaining[violation.rule_id] = allowed - 1
            continue
        beyond.append(violation)
    return tuple(beyond)


def new_penalty(
    violations: Tuple[ComplianceViolation, ...],
    baseline: Optional[BaselineSnapshot] = None,
) -> int:
    """The absolute penalty of findings the baseline does not already account for."""
    return penalty_for(violations_beyond_baseline(violations, baseline))



def stage_attribution(journal: Optional[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Attribute findings to the stage that introduced them (FR-006, SC-002).

    Reads the ``initial_verdict`` already carried on each stage journal entry --
    the verdict on that stage's *first* candidate, before any correction. That is
    what makes it an attribution of introduction rather than of persistence: a
    violation the stage fixed on its second attempt still belongs to it, and
    reporting only the final verdict would hide the mistake entirely.

    This is read, not recomputed. The platform already produced these verdicts
    during the run; nothing here re-evaluates an artifact.

    **It adds resolution, not evidence.** The number of distinct tasks is
    unchanged by it, and it must never be counted as more observations (FR-013).
    """
    if not journal:
        return []

    attributed: List[Dict[str, Any]] = []
    for entry in journal.get("entries", []) or []:
        if not isinstance(entry, Mapping):
            continue
        # A stage whose first candidate never parsed carries NO verdict at all.
        # That is a third state, not a pass: rendering it as ``passed`` turned a
        # session in which every stage was rejected into one that reads as clean
        # -- the conflation FR-004 forbids, one level down. It is also the
        # fabricated-looking shape the store actually held: five EXHAUSTED stages,
        # every one reported ``passed``, every rule histogram empty.
        raw_verdict = entry.get("initial_verdict")
        verdict: Optional[Mapping[str, Any]] = (
            raw_verdict if isinstance(raw_verdict, Mapping) else None
        )
        violations = (verdict or {}).get("violations") or []
        histogram: Dict[str, int] = {}
        severities: Dict[str, int] = {}
        for violation in violations:
            if not isinstance(violation, Mapping):
                continue
            rule_id = str(violation.get("rule_id") or "UNKNOWN")
            histogram[rule_id] = histogram.get(rule_id, 0) + 1
            severity = str(violation.get("severity") or "UNKNOWN")
            severities[severity] = severities.get(severity, 0) + 1
        # ``None`` means "no verdict was produced"; it is neither True nor False.
        passed: Optional[bool] = (
            None if verdict is None else bool(verdict.get("passed", not violations))
        )
        attributed.append({
            "stage": str(entry.get("stage") or "UNKNOWN"),
            "outcome": entry.get("outcome"),
            "request_count": entry.get("request_count"),
            "rule_histogram": histogram,
            "counts_by_severity": severities,
            "passed": passed,
        })
    return attributed


def check_schema_matches_entities(files: Mapping[str, str]) -> list:
    """Every table the JPA entities declare must exist in the generated ``schema.sql``.

    This is a cross-artifact check, which is why it lives here and not in a validator
    family: it compares two generated files against each other, not the artifacts
    against a rule set.

    **Why it exists.** An external review of real generated output found a service
    whose ``schema.sql`` created a table ``items`` while its JPA entity mapped
    ``orders``. ``docker-compose.yml`` mounts ``schema.sql`` into
    ``/docker-entrypoint-initdb.d/``, so under ``ddl-auto: validate`` the application
    refuses to start against the database its own schema just created. Nothing in the
    pipeline compared the two files, so nothing noticed.

    Attribution is ACCUMULATED: no single stage owns both files, and a stage must not
    be rejected for a mismatch it could not have seen. That also makes this rule part
    of the channel that survives into a saved artifact set -- which is the only
    channel a conformance measure can vary on.
    """
    schema = files.get("schema.sql")
    if not schema:
        return []                       # nothing to compare; not a finding

    declared = set(re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?(\w+)",
                              schema, re.IGNORECASE))
    if not declared:
        return []

    violations = []
    for path, content in files.items():
        if not path.endswith(".java"):
            continue
        for table in re.findall(r'@Table\s*\(\s*name\s*=\s*[\'"]([^\'"]+)[\'"]', content):
            if table.lower() in {name.lower() for name in declared}:
                continue
            violations.append(ComplianceViolation(
                artifact_path="schema.sql",
                rule_id=RULE_SCHEMA_ENTITY_MISMATCH,
                severity=SEVERITY_HIGH,
                message=(
                    f"Entity in {path} maps table '{table}', but schema.sql does not "
                    f"create it (it creates: {', '.join(sorted(declared)) or 'none'}). "
                    f"The service will fail to start against its own schema under "
                    f"ddl-auto=validate, and the docker-compose init script will build "
                    f"the wrong tables."
                ),
                suggested_fix=(
                    f"Emit CREATE TABLE IF NOT EXISTS {table} (...) in schema.sql with "
                    f"the entity's columns, or remove the @Table name so the default "
                    f"naming applies to both."
                ),
                attribution=ATTRIBUTION_ACCUMULATED,
                contributing_sources=("conformance_diagnostics.check_schema_matches_entities",),
            ))
    return violations


_CREATE_TABLE_BLOCK_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?(\w+)[\"`]?\s*\((.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
_EXPLICIT_COLUMN_RE = re.compile(r"@Column\s*\(\s*name\s*=\s*[\'\"]([^\'\"]+)[\'\"]")
_MAPPED_TABLE_RE = re.compile(r"@Table\s*\(\s*name\s*=\s*[\'\"](\w+)[\'\"]")
_HAS_ID_RE = re.compile(r"@Id\b")


def _schema_tables(schema: str) -> Dict[str, Dict[str, Any]]:
    """``table -> {"columns": set, "primary_key": bool}`` from the generated DDL."""
    tables: Dict[str, Dict[str, Any]] = {}
    for table, body in _CREATE_TABLE_BLOCK_RE.findall(schema):
        columns = set()
        for line in body.splitlines():
            stripped = line.strip().rstrip(",")
            if not stripped:
                continue
            first = stripped.split()[0].strip('"`')
            if first.upper() in {"PRIMARY", "FOREIGN", "UNIQUE", "CONSTRAINT", "INDEX", "KEY"}:
                continue
            columns.add(first)
        tables[table.lower()] = {
            "columns": columns,
            "primary_key": "PRIMARY KEY" in body.upper(),
        }
    return tables


def check_schema_columns_match_entities(files: Mapping[str, str]) -> list:
    """Columns an entity explicitly maps must exist in the table that maps it.

    The table-name check next door cannot see this: a table can exist, carry the
    right name, and still lack the columns the entity declares -- which fails
    identically under ``ddl-auto=validate`` and is invisible to every unit test the
    generator writes, because those mock the repository.

    **Deliberately narrow, to stay false-positive free.** Only *explicit*
    ``@Column(name = ...)`` mappings are compared, plus the presence of a primary
    key when the entity declares ``@Id``. A bare field is not checked, because its
    column name depends on the persistence provider's naming strategy and guessing
    it would produce findings that are wrong rather than findings that are useful.
    A rule that cries wolf is worse than no rule: it teaches the operator to ignore
    the channel.

    Attribution is ACCUMULATED, for the same reason as the table-name check: no
    single stage owns both the entity and the DDL, and a stage must not be rejected
    for a mismatch it could not have seen.
    """
    schema = files.get("schema.sql")
    if not schema:
        return []

    tables = _schema_tables(schema)
    if not tables:
        return []

    violations = []
    for path, content in sorted(files.items()):
        if not path.endswith(".java"):
            continue
        mapped = _MAPPED_TABLE_RE.search(content)
        if not mapped:
            continue
        table = mapped.group(1).lower()
        declared = tables.get(table)
        if declared is None:
            continue  # the table-name rule already reports this

        for column in sorted(set(_EXPLICIT_COLUMN_RE.findall(content))):
            if column.lower() in {c.lower() for c in declared["columns"]}:
                continue
            violations.append(ComplianceViolation(
                artifact_path="schema.sql",
                rule_id=RULE_SCHEMA_COLUMN_MISMATCH,
                severity=SEVERITY_HIGH,
                message=(
                    f"Entity in {path} maps {table}.{column}, but schema.sql's "
                    f"{table} declares only: "
                    f"{', '.join(sorted(declared['columns'])) or 'no columns'}. "
                    f"Under ddl-auto=validate the application will not start against "
                    f"the schema it generated."
                ),
                suggested_fix=(
                    f"Add the column {column} to CREATE TABLE {table} in schema.sql, "
                    f"or drop the explicit @Column name so the provider's naming "
                    f"strategy applies to both."
                ),
                attribution=ATTRIBUTION_ACCUMULATED,
                contributing_sources=(
                    "conformance_diagnostics.check_schema_columns_match_entities",
                ),
            ))

        if _HAS_ID_RE.search(content) and not declared["primary_key"]:
            violations.append(ComplianceViolation(
                artifact_path="schema.sql",
                rule_id=RULE_SCHEMA_COLUMN_MISMATCH,
                severity=SEVERITY_HIGH,
                message=(
                    f"Entity in {path} declares an @Id, but schema.sql's {table} "
                    f"declares no PRIMARY KEY. The entity cannot be loaded or "
                    f"persisted against this table."
                ),
                suggested_fix=(
                    f"Declare a PRIMARY KEY on {table}'s identifier column in schema.sql."
                ),
                attribution=ATTRIBUTION_ACCUMULATED,
                contributing_sources=(
                    "conformance_diagnostics.check_schema_columns_match_entities",
                ),
            ))
    return violations


def record_session_diagnostics(
    session_id: str,
    final_state: Mapping[str, Any],
    *,
    task: Optional[str] = None,
) -> bool:
    """Persist one session's diagnostic record from its final state (FR-001).

    **The single writer.** Every terminal path must call it, including the blocked
    ones -- a blocked session is the one most worth diagnosing. It exists as one
    function rather than a copy per path because the copies are how a path silently
    ends up recording nothing: the sequential pipeline's stage-exhaustion branch set
    an in-memory status, returned, and wrote neither a terminal session state nor a
    record, while the graph path wrote both.

    Never raises: a diagnostics failure must not prevent a session's own terminal
    record from being written. The boolean return keeps the failure visible instead
    of silent, which is the mistake feature 014's write path made.
    """
    from app.models.diagnostics import write_diagnostic_record

    try:
        report = diagnose(dict(final_state.get("generated_files") or {}))
        metrics = final_state.get("test_metrics") or {}
        # `unverified` means verification DID NOT HAPPEN, not merely "it fell back".
        # A session that blocks during generation never reaches the sandbox, so it
        # carries no metrics at all -- and deriving the flag from `fallback_used`
        # alone left it False, reporting such a session as VERIFIED. The first real
        # baseline's report counted exactly one "verified" session whose build never
        # ran, and quoted its score as the corpus's only conformance number.
        verification_ran = bool(metrics)
        unverified = (not verification_ran) or bool(metrics.get("fallback_used", False))
        return write_diagnostic_record(
            session_id,
            task=task,
            score=report.score,
            raw_penalty=report.raw_penalty,
            density=report.density,
            artifact_count=report.evaluated_artifact_count,
            evaluable=report.evaluable,
            # FR-005: excluded from evidence whatever the terminal status says.
            unverified=unverified,
            counts_by_severity=report.counts_by_severity,
            rule_histogram=report.rule_histogram,
            findings=[v.to_dict() for v in report.violations],
            stages=stage_attribution(final_state.get("generation_journal")),
        )
    except Exception:
        return False


def diagnose(
    artifacts: Mapping[str, str],
    *,
    baseline: Optional[BaselineSnapshot] = None,
    min_artifacts: Optional[int] = None,
) -> ConformanceReport:
    """Evaluate an artifact set and describe what is wrong with it.

    Both validator families are consulted through the shared merge layer, so this
    reports exactly what the stage gate would have reported.

    ``baseline`` freezes the findings a run is *expected* to carry; only the excess
    is charged (:func:`new_penalty`). ``min_artifacts`` states the artifact count
    below which the measure is not considered covered, and is reported as
    ``size_floor_met`` rather than enforced, so no existing consumer's rate changes
    meaning without it being visible.

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
    # Cross-artifact consistency, like the allowlist above: outside both validator
    # families because it compares two generated files rather than applying a rule.
    extra_violations.extend(check_schema_matches_entities(files))
    extra_violations.extend(check_schema_columns_match_entities(files))

    verdict = normalize_verdict(files, extra_violations=extra_violations)
    violations = verdict.violations

    counts_by_severity: Dict[str, int] = {}
    rule_histogram: Dict[str, int] = {}
    for violation in violations:
        counts_by_severity[violation.severity] = counts_by_severity.get(violation.severity, 0) + 1
        rule_histogram[violation.rule_id] = rule_histogram.get(violation.rule_id, 0) + 1

    beyond = violations_beyond_baseline(violations, baseline)
    artifact_count = verdict.evaluated_artifact_count

    return ConformanceReport(
        score=score_for(violations),
        evaluable=artifact_count > 0,
        raw_penalty=penalty_for(violations),
        density=measure_for(violations, artifact_count),
        baseline_penalty=penalty_for(violations) - penalty_for(beyond),
        new_penalty=penalty_for(beyond),
        new_violations=beyond,
        size_floor=min_artifacts,
        size_floor_met=(min_artifacts is None or artifact_count >= min_artifacts),
        blocking=verdict.local_blocking_count > 0
        or any(v.blocking for v in violations),
        violations=violations,
        counts_by_severity=counts_by_severity,
        rule_histogram=rule_histogram,
        evaluated_artifact_count=artifact_count,
    )
