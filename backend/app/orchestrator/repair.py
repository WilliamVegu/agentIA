import re
from typing import Dict, Any, Optional

def can_retry(current_attempt: int, max_attempts: int = 3) -> bool:
    """
    Evaluates whether another auto-repair attempt is permitted under Constitution Principle V.
    Attempts start at 1. If current_attempt < max_attempts, retry is allowed.
    """
    return current_attempt < max_attempts

def parse_maven_errors(output: str) -> Dict[str, Any]:
    """
    Parses Maven compiler and Surefire test execution outputs to extract actionable diagnostics.
    """
    # 1. Check for compilation errors
    if "COMPILATION ERROR" in output or "cannot find symbol" in output:
        comp_match = re.search(r"\[ERROR\]\s+(/?[^\s]+\.java):\[\d+,\d+\]\s+(.*)", output)
        if comp_match:
            file_path = comp_match.group(1).strip()
            summary = comp_match.group(2).strip()
            # Capture following symbol/location details if present
            details_match = re.search(r"symbol:\s+(.*?)\s+location:\s+(.*)", output, re.DOTALL)
            details = details_match.group(0).strip() if details_match else summary
            return {
                "error_type": "COMPILATION",
                "failed_file": file_path,
                "summary": summary,
                "details": details
            }
        
        # Fallback regex for generic compilation line
        java_match = re.search(r"([^\s]+\.java)", output)
        return {
            "error_type": "COMPILATION",
            "failed_file": java_match.group(1) if java_match else "Unknown.java",
            "summary": "Compilation error detected",
            "details": output.strip()
        }

    # 2. Check for Surefire test failures
    if "Failures:" in output or "There are test failures" in output or "expected:" in output:
        failure_match = re.search(r"\[ERROR\]\s+([A-Za-z0-9_]+\.[A-Za-z0-9_]+):(\d+)\s+(.*)", output)
        if failure_match:
            test_target = failure_match.group(1).strip()
            details = failure_match.group(3).strip()
            return {
                "error_type": "TEST_FAILURE",
                "failed_file": f"{test_target.split('.')[0]}.java",
                "summary": test_target,
                "details": details
            }

    return {
        "error_type": "UNKNOWN",
        "failed_file": "",
        "summary": "Build or test failure without standard pattern",
        "details": output.strip()
    }

def format_repair_prompt(diag: Dict[str, Any], context: Optional[str] = None) -> str:
    """
    Constructs a targeted prompt to guide LLM auto-repair adhering to Constitution v1.1.0.
    """
    error_type = diag.get("error_type", "UNKNOWN")
    failed_file = diag.get("failed_file", "")
    summary = diag.get("summary", "")
    details = diag.get("details", "")

    return f"""The previous build failed with the following diagnostic:
Error Type: {error_type}
Target File: {failed_file}
Summary: {summary}
Details:
{details}

Context:
{context or 'No additional context'}

Please correct the affected Java code while strictly adhering to:
1. Java 21 LTS syntax and features.
2. Spring Boot 3.x patterns (Jakarta EE, not javax).
3. Layered architecture separation (Entity, Repository, Service, Controller).
4. Record DTOs and Mockito unit tests.
Return only valid, production-ready Java code to resolve this issue.
"""

