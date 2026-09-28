"""Compliance verdict normalization and dependency-allowlist enforcement.

Tasks T014 (verdict adapter) and T049 (allowlist rule). These two write the same
file and are therefore sequential, not parallel — see tasks.md T049.

DESIGN CONSTRAINTS
------------------
1. **Neither existing validator may be modified.** This module invokes
   ``test_analysis_service.analyze_code_compliance`` (family A) and
   ``security_service.scan_architecture_compliance`` (family B) exactly as they
   are and adapts their results.
2. The two families disagree in shape and, for the same rule, in severity:
   family A rates a Lombok violation MEDIUM while family B rates it HIGH. The
   adapter deduplicates by (artifact_path, rule_id) and keeps the **most severe**
   rating, which deliberately *tightens* the gate relative to family A alone
   (contracts/compliance-verdict.md §5).
3. Rule identifiers are derived so that the same constitutional rule reported by
   either family collapses to one key. Family B exposes the principle enum
   directly; family A is mapped from its stable error-summary prefix onto the
   same identifiers. Without this, one violation would be counted twice and the
   severity merge would never fire.

See specs/011-llm-generation-nodes/contracts/compliance-verdict.md.
"""

from __future__ import annotations

import fnmatch
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from app.models.test_analysis import FailureDiagnostic
from app.models.security_quality import StandardsComplianceViolation
from app.services.security_service import scan_architecture_compliance
from app.services.test_analysis_service import test_analysis_service

#: Severity vocabulary of the merged verdict — the union of both families'.
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_BLOCKING = "BLOCKING"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"

#: Ranking used to keep the strictest rating when families disagree.
_SEVERITY_RANK: Mapping[str, int] = {
    SEVERITY_CRITICAL: 4,
    SEVERITY_BLOCKING: 3,
    SEVERITY_HIGH: 2,
    SEVERITY_MEDIUM: 1,
    SEVERITY_LOW: 0,
}

#: Severities that stop an artifact from being persisted (FR-007).
BLOCKING_SEVERITIES = frozenset({SEVERITY_CRITICAL, SEVERITY_BLOCKING, SEVERITY_HIGH})

#: Attribution values (FR-006).
ATTRIBUTION_LOCAL = "LOCAL"
ATTRIBUTION_ACCUMULATED = "ACCUMULATED"

#: Validator-family labels recorded on each violation.
SOURCE_FAMILY_A = "test_analysis_service.analyze_code_compliance"
SOURCE_FAMILY_B = "security_service.scan_architecture_compliance"
SOURCE_ALLOWLIST = "compliance.check_dependency_allowlist"

#: Rule identifier for the dependency-allowlist rule (T049, FR-017).
RULE_DEPENDENCY_NOT_ALLOWED = "DEPENDENCY_NOT_ALLOWED"

#: Rule identifier for the generated-artifact credential rule (FR-018).
RULE_CREDENTIAL_IN_ARTIFACT = "CREDENTIAL_IN_ARTIFACT"

#: Rule identifier for the sample-credential placeholder used in tests.
SEVERITY_OF_CREDENTIAL_RULE = SEVERITY_CRITICAL

#: Resolved from this file: backend/app/resources/dependency_allowlist.json.
#: Deliberately OUTSIDE the instructions directory so that editing the allowlist
#: does not perturb the instruction-set revision digest.
DEFAULT_ALLOWLIST_PATH = Path(__file__).resolve().parents[2] / "resources" / "dependency_allowlist.json"

# Family A carries no rule identifier, so one is derived from its stable
# error-summary prefix. These strings must match the identifiers in family B's
# ConstitutionPrinciple enum for deduplication to work.
_FAMILY_A_RULE_PREFIXES: Tuple[Tuple[str, str], ...] = (
    ("Principle I Violation", "PRINCIPLE_I_LAYER_ISOLATION"),
    ("Principle II Violation", "PRINCIPLE_II_IMMUTABLE_DTOS"),
    ("Principle III Violation", "PRINCIPLE_III_CENTRALIZED_ERRORS"),
    ("Lombok Violation", "STACK_LOMBOK_RESTRICTION"),
)

_VERSION_SELECTOR_RE = re.compile(r"^\s*[\[\(].*[\]\)]\s*$")


# ---------------------------------------------------------------------------
# Verdict model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ComplianceViolation:
    artifact_path: str
    rule_id: str
    severity: str
    message: str
    suggested_fix: Optional[str] = None
    attribution: str = ATTRIBUTION_LOCAL
    contributing_sources: Tuple[str, ...] = ()

    @property
    def blocking(self) -> bool:
        return self.severity in BLOCKING_SEVERITIES

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_path": self.artifact_path,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "blocking": self.blocking,
            "message": self.message,
            "suggested_fix": self.suggested_fix,
            "attribution": self.attribution,
            "contributing_sources": list(self.contributing_sources),
        }


@dataclass(frozen=True)
class ComplianceVerdict:
    passed: bool
    violations: Tuple[ComplianceViolation, ...] = ()
    evaluated_artifact_count: int = 0
    sources: Tuple[str, ...] = ()
    local_blocking_count: int = 0
    accumulated_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "evaluated_artifact_count": self.evaluated_artifact_count,
            "sources": list(self.sources),
            "local_blocking_count": self.local_blocking_count,
            "accumulated_count": self.accumulated_count,
            "violations": [v.to_dict() for v in self.violations],
        }


# ---------------------------------------------------------------------------
# Rule-identifier derivation
# ---------------------------------------------------------------------------
def _family_a_rule_id(finding: FailureDiagnostic) -> str:
    summary = finding.errorSummary or ""
    for prefix, rule_id in _FAMILY_A_RULE_PREFIXES:
        if prefix in summary:
            return rule_id
    category = getattr(finding.category, "value", str(finding.category))
    return f"DIAG-{category}"


def _family_b_rule_id(violation: StandardsComplianceViolation) -> str:
    principle = getattr(violation.principle, "value", str(violation.principle))
    return principle


def _severity_value(raw: Any) -> str:
    value = getattr(raw, "value", str(raw))
    return value if value in _SEVERITY_RANK else SEVERITY_MEDIUM


# ---------------------------------------------------------------------------
# Attribution (FR-006)
# ---------------------------------------------------------------------------
def resolve_attribution(artifact_path: str, stage_scope: Optional[Iterable[str]]) -> str:
    """LOCAL when the offending artifact belongs to the current stage.

    An empty or ``None`` scope means nothing can be attributed locally, so every
    violation is ACCUMULATED. That default is deliberate: it is the safe
    direction, because an ACCUMULATED violation never rejects a stage (FR-006),
    so a missing scope cannot cause a stage to be blamed for a project-wide rule.
    """
    if not stage_scope:
        return ATTRIBUTION_ACCUMULATED
    normalized = artifact_path.replace("\\", "/")
    for pattern in stage_scope:
        candidate = pattern.replace("\\", "/")
        if fnmatch.fnmatch(normalized, candidate):
            return ATTRIBUTION_LOCAL
        # Directory-shaped rules (for example family B's whole-project rule,
        # which reports "src/main/java") and exact paths.
        if candidate.endswith("/") and normalized.startswith(candidate):
            return ATTRIBUTION_LOCAL
        if normalized == candidate:
            return ATTRIBUTION_LOCAL
    return ATTRIBUTION_ACCUMULATED


# ---------------------------------------------------------------------------
# The adapter (T014)
# ---------------------------------------------------------------------------
def normalize_verdict(
    artifacts: Mapping[str, str],
    stage_scope: Optional[Iterable[str]] = None,
    extra_violations: Sequence[ComplianceViolation] = (),
) -> ComplianceVerdict:
    """Validate a candidate/accumulated artifact set with BOTH validator families.

    :param artifacts: workspace-relative path -> content. Per FR-005 this is the
        session's *accumulated* set, not just the current stage's response, so
        whole-project rules can be evaluated.
    :param stage_scope: glob patterns owned by the calling stage, used for
        attribution.
    :param extra_violations: violations produced by checks outside the two
        validator families (for example the dependency allowlist, T049).
    """
    files = dict(artifacts)
    collected: List[ComplianceViolation] = []
    sources: List[str] = []

    # --- Family A: test_analysis_service.analyze_code_compliance ---------------
    # Returns (is_compliant, List[FailureDiagnostic]). The boolean is recorded
    # implicitly through the findings; severity drives blocking, not the flag.
    try:
        _is_compliant, diagnostics = test_analysis_service.analyze_code_compliance(files)
        sources.append(SOURCE_FAMILY_A)
    except Exception as exc:  # noqa: BLE001
        # A validator that cannot run must not be silently treated as "pass":
        # that would let unvalidated artifacts through, defeating FR-004.
        raise RuntimeError(
            f"family A compliance validator failed to run: {type(exc).__name__}: {exc}"
        ) from exc

    for finding in diagnostics or []:
        path = getattr(finding, "filePath", "") or ""
        collected.append(
            ComplianceViolation(
                artifact_path=path,
                rule_id=_family_a_rule_id(finding),
                severity=_severity_value(getattr(finding, "severity", None)),
                message=getattr(finding, "errorSummary", "") or "",
                suggested_fix=getattr(finding, "suggestedFix", None),
                attribution=resolve_attribution(path, stage_scope),
                contributing_sources=(SOURCE_FAMILY_A,),
            )
        )

    # --- Family B: security_service.scan_architecture_compliance --------------
    # Returns List[StandardsComplianceViolation].
    try:
        standards = scan_architecture_compliance(files)
        sources.append(SOURCE_FAMILY_B)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"family B compliance validator failed to run: {type(exc).__name__}: {exc}"
        ) from exc

    for violation in standards or []:
        path = getattr(violation, "filePath", "") or ""
        collected.append(
            ComplianceViolation(
                artifact_path=path,
                rule_id=_family_b_rule_id(violation),
                severity=_severity_value(getattr(violation, "severity", None)),
                message=getattr(violation, "ruleDescription", "") or "",
                suggested_fix=getattr(violation, "suggestedFix", None),
                attribution=resolve_attribution(path, stage_scope),
                contributing_sources=(SOURCE_FAMILY_B,),
            )
        )

    # --- Credential rule (FR-018): the two families do not cover secrets, so ---
    # --- the gate carries this rule itself. See check_artifact_credentials.  ---
    collected.extend(check_artifact_credentials(files, stage_scope))

    collected.extend(extra_violations)

    # --- Deduplicate by (artifact_path, rule_id), keeping the strictest ------
    merged: Dict[Tuple[str, str], ComplianceViolation] = {}
    for violation in collected:
        key = (violation.artifact_path, violation.rule_id)
        existing = merged.get(key)
        if existing is None:
            merged[key] = violation
            continue
        winner, loser = (
            (violation, existing)
            if _SEVERITY_RANK[violation.severity] > _SEVERITY_RANK[existing.severity]
            else (existing, violation)
        )
        merged[key] = ComplianceViolation(
            artifact_path=winner.artifact_path,
            rule_id=winner.rule_id,
            severity=winner.severity,
            message=winner.message or loser.message,
            suggested_fix=winner.suggested_fix or loser.suggested_fix,
            # Severity is resolved strictly; attribution is resolved permissively
            # so a local finding is never demoted to accumulated by a duplicate.
            attribution=(
                ATTRIBUTION_LOCAL
                if ATTRIBUTION_LOCAL in (winner.attribution, loser.attribution)
                else ATTRIBUTION_ACCUMULATED
            ),
            contributing_sources=tuple(sorted(set(winner.contributing_sources) | set(loser.contributing_sources))),
        )

    ordered = tuple(sorted(merged.values(), key=lambda v: (-_SEVERITY_RANK[v.severity], v.artifact_path, v.rule_id)))
    local_blocking = sum(1 for v in ordered if v.blocking and v.attribution == ATTRIBUTION_LOCAL)
    accumulated = sum(1 for v in ordered if v.attribution == ATTRIBUTION_ACCUMULATED)

    return ComplianceVerdict(
        passed=local_blocking == 0,
        violations=ordered,
        evaluated_artifact_count=len(files),
        sources=tuple(sources),
        local_blocking_count=local_blocking,
        accumulated_count=accumulated,
    )


def blocking_local_violations(verdict: ComplianceVerdict) -> Tuple[ComplianceViolation, ...]:
    """The subset that must reject a stage and consume a correction attempt.

    ACCUMULATED violations are excluded per FR-006: a whole-project rule that
    only the accumulated set can satisfy must not reject the stage that cannot
    satisfy it.
    """
    return tuple(v for v in verdict.violations if v.blocking and v.attribution == ATTRIBUTION_LOCAL)


# ---------------------------------------------------------------------------
# Generated-artifact credential rule (FR-018)
# ---------------------------------------------------------------------------
# Neither existing validator family inspects artifacts for secrets — the
# platform's secret scanner is part of the separate security-audit path, not of
# the two constitutional families. FR-018 and SC-003 nevertheless require the
# gate itself to cover this rule, so it is implemented here alongside the
# allowlist rule rather than left to review.
_ARTIFACT_CREDENTIAL_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"gsk_[0-9A-Za-z]{20,}"),
    re.compile(r"\bsk-[0-9A-Za-z_\-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def check_artifact_credentials(
    artifacts: Mapping[str, str],
    stage_scope: Optional[Iterable[str]] = None,
) -> List[ComplianceViolation]:
    """Flag credential-shaped material in a candidate artifact set.

    Severity is CRITICAL, so a match is always blocking regardless of attribution
    resolution: a leaked secret is never acceptable in a persisted artifact.
    """
    violations: List[ComplianceViolation] = []
    for path, content in artifacts.items():
        if not isinstance(content, str):
            continue
        for pattern in _ARTIFACT_CREDENTIAL_PATTERNS:
            if pattern.search(content):
                violations.append(
                    ComplianceViolation(
                        artifact_path=path,
                        rule_id=RULE_CREDENTIAL_IN_ARTIFACT,
                        severity=SEVERITY_OF_CREDENTIAL_RULE,
                        message=(
                            "artifact appears to embed a credential or private key. Generated "
                            "artifacts must never carry secrets (FR-018, Constitution VI)."
                        ),
                        suggested_fix=(
                            "Remove the literal secret and source it from an environment variable "
                            "at runtime."
                        ),
                        attribution=resolve_attribution(path, stage_scope),
                        contributing_sources=("compliance.check_artifact_credentials",),
                    )
                )
                break
    return violations


# ---------------------------------------------------------------------------
# Dependency allowlist enforcement (T049, FR-017)
# ---------------------------------------------------------------------------
def load_dependency_allowlist(path: Optional[Path] = None) -> Dict[str, Any]:
    allowlist_path = Path(path) if path is not None else DEFAULT_ALLOWLIST_PATH
    if not allowlist_path.is_file():
        raise RuntimeError(f"dependency allowlist not found at {allowlist_path} (FR-017 requires it)")
    return json.loads(allowlist_path.read_text(encoding="utf-8"))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _split_coordinates(pom_xml: str):
    """Return (parent, dependencies, plugins, repository_count) from a POM.

    Uses the document's own namespace when present. Only *project-level*
    dependencies are collected — plugin-level dependencies are excluded so a
    plugin's own test dependency cannot be mistaken for a project dependency.
    """
    root = ET.fromstring(pom_xml)
    if "}" in root.tag:
        ns = root.tag.split("}", 1)[0] + "}"
    else:
        ns = ""

    def text_of(element, child_name):
        if element is None:
            return ""
        found = element.find(f"{ns}{child_name}")
        return (found.text or "").strip() if found is not None and found.text else ""

    parent_el = root.find(f"{ns}parent")
    parent = (
        {"groupId": text_of(parent_el, "groupId"), "artifactId": text_of(parent_el, "artifactId"),
         "version": text_of(parent_el, "version")}
        if parent_el is not None
        else None
    )

    dependencies = []
    for dep in root.findall(f"{ns}dependencies/{ns}dependency"):
        dependencies.append({
            "groupId": text_of(dep, "groupId"),
            "artifactId": text_of(dep, "artifactId"),
            "version": text_of(dep, "version"),
            "scope": text_of(dep, "scope"),
        })

    plugins = []
    for plugin in root.findall(f"{ns}build/{ns}plugins/{ns}plugin"):
        plugins.append({
            "groupId": text_of(plugin, "groupId"),
            "artifactId": text_of(plugin, "artifactId"),
            "version": text_of(plugin, "version"),
        })

    repositories = len(root.findall(f"{ns}repositories")) + len(root.findall(f"{ns}pluginRepositories"))
    return parent, dependencies, plugins, repositories


def check_dependency_allowlist(
    pom_xml: str,
    allowlist: Optional[Mapping[str, Any]] = None,
    artifact_path: str = "pom.xml",
    stage_scope: Optional[Iterable[str]] = None,
) -> List[ComplianceViolation]:
    """Flag any build-configuration declaration outside the allowlist.

    Every violation is BLOCKING with rule_id ``DEPENDENCY_NOT_ALLOWED``. The
    check exists because an unlisted artifact cannot be resolved by the hermetic
    offline build, and the resulting failure can be silently absorbed by the
    verification environment's offline-cache fallback — so it must be caught
    before persistence rather than diagnosed after a build (FR-017).
    """
    data = dict(allowlist) if allowlist is not None else load_dependency_allowlist()

    allowed_deps = {
        (d.get("groupId", ""), d.get("artifactId", ""))
        for d in data.get("dependencies", []) or []
    }
    allowed_plugins = {
        (p.get("groupId", ""), p.get("artifactId", ""))
        for p in data.get("build_plugins", []) or []
    }
    allowed_parent = data.get("parent") or {}

    violations: List[ComplianceViolation] = []

    def flag(message: str, fix: str) -> None:
        violations.append(
            ComplianceViolation(
                artifact_path=artifact_path,
                rule_id=RULE_DEPENDENCY_NOT_ALLOWED,
                severity=SEVERITY_BLOCKING,
                message=message,
                suggested_fix=fix,
                attribution=resolve_attribution(artifact_path, stage_scope),
                contributing_sources=(SOURCE_ALLOWLIST,),
            )
        )

    try:
        parent, dependencies, plugins, repositories = _split_coordinates(pom_xml)
    except ET.ParseError as exc:
        violations.append(
            ComplianceViolation(
                artifact_path=artifact_path,
                rule_id="MALFORMED_POM",
                severity=SEVERITY_BLOCKING,
                message=f"generated build configuration is not well-formed XML: {exc}",
                suggested_fix="Emit a valid Maven POM.",
                attribution=resolve_attribution(artifact_path, stage_scope),
                contributing_sources=(SOURCE_ALLOWLIST,),
            )
        )
        return violations

    if parent:
        if (parent.get("groupId"), parent.get("artifactId")) != (
            allowed_parent.get("groupId"), allowed_parent.get("artifactId"),
        ):
            flag(
                f"parent {parent.get('groupId')}:{parent.get('artifactId')} is not the allowed parent "
                f"{allowed_parent.get('groupId')}:{allowed_parent.get('artifactId')}",
                f"Use the {allowed_parent.get('groupId')}:{allowed_parent.get('artifactId')} parent.",
            )

    for dep in dependencies:
        coords = (dep.get("groupId", ""), dep.get("artifactId", ""))
        if coords not in allowed_deps:
            flag(
                f"dependency {coords[0]}:{coords[1]} is not present in the dependency allowlist",
                "Remove the dependency or add it to the allowlist only if it is pre-cached in the "
                "offline build environment.",
            )
        version = dep.get("version", "")
        if version:
            upper = version.upper()
            if upper in ("LATEST", "RELEASE") or "SNAPSHOT" in upper or _VERSION_SELECTOR_RE.match(version):
                flag(
                    f"dependency {coords[0]}:{coords[1]} declares non-deterministic version selector {version!r}",
                    "Let the Spring Boot parent manage the version; never use ranges, SNAPSHOT, LATEST or RELEASE.",
                )

    for plugin in plugins:
        coords = (plugin.get("groupId") or "org.apache.maven.plugins", plugin.get("artifactId", ""))
        if coords not in allowed_plugins:
            flag(
                f"build plugin {coords[0]}:{coords[1]} is not present in the allowlist",
                "Use only the allowlisted build plugins; an unlisted plugin may download at build time "
                "and break the hermetic offline build.",
            )

    if repositories:
        flag(
            "build configuration declares an additional remote repository",
            "Remove the repository declaration; the offline build resolves only from the pre-cached local repository.",
        )

    return violations
