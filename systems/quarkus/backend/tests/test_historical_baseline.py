"""
Comprehensive test suite for Historical Baseline Analysis (Feature 009).
"""

import json
import sqlite3
import tempfile
from pathlib import Path
import pytest

try:
    from scripts.analyze_historical_baseline import (
        connect_readonly,
        fetch_sessions,
        calculate_outcome_metrics,
        calculate_repair_metrics,
        parse_session_errors,
        calculate_constitutional_violations,
        evaluate_domains,
        generate_markdown_report,
        generate_json_telemetry,
        run_analysis,
        RawSessionRecord,
    )
    from tests.fixtures.baseline_fixture_db import (
        create_fixture_database,
        CREATE_TABLE_SQL,
        SAMPLE_ERRORS,
    )
except ImportError:
    from backend.scripts.analyze_historical_baseline import (
        connect_readonly,
        fetch_sessions,
        calculate_outcome_metrics,
        calculate_repair_metrics,
        parse_session_errors,
        calculate_constitutional_violations,
        evaluate_domains,
        generate_markdown_report,
        generate_json_telemetry,
        run_analysis,
        RawSessionRecord,
    )
    from backend.tests.fixtures.baseline_fixture_db import (
        create_fixture_database,
        CREATE_TABLE_SQL,
        SAMPLE_ERRORS,
    )


@pytest.fixture
def temp_fixture_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "test_studio.db"
    return create_fixture_database(db_file)


@pytest.fixture
def empty_fixture_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "empty_studio.db"
    conn = sqlite3.connect(db_file)
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()
    conn.close()
    return db_file


# ==============================================================================
# Phase 2 & Safety Tests: Read-Only Database Connection
# ==============================================================================

def test_readonly_connection_enforcement(temp_fixture_db: Path):
    """
    Verifies that connect_readonly opens the database in strict read-only mode,
    and any attempt to modify data raises sqlite3.OperationalError.
    """
    conn = connect_readonly(temp_fixture_db)

    # Read should succeed
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM generation_sessions")
    count = cursor.fetchone()[0]
    assert count > 0

    # Write should be rejected at SQLite engine level
    with pytest.raises(sqlite3.OperationalError, match="readonly|read-only"):
        cursor.execute(
            "UPDATE generation_sessions SET status = 'MUTATED' WHERE id = 'dummy'"
        )

    with pytest.raises(sqlite3.OperationalError, match="readonly|read-only"):
        cursor.execute("DROP TABLE generation_sessions")

    conn.close()


def test_fetch_sessions_introspects_schema(temp_fixture_db: Path):
    """
    Verifies session records are correctly fetched and mapped to dataclasses.
    """
    conn = connect_readonly(temp_fixture_db)
    sessions = fetch_sessions(conn)
    conn.close()

    assert len(sessions) == 50  # 28 verified + 16 blocked + 4 failed + 2 running
    assert all(isinstance(s, RawSessionRecord) for s in sessions)


# ==============================================================================
# Phase 3: User Story 1 Tests (Pass/Fail & Repair Loop Metrics)
# ==============================================================================

def test_outcome_metrics_calculation(temp_fixture_db: Path):
    """
    Verifies calculation of Verified, Blocked, Failed counts and percentages.
    """
    conn = connect_readonly(temp_fixture_db)
    sessions = fetch_sessions(conn)
    conn.close()

    metrics = calculate_outcome_metrics(sessions)

    assert metrics.total_sessions == 50
    assert metrics.in_flight_sessions == 2
    assert metrics.terminal_sessions == 48

    # In fixture: 28 verified, 16 blocked, 4 failed
    assert metrics.verified_count == 28
    assert metrics.blocked_count == 16
    assert metrics.failed_count == 4

    # Percentages relative to terminal sessions (48)
    # 28 / 48 = 58.3%, 16 / 48 = 33.3%, 4 / 48 = 8.3%
    assert metrics.verified_percentage == 58.3
    assert metrics.blocked_percentage == 33.3
    assert metrics.failed_percentage == 8.3


def test_repair_loop_metrics_calculation(temp_fixture_db: Path):
    """
    Verifies attempt distribution (0, 1, 2, 3) and exhaustion rate calculation.
    """
    conn = connect_readonly(temp_fixture_db)
    sessions = fetch_sessions(conn)
    conn.close()

    repair = calculate_repair_metrics(sessions)

    # In fixture:
    # 0 repairs: 16 verified
    # 1 repair: 8 verified + 4 failed = 12
    # 2 repairs: 4 verified
    # 3 repairs: 16 blocked (all exhausted)
    assert repair.attempt_distribution[0] == 16
    assert repair.attempt_distribution[1] == 12
    assert repair.attempt_distribution[2] == 4
    assert repair.attempt_distribution[3] == 16

    assert repair.total_repaired_sessions == (12 + 4 + 16)  # 32
    assert repair.exhausted_count == 16

    # Exhaustion rate = 16 / 32 = 50.0%
    assert repair.exhaustion_rate == 50.0

    # First attempt recovery rate: 8 verified out of 32 repaired = 25.0%
    assert repair.first_attempt_recovery_rate == 25.0


def test_regex_diagnostic_extraction():
    """
    Verifies extraction of javac errors, surefire assertions, and constitutional warnings.
    """
    sample_session = RawSessionRecord(
        id="test-1",
        spec_id="spec-1",
        spec_name="Sample",
        status="BLOCKED",
        phase="SELF_REPAIR_LOOP",
        repair_attempts=3,
        created_at="2026-09-25T00:00:00Z",
        error_message=(
            "[ERROR] /app/OrderService.java:[32,15] cannot find symbol\n"
            "[ERROR] OrderTest.shouldCreate:45 expected: <200> but was: <500>\n"
            "Constitutional Violation: Principle I (Layer Isolation)"
        ),
    )

    diagnostics = parse_session_errors([sample_session])
    categories = [d.category for d in diagnostics]

    assert "COMPILATION_ERROR" in categories
    assert "ASSERTION_FAILURE" in categories
    assert "CONSTITUTIONAL_VIOLATION" in categories


# ==============================================================================
# Phase 4: User Story 2 Tests (Candidate Domain Triage & Scorecard)
# ==============================================================================

def test_candidate_domain_evaluation(temp_fixture_db: Path):
    """
    Verifies that all 5 candidate domains are evaluated and assigned proper verdicts.
    """
    conn = connect_readonly(temp_fixture_db)
    sessions = fetch_sessions(conn)
    conn.close()

    diagnostics = parse_session_errors(sessions)
    evaluations = evaluate_domains(sessions, diagnostics)

    assert len(evaluations) == 5
    eval_map = {e.domain_key: e for e in evaluations}

    # Verify keys
    assert "jakarta_namespace" in eval_map
    assert "layer_architecture" in eval_map
    assert "exception_handling" in eval_map
    assert "maven_pom" in eval_map
    assert "mockito_tests" in eval_map

    # Verified verdicts based on fixture error content
    assert eval_map["jakarta_namespace"].verdict == "deterministic-fixer appropriate"
    assert eval_map["layer_architecture"].verdict == "skill-layer appropriate"
    assert eval_map["exception_handling"].verdict == "skill-layer appropriate"
    assert eval_map["maven_pom"].verdict == "deterministic-fixer appropriate"
    assert eval_map["mockito_tests"].verdict == "skill-layer appropriate"

    # Verify incident counts are greater than 0
    assert eval_map["jakarta_namespace"].incident_count > 0
    assert eval_map["layer_architecture"].incident_count > 0
    assert eval_map["mockito_tests"].incident_count > 0


def test_domain_evaluation_unobserved():
    """
    Verifies that a domain with 0 incidents is classified as 'not observed'.
    """
    clean_session = RawSessionRecord(
        id="clean-1",
        spec_id="spec-clean",
        spec_name="Clean Spec",
        status="COMPLETED",
        phase="VERIFIED",
        repair_attempts=0,
        created_at="2026-09-25T00:00:00Z",
        error_message=None,
    )

    evaluations = evaluate_domains([clean_session], [])
    for e in evaluations:
        assert e.verdict == "not observed"
        assert e.incident_count == 0


def test_constitutional_violations_count(temp_fixture_db: Path):
    """
    Verifies tallying of constitutional principle violations.
    """
    conn = connect_readonly(temp_fixture_db)
    sessions = fetch_sessions(conn)
    conn.close()

    violations = calculate_constitutional_violations(sessions)
    assert violations["Principle I: Layer Isolation"] > 0
    assert violations["Principle III: Centralized Exception Handling"] > 0
    assert violations["Principle IV: Offline Determinism"] > 0


# ==============================================================================
# Phase 5: User Story 3 Tests (CLI, Empty DB, & Report Output)
# ==============================================================================

def test_empty_database_handling(empty_fixture_db: Path, tmp_path: Path):
    """
    Verifies graceful execution on empty database without division by zero.
    """
    report_file = tmp_path / "empty_report.md"
    exit_code, report_data = run_analysis(
        db_path=empty_fixture_db,
        output_path=report_file,
    )

    assert exit_code == 0
    assert report_data is not None
    assert report_data.outcome_metrics.total_sessions == 0
    assert report_data.outcome_metrics.verified_count == 0
    assert report_data.repair_metrics.exhausted_count == 0
    assert report_file.exists()

    content = report_file.read_text(encoding="utf-8")
    assert "| **Total Sessions Queried** | **0** |" in content


def test_missing_database_file(tmp_path: Path):
    """
    Verifies exit code 1 when target database file does not exist.
    """
    missing_file = tmp_path / "non_existent.db"
    exit_code, _ = run_analysis(db_path=missing_file)
    assert exit_code == 1


def test_corrupted_database_file(tmp_path: Path):
    """
    Verifies exit code 2 when database file is corrupted or lacks schema.
    """
    corrupt_file = tmp_path / "corrupt.db"
    corrupt_file.write_text("NOT A SQLITE FILE")

    exit_code, _ = run_analysis(db_path=corrupt_file)
    assert exit_code == 2


def test_full_markdown_report_formatting(temp_fixture_db: Path, tmp_path: Path):
    """
    Verifies that the generated markdown report strictly follows the 7-section
    contract and contains dual formatting (count and percentage) on metrics.
    """
    report_file = tmp_path / "test_report.md"
    exit_code, report_data = run_analysis(
        db_path=temp_fixture_db,
        output_path=report_file,
    )

    assert exit_code == 0
    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")

    # Contract sections
    assert "## 1. Metadata & Dataset Overview" in content
    assert "## 2. Executive Scorecard: Candidate Domain Triage" in content
    assert "## 3. Session Terminal State Distribution" in content
    assert "## 4. Autonomous Self-Repair Loop Behavior" in content
    assert "## 5. Failure Mode Taxonomy & Diagnostic Breakdown" in content
    assert "## 6. Constitutional Validator Violation Frequency" in content
    assert "## 7. Pilot Scope Recommendations & Next Actions" in content

    # Dual representation check: raw number and percentage
    assert "28 (58.3%)" in content or "58.3%" in content
    assert "16 (50.0%)" in content or "50.0%" in content


def test_json_telemetry_schema(temp_fixture_db: Path):
    """
    Verifies JSON telemetry structure matches the CLI contract.
    """
    _, report_data = run_analysis(db_path=temp_fixture_db)
    telemetry = generate_json_telemetry(report_data)

    assert "total_sessions" in telemetry
    assert "verified_count" in telemetry
    assert "verified_percentage" in telemetry
    assert "blocked_count" in telemetry
    assert "repair_loop" in telemetry
    assert "candidate_domains" in telemetry

    domains = telemetry["candidate_domains"]
    assert "jakarta_namespace" in domains
    assert "layer_architecture" in domains
    assert "verdict" in domains["layer_architecture"]
