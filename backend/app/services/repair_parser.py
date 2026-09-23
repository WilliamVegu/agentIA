import re
import uuid
from typing import List, Dict, Any, Optional

try:
    from app.models.test_analysis import (
        FailureDiagnostic,
        DiagnosticCategory,
        DiagnosticSeverity,
    )
except ImportError:
    from backend.app.models.test_analysis import (
        FailureDiagnostic,
        DiagnosticCategory,
        DiagnosticSeverity,
    )


def can_retry(current_attempt: int, max_attempts: int = 5) -> bool:
    """
    Evaluates whether another auto-repair attempt is permitted under Constitution Principle V.
    Attempts start at 1. If current_attempt < max_attempts, retry is allowed.
    """
    return current_attempt < max_attempts


def parse_granular_diagnostics(output: str) -> List[FailureDiagnostic]:
    """
    Extracts structured FailureDiagnostic objects from raw Maven compiler output and Surefire logs.
    """
    diagnostics: List[FailureDiagnostic] = []

    # 1. Regex for Java compilation errors:
    # [ERROR] /path/to/File.java:[line,col] message
    compilation_pattern = re.compile(
        r"\[ERROR\]\s+([^\s:]+\.java):\[(\d+),(\d+)\]\s+(.*)"
    )

    for match in compilation_pattern.finditer(output):
        file_path = match.group(1).strip()
        line_no = int(match.group(2))
        col_no = int(match.group(3))
        msg = match.group(4).strip()

        # Capture following symbol/location details if present
        details_match = re.search(
            r"symbol:\s+(.*?)\s+location:\s+([^\n\r]+)", output[match.end():match.end() + 300]
        )
        extra_details = f" - {details_match.group(0).strip()}" if details_match else ""

        diag_id = f"DIAG-COMP-{uuid.uuid4().hex[:6]}"
        diagnostics.append(
            FailureDiagnostic(
                id=diag_id,
                category=DiagnosticCategory.COMPILATION_ERROR,
                severity=DiagnosticSeverity.BLOCKING,
                filePath=file_path,
                lineNumber=line_no,
                columnNumber=col_no,
                errorSummary=f"{msg}{extra_details}",
                rawStackTrace=output[match.start():min(len(output), match.end() + 300)],
                suggestedFix=f"Fix syntax or missing symbol on line {line_no} of {file_path.split('/')[-1]}",
            )
        )

    # 2. Regex for Surefire test assertion failures:
    # [ERROR]   OrderServiceTest.shouldCreateOrder:45 expected: <SUCCESS> but was: <PENDING>
    surefire_pattern = re.compile(
        r"\[ERROR\]\s+([A-Za-z0-9_]+)\.([A-Za-z0-9_]+):(\d+)\s+(.*?)(?=\n\[|$)",
        re.MULTILINE
    )

    for match in surefire_pattern.finditer(output):
        class_name = match.group(1).strip()
        method_name = match.group(2).strip()
        line_no = int(match.group(3))
        msg = match.group(4).strip()

        # Extract expected vs actual if present
        val_match = re.search(r"expected:\s*<([^>]+)>\s*but was:\s*<([^>]+)>", msg)
        expected_val = val_match.group(1) if val_match else None
        actual_val = val_match.group(2) if val_match else None

        file_guess = f"src/test/java/{class_name}.java"
        diag_id = f"DIAG-TEST-{uuid.uuid4().hex[:6]}"

        diagnostics.append(
            FailureDiagnostic(
                id=diag_id,
                category=DiagnosticCategory.ASSERTION_FAILURE,
                severity=DiagnosticSeverity.HIGH,
                filePath=file_guess,
                className=class_name,
                methodName=method_name,
                lineNumber=line_no,
                errorSummary=f"Test assertion failed in {class_name}.{method_name}: {msg}",
                expectedValue=expected_val,
                actualValue=actual_val,
                rawStackTrace=msg,
                suggestedFix=f"Update method logic or test expectation in {class_name}.{method_name}",
            )
        )

    # 3. Fallback if errors mentioned but regex found none
    if not diagnostics and ("COMPILATION ERROR" in output or "BUILD FAILURE" in output or "There are test failures" in output):
        diagnostics.append(
            FailureDiagnostic(
                id=f"DIAG-GEN-{uuid.uuid4().hex[:6]}",
                category=DiagnosticCategory.COMPILATION_ERROR if "COMPILATION ERROR" in output else DiagnosticCategory.RUNTIME_EXCEPTION,
                severity=DiagnosticSeverity.BLOCKING,
                filePath="pom.xml",
                errorSummary="Uncategorized build or test failure in Maven execution",
                rawStackTrace=output[-1000:],
                suggestedFix="Review build logs for details",
            )
        )

    return diagnostics


def parse_maven_errors(output: str) -> Dict[str, Any]:
    """
    Backward-compatible dictionary parser for existing orchestrator calls.
    """
    diags = parse_granular_diagnostics(output)
    if not diags:
        return {
            "error_type": "UNKNOWN",
            "failed_file": "",
            "summary": "Build or test failure without standard pattern",
            "details": output.strip()
        }

    first = diags[0]
    return {
        "error_type": "COMPILATION" if first.category == DiagnosticCategory.COMPILATION_ERROR else "TEST_FAILURE",
        "failed_file": first.filePath,
        "summary": first.errorSummary,
        "details": first.rawStackTrace or first.errorSummary
    }

