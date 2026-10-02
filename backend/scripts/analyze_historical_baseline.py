#!/usr/bin/env python3
"""
Historical Baseline Analysis Utility for AgentIA Skill Injection Pilot.

Inspects historical generation session metadata and logs from studio.db in strict
read-only mode. Computes pass/fail distribution, repair-loop exhaustion rates,
error taxonomy, constitutional violations, and domain triage recommendations.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ==============================================================================
# Domain Taxonomy & Signatures
# ==============================================================================

CANDIDATE_DOMAINS = [
    {
        "key": "jakarta_namespace",
        "name": "Jakarta EE 10 Namespace Migration",
        "patterns": [
            re.compile(r"package\s+javax\.(?:persistence|validation|servlet|annotation)"),
            re.compile(r"import\s+javax\.(?:persistence|validation|servlet|annotation)"),
            re.compile(r"javax\.(?:persistence|validation|servlet|annotation)\b"),
        ],
        "default_verdict": "deterministic-fixer appropriate",
        "rationale_fixer": (
            "Mechanical, regular package import replacements (javax.* -> jakarta.*) "
            "best handled by AST/regex deterministic post-processor."
        ),
        "rationale_skill": "Requires contextual import reasoning across multi-module hierarchy.",
    },
    {
        "key": "layer_architecture",
        "name": "Architectural Layer Isolation (Principle I)",
        "patterns": [
            re.compile(r"Principle I\s*\(Layer Isolation\)", re.IGNORECASE),
            re.compile(r"accesses\s+\w*Repository\s+directly", re.IGNORECASE),
            re.compile(r"Controllers\s+MUST\s+NOT\s+access\s+Repositories", re.IGNORECASE),
            re.compile(r"JPA\s+entit(?:y|ies)\s+directly", re.IGNORECASE),
            re.compile(r"layer\s+isolation\s+violation", re.IGNORECASE),
        ],
        "default_verdict": "skill-layer appropriate",
        "rationale_fixer": "Simple layer violations with clear 1-to-1 extraction rules.",
        "rationale_skill": (
            "Semantic architectural violations requiring service method extraction, "
            "business logic refactoring, and multi-file reasoning."
        ),
    },
    {
        "key": "exception_handling",
        "name": "Centralized Error Handling (Principle III)",
        "patterns": [
            re.compile(r"Principle III\s*\(Centralized Exception Handling\)", re.IGNORECASE),
            re.compile(r"inline\s+try-catch", re.IGNORECASE),
            re.compile(r"@RestControllerAdvice", re.IGNORECASE),
            re.compile(r"ProblemDetails", re.IGNORECASE),
            re.compile(r"ApiErrorRecord", re.IGNORECASE),
        ],
        "default_verdict": "skill-layer appropriate",
        "rationale_fixer": "Standardized boilerplate replacement for generic exception handlers.",
        "rationale_skill": (
            "Domain-specific exception mapping requiring semantic definition of business "
            "exceptions, status codes, and @RestControllerAdvice handlers."
        ),
    },
    {
        "key": "maven_pom",
        "name": "Maven POM & Offline Dependency Management (Principle IV)",
        "patterns": [
            re.compile(r"Non-resolvable\s+parent\s+POM", re.IGNORECASE),
            re.compile(r"Could\s+not\s+resolve\s+dependencies", re.IGNORECASE),
            re.compile(r"BUILD FAILURE.*pom\.xml", re.IGNORECASE | re.DOTALL),
            re.compile(r"Plugin\s+execution\s+failed", re.IGNORECASE),
            re.compile(r"Principle IV\s*\(Offline Determinism\)", re.IGNORECASE),
        ],
        "default_verdict": "deterministic-fixer appropriate",
        "rationale_fixer": (
            "XML dependency verification and offline plugin fixes are mechanical and "
            "best handled by deterministic POM injectors."
        ),
        "rationale_skill": "Complex multi-dependency conflict resolution requiring build graph analysis.",
    },
    {
        "key": "mockito_tests",
        "name": "Mockito Test Synthesis & Stubbing Correctness",
        "patterns": [
            re.compile(r"UnnecessaryStubbingException", re.IGNORECASE),
            re.compile(r"Strictness\.STRICT_STUBS", re.IGNORECASE),
            re.compile(r"Wanted\s+but\s+not\s+invoked", re.IGNORECASE),
            re.compile(r"Arguments\s+are\s+different!", re.IGNORECASE),
            re.compile(r"org\.mockito\.", re.IGNORECASE),
            re.compile(r"Cannot\s+mock\s+final\s+classes", re.IGNORECASE),
        ],
        "default_verdict": "skill-layer appropriate",
        "rationale_fixer": "Static mockito annotations cleanup.",
        "rationale_skill": (
            "Complex test lifecycle, assertion logic, mock verification, and stubbing "
            "flow requiring deep semantic understanding of unit testing intentions."
        ),
    },
]


# ==============================================================================
# Data Structures (conforming to specs/009-historical-baseline-analysis/data-model.md)
# ==============================================================================

@dataclass
class RawSessionRecord:
    id: str
    spec_id: Optional[str]
    spec_name: str
    status: str
    phase: str
    repair_attempts: int
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    lifecycle_phase: Optional[str] = None


@dataclass
class SessionOutcomeMetrics:
    total_sessions: int
    terminal_sessions: int
    in_flight_sessions: int
    status_counts: Dict[str, int] = field(default_factory=dict)
    status_percentages: Dict[str, float] = field(default_factory=dict)
    phase_counts: Dict[str, int] = field(default_factory=dict)
    verified_count: int = 0
    verified_percentage: float = 0.0
    blocked_count: int = 0
    blocked_percentage: float = 0.0
    failed_count: int = 0
    failed_percentage: float = 0.0


@dataclass
class RepairLoopMetrics:
    total_repaired_sessions: int
    attempt_distribution: Dict[int, int] = field(default_factory=dict)
    attempt_percentages: Dict[int, float] = field(default_factory=dict)
    exhausted_count: int = 0
    exhaustion_rate: float = 0.0
    first_attempt_recovery_rate: float = 0.0


@dataclass
class ParsedErrorDiagnostic:
    category: str
    summary: str
    raw_text: str
    source_file: Optional[str] = None
    line_number: Optional[int] = None
    matched_domain: Optional[str] = None


@dataclass
class CandidateDomainEvaluation:
    domain_key: str
    display_name: str
    incident_count: int
    failure_share: float
    verdict: str  # "skill-layer appropriate" | "deterministic-fixer appropriate" | "not observed"
    rationale: str
    sample_signatures: List[str] = field(default_factory=list)


@dataclass
class HistoricalBaselineReportData:
    generated_at: str
    database_path: str
    outcome_metrics: SessionOutcomeMetrics
    repair_metrics: RepairLoopMetrics
    domain_evaluations: List[CandidateDomainEvaluation]
    top_diagnostics: List[ParsedErrorDiagnostic]
    constitutional_violations: Dict[str, int]
    raw_error_count: int


# ==============================================================================
# Database Connector (Strict Read-Only)
# ==============================================================================

def connect_readonly(db_path: Path) -> sqlite3.Connection:
    """
    Connects to the SQLite database in strict read-only mode using URI scheme.
    Enforces engine-level query_only pragma to guarantee zero write operations.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")

    # Use file:path?mode=ro for engine-level read-only enforcement
    uri_path = f"file:{db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri_path, uri=True)
    conn.row_factory = sqlite3.Row

    # Enforce read-only at session pragma level
    conn.execute("PRAGMA query_only = ON;")
    return conn


def fetch_sessions(conn: sqlite3.Connection) -> List[RawSessionRecord]:
    """
    Queries generation_sessions table with dynamic column introspection.
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(generation_sessions)")
    columns = {row["name"] for row in cursor.fetchall()}

    if not columns:
        raise ValueError("Table 'generation_sessions' not found in database.")

    query = "SELECT * FROM generation_sessions ORDER BY created_at ASC"
    cursor.execute(query)
    rows = cursor.fetchall()

    records: List[RawSessionRecord] = []
    for r in rows:
        row_dict = dict(r)
        records.append(
            RawSessionRecord(
                id=str(row_dict.get("id", "")),
                spec_id=row_dict.get("spec_id"),
                spec_name=str(row_dict.get("spec_name", "Unknown")),
                status=str(row_dict.get("status", "UNKNOWN")).upper(),
                phase=str(row_dict.get("phase", "UNKNOWN")).upper(),
                repair_attempts=int(row_dict.get("repair_attempts") or 0),
                created_at=str(row_dict.get("created_at", "")),
                completed_at=row_dict.get("completed_at"),
                error_message=row_dict.get("error_message"),
                lifecycle_phase=row_dict.get("current_lifecycle_phase"),
            )
        )
    return records


# ==============================================================================
# Metric Calculations (User Story 1 & User Story 2)
# ==============================================================================

TERMINAL_STATUSES = {"COMPLETED", "BLOCKED", "FAILED", "CANCELLED"}
IN_FLIGHT_STATUSES = {"QUEUED", "RUNNING", "PAUSED"}


def calculate_outcome_metrics(sessions: List[RawSessionRecord]) -> SessionOutcomeMetrics:
    """
    Computes pass/fail distribution across terminal sessions.
    Distinguishes terminal sessions from in-flight sessions.
    """
    total = len(sessions)
    if total == 0:
        return SessionOutcomeMetrics(
            total_sessions=0,
            terminal_sessions=0,
            in_flight_sessions=0,
        )

    status_counts: Dict[str, int] = {}
    phase_counts: Dict[str, int] = {}
    terminal_count = 0
    in_flight_count = 0

    verified_count = 0
    blocked_count = 0
    failed_count = 0

    for s in sessions:
        st = s.status
        ph = s.phase

        status_counts[st] = status_counts.get(st, 0) + 1
        phase_counts[ph] = phase_counts.get(ph, 0) + 1

        if st in IN_FLIGHT_STATUSES:
            in_flight_count += 1
            continue

        terminal_count += 1

        # Evaluate verified vs blocked vs failed
        if ph == "VERIFIED" or (st == "COMPLETED" and ph != "FAILED"):
            verified_count += 1
        elif ph == "FAILED" or st == "FAILED":
            failed_count += 1
        elif st == "BLOCKED" or ph == "SELF_REPAIR_LOOP":
            blocked_count += 1
        else:
            # Fallback based on status
            if st == "COMPLETED":
                verified_count += 1
            else:
                blocked_count += 1

    status_percentages: Dict[str, float] = {}
    denom = terminal_count if terminal_count > 0 else 1
    for k, v in status_counts.items():
        if k not in IN_FLIGHT_STATUSES:
            status_percentages[k] = round((v / denom) * 100.0, 1)

    verified_pct = round((verified_count / denom) * 100.0, 1) if terminal_count > 0 else 0.0
    blocked_pct = round((blocked_count / denom) * 100.0, 1) if terminal_count > 0 else 0.0
    failed_pct = round((failed_count / denom) * 100.0, 1) if terminal_count > 0 else 0.0

    return SessionOutcomeMetrics(
        total_sessions=total,
        terminal_sessions=terminal_count,
        in_flight_sessions=in_flight_count,
        status_counts=status_counts,
        status_percentages=status_percentages,
        phase_counts=phase_counts,
        verified_count=verified_count,
        verified_percentage=verified_pct,
        blocked_count=blocked_count,
        blocked_percentage=blocked_pct,
        failed_count=failed_count,
        failed_percentage=failed_pct,
    )


def calculate_repair_metrics(sessions: List[RawSessionRecord]) -> RepairLoopMetrics:
    """
    Calculates distribution of repair attempts per session and loop exhaustion rate.
    """
    terminal_sessions = [s for s in sessions if s.status not in IN_FLIGHT_STATUSES]
    if not terminal_sessions:
        return RepairLoopMetrics(total_repaired_sessions=0)

    attempt_dist: Dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0}
    repaired_sessions = 0
    exhausted_count = 0
    attempt_1_recovered = 0

    for s in terminal_sessions:
        attempts = min(s.repair_attempts, 3)
        attempt_dist[attempts] = attempt_dist.get(attempts, 0) + 1

        if s.repair_attempts > 0:
            repaired_sessions += 1

        is_verified = s.phase == "VERIFIED" or (s.status == "COMPLETED" and s.phase != "FAILED")

        if s.repair_attempts >= 3 and not is_verified:
            exhausted_count += 1

        if s.repair_attempts == 1 and is_verified:
            attempt_1_recovered += 1

    total_denom = len(terminal_sessions)
    attempt_percentages: Dict[int, float] = {
        k: round((v / total_denom) * 100.0, 1) for k, v in attempt_dist.items()
    }

    repair_denom = repaired_sessions if repaired_sessions > 0 else 1
    exhaustion_rate = round((exhausted_count / repair_denom) * 100.0, 1) if repaired_sessions > 0 else 0.0
    recovery_rate_1 = round((attempt_1_recovered / repair_denom) * 100.0, 1) if repaired_sessions > 0 else 0.0

    return RepairLoopMetrics(
        total_repaired_sessions=repaired_sessions,
        attempt_distribution=attempt_dist,
        attempt_percentages=attempt_percentages,
        exhausted_count=exhausted_count,
        exhaustion_rate=exhaustion_rate,
        first_attempt_recovery_rate=recovery_rate_1,
    )


def parse_session_errors(sessions: List[RawSessionRecord]) -> List[ParsedErrorDiagnostic]:
    """
    Parses raw error messages from sessions into structured diagnostics.
    """
    diagnostics: List[ParsedErrorDiagnostic] = []

    compilation_regex = re.compile(r"\[ERROR\]\s+([^\s:]+\.java):\[(\d+),(\d+)\]\s+(.*)")
    surefire_regex = re.compile(r"\[ERROR\]\s+([A-Za-z0-9_]+)\.([A-Za-z0-9_]+):(\d+)\s+(.*?)(?=\n\[|$)", re.MULTILINE)

    for s in sessions:
        err = s.error_message
        if not err or not err.strip():
            continue

        matched_any = False

        # 1. Compilation errors
        for m in compilation_regex.finditer(err):
            matched_any = True
            file_path = m.group(1).strip()
            line_no = int(m.group(2))
            msg = m.group(4).strip()
            diagnostics.append(
                ParsedErrorDiagnostic(
                    category="COMPILATION_ERROR",
                    summary=f"Compilation failure in {file_path.split('/')[-1]}:{line_no} - {msg}",
                    raw_text=m.group(0),
                    source_file=file_path,
                    line_number=line_no,
                )
            )

        # 2. Surefire assertions
        for m in surefire_regex.finditer(err):
            matched_any = True
            cls_name = m.group(1).strip()
            meth_name = m.group(2).strip()
            line_no = int(m.group(3))
            msg = m.group(4).strip()
            diagnostics.append(
                ParsedErrorDiagnostic(
                    category="ASSERTION_FAILURE",
                    summary=f"Test failure in {cls_name}.{meth_name}:{line_no} - {msg}",
                    raw_text=m.group(0),
                    source_file=f"src/test/java/{cls_name}.java",
                    line_number=line_no,
                )
            )

        # 3. Constitutional violations in log
        if "Constitutional Violation" in err or "Principle" in err:
            matched_any = True
            first_line = err.split("\n")[0].strip()
            diagnostics.append(
                ParsedErrorDiagnostic(
                    category="CONSTITUTIONAL_VIOLATION",
                    summary=first_line,
                    raw_text=err[:500],
                )
            )

        # 4. Fallback if errors mentioned but regex didn't catch specific format
        if not matched_any:
            diagnostics.append(
                ParsedErrorDiagnostic(
                    category="RUNTIME_EXCEPTION" if "BUILD FAILURE" not in err else "BUILD_FAILURE",
                    summary=err.split("\n")[0][:120],
                    raw_text=err[:500],
                )
            )

    return diagnostics


def calculate_constitutional_violations(sessions: List[RawSessionRecord]) -> Dict[str, int]:
    """
    Quantifies frequency of constitutional rule triggers across sessions.
    """
    principles = {
        "Principle I: Layer Isolation": re.compile(r"Principle I|Layer Isolation|Repository directly|Controllers MUST NOT", re.IGNORECASE),
        "Principle II: Immutable DTOs": re.compile(r"Principle II|Immutable|Java Record|Jakarta Validation", re.IGNORECASE),
        "Principle III: Centralized Exception Handling": re.compile(r"Principle III|try-catch|@RestControllerAdvice|ProblemDetails", re.IGNORECASE),
        "Principle IV: Offline Determinism": re.compile(r"Principle IV|Offline|Non-resolvable parent POM|Could not resolve dependencies", re.IGNORECASE),
        "Principle V: Quality Gates & 3-Repair Cap": re.compile(r"Principle V|repair_attempts|exceeded|exhausted", re.IGNORECASE),
        "Principle VI: Zero Secrets & Isolation": re.compile(r"Principle VI|Hardcoded|Secret|API key", re.IGNORECASE),
    }

    counts: Dict[str, int] = {k: 0 for k in principles}

    for s in sessions:
        err = s.error_message or ""
        for name, pat in principles.items():
            if pat.search(err):
                counts[name] += 1

    return counts


def evaluate_domains(
    sessions: List[RawSessionRecord],
    diagnostics: List[ParsedErrorDiagnostic]
) -> List[CandidateDomainEvaluation]:
    """
    Evaluates each of the 5 candidate domains against observed error logs.
    Assigns data-driven triage classification and technical reasoning.
    """
    # Aggregate all error text across sessions
    error_blobs = [s.error_message for s in sessions if s.error_message]
    total_error_sessions = len(error_blobs)

    evaluations: List[CandidateDomainEvaluation] = []

    for dom in CANDIDATE_DOMAINS:
        key = dom["key"]
        name = dom["name"]
        patterns = dom["patterns"]
        default_verdict = dom["default_verdict"]

        incident_count = 0
        samples: List[str] = []

        for blob in error_blobs:
            matched_for_session = False
            for pat in patterns:
                match = pat.search(blob)
                if match:
                    matched_for_session = True
                    sample = match.group(0).strip()
                    if sample not in samples and len(samples) < 3:
                        samples.append(sample)
            if matched_for_session:
                incident_count += 1

        denom = total_error_sessions if total_error_sessions > 0 else 1
        share = round((incident_count / denom) * 100.0, 1) if total_error_sessions > 0 else 0.0

        if incident_count == 0:
            verdict = "not observed"
            rationale = (
                f"Zero incidents detected in historical dataset ({incident_count} occurrences). "
                "Exclude from the skill injection pilot as no current failure evidence exists."
            )
        elif default_verdict == "deterministic-fixer appropriate":
            verdict = "deterministic-fixer appropriate"
            rationale = dom["rationale_fixer"]
        else:
            verdict = "skill-layer appropriate"
            rationale = dom["rationale_skill"]

        evaluations.append(
            CandidateDomainEvaluation(
                domain_key=key,
                display_name=name,
                incident_count=incident_count,
                failure_share=share,
                verdict=verdict,
                rationale=rationale,
                sample_signatures=samples,
            )
        )

    return evaluations


# ==============================================================================
# Markdown Report & JSON Generators (User Story 3)
# ==============================================================================

def generate_markdown_report(report: HistoricalBaselineReportData) -> str:
    """
    Renders structured single-page markdown report adhering to contracts/report-schema.md.
    Enforces dual numerical format: count (percentage%).
    """
    o = report.outcome_metrics
    r = report.repair_metrics

    # Pilot survival summary
    skill_domains = [d for d in report.domain_evaluations if d.verdict == "skill-layer appropriate"]
    fixer_domains = [d for d in report.domain_evaluations if d.verdict == "deterministic-fixer appropriate"]
    unobserved_domains = [d for d in report.domain_evaluations if d.verdict == "not observed"]

    now_iso = report.generated_at

    lines = [
        "# AgentIA Historical Baseline Analysis: Failure Mode Distribution & Skill Pilot Triage",
        "",
        "> **Executive Digest**: Analysis of historical generation sessions demonstrates that "
        f"**{o.verified_count} ({o.verified_percentage}%)** of terminal sessions completed successfully, while "
        f"**{o.blocked_count} ({o.blocked_percentage}%)** terminated in blocked state and "
        f"**{o.failed_count} ({o.failed_percentage}%)** suffered unrecoverable failures. "
        f"Out of 5 evaluated candidate failure domains, **{len(skill_domains)} domains** survive into the "
        f"Skill Injection Pilot, **{len(fixer_domains)} domains** are triaged to deterministic fixers, "
        f"and **{len(unobserved_domains)} domains** were not observed.",
        "",
        "---",
        "",
        "## 1. Metadata & Dataset Overview",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| **Analysis Date** | `{now_iso}` |",
        f"| **Database Source** | `{report.database_path}` |",
        f"| **Total Sessions Queried** | **{o.total_sessions}** |",
        f"| **Terminal Sessions Analyzed** | **{o.terminal_sessions}** |",
        f"| **In-Flight / Active Sessions** | **{o.in_flight_sessions}** |",
        "",
        "---",
        "",
        "## 2. Executive Scorecard: Candidate Domain Triage",
        "",
        "| Candidate Domain | Incidents | Error Share | Triage Verdict | Strategic Justification | Pilot Scope |",
        "| :--- | :---: | :---: | :---: | :--- | :---: |",
    ]

    for d in report.domain_evaluations:
        status_icon = "🎯 **SURVIVES**" if d.verdict == "skill-layer appropriate" else ("🔧 **DETERMINISTIC**" if d.verdict == "deterministic-fixer appropriate" else "⚪ **EXCLUDED**")
        lines.append(
            f"| **{d.display_name}** | {d.incident_count} | {d.failure_share}% | `{d.verdict}` | {d.rationale} | {status_icon} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Session Terminal State Distribution",
        "",
        "| Final Status | Session Count | Percentage Share (%) | Operational Significance |",
        "| :--- | :---: | :---: | :--- |",
        f"| **`VERIFIED`** | **{o.verified_count}** | **{o.verified_percentage}%** | Microservice passed 100% tests & quality gates |",
        f"| **`BLOCKED`** | **{o.blocked_count}** | **{o.blocked_percentage}%** | Execution halted by Quality Gate or loop exhaustion |",
        f"| **`FAILED`** | **{o.failed_count}** | **{o.failed_percentage}%** | Unrecoverable build / infrastructure exception |",
        "",
        f"- **Verification Success Rate**: {o.verified_count} of {o.terminal_sessions} terminal sessions ({o.verified_percentage}%).",
        f"- **Intervention Overhead Rate**: {o.blocked_count + o.failed_count} of {o.terminal_sessions} terminal sessions ({round(100.0 - o.verified_percentage, 1)}%) required human intervention or aborted.",
        "",
        "---",
        "",
        "## 4. Autonomous Self-Repair Loop Behavior",
        "",
        "Under Constitution Principle V, the autonomous repair loop is bounded to a maximum of 3 iterations.",
        "",
        "| Repair Attempts Required | Sessions | Percentage (%) | Efficiency Analysis |",
        "| :---: | :---: | :---: | :--- |",
        f"| **0 Attempts** (First-Pass Clean) | **{r.attempt_distribution.get(0, 0)}** | **{r.attempt_percentages.get(0, 0.0)}%** | Code passed compilation & tests without repair |",
        f"| **1 Attempt** (Self-Repaired) | **{r.attempt_distribution.get(1, 0)}** | **{r.attempt_percentages.get(1, 0.0)}%** | Fixed on first automated repair cycle |",
        f"| **2 Attempts** (Complex Repair) | **{r.attempt_distribution.get(2, 0)}** | **{r.attempt_percentages.get(2, 0.0)}%** | Required secondary diagnostic repair |",
        f"| **3 Attempts** (Cap Exhausted) | **{r.attempt_distribution.get(3, 0)}** | **{r.attempt_percentages.get(3, 0.0)}%** | Hit boundary limit; triggered safety abort |",
        "",
        f"- **Total Sessions Involving Repair**: {r.total_repaired_sessions} sessions.",
        f"- **Loop Exhaustion Rate**: **{r.exhausted_count} ({r.exhaustion_rate}%)** of repaired sessions exhausted the 3-attempt cap without reaching verified status.",
        f"- **First-Attempt Recovery Efficiency**: **{r.attempt_distribution.get(1, 0)} ({r.first_attempt_recovery_rate}%)** of failed runs were remediated on the very first repair cycle.",
        "",
        "---",
        "",
        "## 5. Failure Mode Taxonomy & Diagnostic Breakdown",
        "",
        "Breakdown of errors parsed across compiler logs, surefire test executions, and sandbox traces:",
        "",
        "| Diagnostic Category | Incident Count | Share (%) | Primary Root Causes |",
        "| :--- | :---: | :---: | :--- |",
    ])

    cat_counts: Dict[str, int] = {}
    for diag in report.top_diagnostics:
        cat_counts[diag.category] = cat_counts.get(diag.category, 0) + 1

    total_diags = len(report.top_diagnostics) if len(report.top_diagnostics) > 0 else 1
    for cat, cnt in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
        share = round((cnt / total_diags) * 100.0, 1)
        lines.append(f"| **`{cat}`** | {cnt} | {share}% | Recurrent syntax, assertion, or architectural boundary failures |")

    lines.extend([
        "",
        "---",
        "",
        "## 6. Constitutional Validator Violation Frequency",
        "",
        "Frequency of automated quality gate violations flagged by platform validators:",
        "",
        "| Constitutional Principle | Violations Observed | Enforcement Action |",
        "| :--- | :---: | :--- |",
    ])

    for princ, count in report.constitutional_violations.items():
        action = "Gate BLOCKED - Human Review Required" if count > 0 else "Compliant (0 violations)"
        lines.append(f"| **{princ}** | **{count}** | {action} |")

    lines.extend([
        "",
        "---",
        "",
        "## 7. Pilot Scope Recommendations & Next Actions",
        "",
        "### A. Domains Surviving into Skill Injection Pilot",
    ])

    if skill_domains:
        for d in skill_domains:
            lines.append(f"1. **`{d.domain_key}`** ({d.display_name}): {d.incident_count} incidents ({d.failure_share}% failure share). *Justification*: {d.rationale}")
    else:
        lines.append("- *No domains survived under skill-layer classification based on current empirical data.*")

    lines.extend([
        "",
        "### B. Domains Triaged to Deterministic Fixers (AST/Regex)",
    ])

    if fixer_domains:
        for d in fixer_domains:
            lines.append(f"1. **`{d.domain_key}`** ({d.display_name}): {d.incident_count} incidents ({d.failure_share}% failure share). *Justification*: {d.rationale}")
    else:
        lines.append("- *No domains classified for deterministic fixers.*")

    if unobserved_domains:
        lines.extend([
            "",
            "### C. Excluded Domains (Not Observed in Historical Data)",
        ])
        for d in unobserved_domains:
            lines.append(f"1. **`{d.domain_key}`** ({d.display_name}): 0 incidents recorded. Do not invest pilot resources.")

    lines.extend([
        "",
        "### D. Architectural Roadmap for Skill Injection Pilot",
        "- **Zero Code Changes to Core Runtime**: Implement skill injection as a pre-generation prompt layer, preserving AgentIA core stability.",
        "- **Targeted Focus**: Prioritize skill authoring for surviving semantic domains (`layer_architecture` and `mockito_tests`).",
        "- **Deterministic Interceptor**: Implement a lightweight post-processing pass for `jakarta_namespace` and `maven_pom` before invoking the 3-attempt repair loop.",
        "",
        "---",
        f"*Report auto-generated by `backend/scripts/analyze_historical_baseline.py` on {now_iso}.*",
    ])

    return "\n".join(lines)


def generate_json_telemetry(report: HistoricalBaselineReportData) -> Dict[str, Any]:
    """
    Renders structured dictionary matching CLI JSON mode contract.
    """
    o = report.outcome_metrics
    r = report.repair_metrics

    domains_dict = {}
    for d in report.domain_evaluations:
        domains_dict[d.domain_key] = {
            "name": d.display_name,
            "count": d.incident_count,
            "failure_share": d.failure_share,
            "verdict": d.verdict,
            "rationale": d.rationale,
        }

    return {
        "generated_at": report.generated_at,
        "database_path": report.database_path,
        "total_sessions": o.total_sessions,
        "terminal_sessions": o.terminal_sessions,
        "in_flight_sessions": o.in_flight_sessions,
        "verified_count": o.verified_count,
        "verified_percentage": o.verified_percentage,
        "blocked_count": o.blocked_count,
        "blocked_percentage": o.blocked_percentage,
        "failed_count": o.failed_count,
        "failed_percentage": o.failed_percentage,
        "repair_loop": {
            "sessions_with_repairs": r.total_repaired_sessions,
            "attempt_distribution": r.attempt_distribution,
            "attempt_percentages": r.attempt_percentages,
            "exhausted_count": r.exhausted_count,
            "exhaustion_rate": r.exhaustion_rate,
            "first_attempt_recovery_rate": r.first_attempt_recovery_rate,
        },
        "candidate_domains": domains_dict,
        "constitutional_violations": report.constitutional_violations,
    }


# ==============================================================================
# CLI Entrypoint & Runner
# ==============================================================================

def run_analysis(
    db_path: Path,
    output_path: Optional[Path] = None,
    json_mode: bool = False,
    verbose: bool = False,
) -> Tuple[int, HistoricalBaselineReportData]:
    """
    Executes end-to-end analysis on database and writes report if output_path is provided.
    Returns (exit_code, report_data).
    """
    if not db_path.exists():
        if not json_mode:
            print(f"[ERROR] Database file not found: {db_path}", file=sys.stderr)
        return 1, None  # type: ignore

    try:
        conn = connect_readonly(db_path)
    except sqlite3.OperationalError as e:
        if not json_mode:
            print(f"[ERROR] Failed to connect to SQLite database: {e}", file=sys.stderr)
        return 2, None  # type: ignore

    try:
        sessions = fetch_sessions(conn)
    except Exception as e:
        if not json_mode:
            print(f"[ERROR] Failed to query generation_sessions: {e}", file=sys.stderr)
        conn.close()
        return 2, None  # type: ignore
    finally:
        conn.close()

    if verbose and not json_mode:
        print(f"[INFO] Fetched {len(sessions)} session records from {db_path}")

    # Compute metrics
    outcome = calculate_outcome_metrics(sessions)
    repair = calculate_repair_metrics(sessions)
    diagnostics = parse_session_errors(sessions)
    violations = calculate_constitutional_violations(sessions)
    evaluations = evaluate_domains(sessions, diagnostics)

    now_iso = datetime.now(timezone.utc).isoformat()
    report_data = HistoricalBaselineReportData(
        generated_at=now_iso,
        database_path=str(db_path),
        outcome_metrics=outcome,
        repair_metrics=repair,
        domain_evaluations=evaluations,
        top_diagnostics=diagnostics,
        constitutional_violations=violations,
        raw_error_count=len(diagnostics),
    )

    # Render Markdown report
    md_content = generate_markdown_report(report_data)

    if output_path:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(md_content, encoding="utf-8")
            if verbose and not json_mode:
                print(f"[INFO] Written baseline distribution report to: {output_path}")
        except Exception as e:
            if not json_mode:
                print(f"[ERROR] Failed to write report file {output_path}: {e}", file=sys.stderr)
            return 3, report_data

    return 0, report_data


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Historical Baseline Analysis Utility for AgentIA Skill Injection Pilot."
    )
    default_db = os.environ.get("AGENTIA_STUDIO_DB")
    if not default_db:
        # Check standard locations
        if Path("backend/studio.db").exists():
            default_db = "backend/studio.db"
        elif Path("studio.db").exists():
            default_db = "studio.db"
        else:
            default_db = "backend/studio.db"

    default_output = os.environ.get("BASELINE_REPORT_OUTPUT", "reports/009-historical-baseline.md")

    parser.add_argument(
        "--db-path",
        "-d",
        type=Path,
        default=Path(default_db),
        help=f"Path to SQLite database (default: {default_db})",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path(default_output),
        help=f"Path for output markdown report (default: {default_output})",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Emit structured JSON metrics to stdout",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose informational output",
    )

    return parser.parse_args(args)


def main() -> None:
    args = parse_args()

    exit_code, report_data = run_analysis(
        db_path=args.db_path,
        output_path=args.output,
        json_mode=args.json,
        verbose=args.verbose,
    )

    if exit_code != 0:
        sys.exit(exit_code)

    if args.json:
        telemetry = generate_json_telemetry(report_data)
        print(json.dumps(telemetry, indent=2))
    else:
        o = report_data.outcome_metrics
        r = report_data.repair_metrics
        print(f"[INFO] Analyzed {o.total_sessions} sessions from {args.db_path}")
        print(f"[INFO] Outcomes: {o.verified_count} ({o.verified_percentage}%) Verified, {o.blocked_count} ({o.blocked_percentage}%) Blocked, {o.failed_count} ({o.failed_percentage}%) Failed")
        print(f"[INFO] Repair Loop: {r.total_repaired_sessions} repaired, {r.exhausted_count} ({r.exhaustion_rate}%) exhausted")
        print(f"[INFO] Report generated at: {args.output}")


if __name__ == "__main__":
    main()
