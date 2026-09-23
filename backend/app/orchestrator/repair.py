import re
from typing import Dict, Any, Optional

def can_retry(current_attempt: int, max_attempts: int = 5) -> bool:
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
    if any(keyword in output for keyword in ["COMPILATION ERROR", "cannot find symbol", "package does not exist", "incompatible types", "cannot be applied", "unreported exception"]):
        comp_match = re.search(r"\[ERROR\]\s+(/?[^\s:]+\.java):\[(\d+),(\d+)\]\s+(.*)", output)
        if comp_match:
            file_path = comp_match.group(1).strip()
            line_no = int(comp_match.group(2))
            col_no = int(comp_match.group(3))
            summary = comp_match.group(4).strip()
            # Capture following symbol/location details if present
            details_match = re.search(r"symbol:\s+(.*?)\s+location:\s+([^\n\r]+)", output[comp_match.end():comp_match.end() + 300], re.DOTALL)
            details = details_match.group(0).strip() if details_match else summary
            return {
                "error_type": "COMPILATION",
                "failed_file": file_path,
                "line_number": line_no,
                "column_number": col_no,
                "summary": summary,
                "details": details
            }
        
        # Fallback regex for generic compilation line
        java_match = re.search(r"([^\s:]+\.java)", output)
        return {
            "error_type": "COMPILATION",
            "failed_file": java_match.group(1) if java_match else "src/main/java",
            "summary": "Compilation error detected in source tree",
            "details": output.strip()
        }

    # 2. Check for Surefire test failures or assertion mismatches
    if any(keyword in output for keyword in ["Failures:", "There are test failures", "expected:", "AssertionFailedError", "ComparisonFailure"]):
        failure_match = re.search(r"\[ERROR\]\s+([A-Za-z0-9_]+)\.([A-Za-z0-9_]+):(\d+)\s+(.*)", output)
        if failure_match:
            class_name = failure_match.group(1).strip()
            method_name = failure_match.group(2).strip()
            line_no = int(failure_match.group(3))
            details = failure_match.group(4).strip()
            return {
                "error_type": "TEST_FAILURE",
                "failed_file": f"{class_name}.java",
                "class_name": class_name,
                "method_name": method_name,
                "line_number": line_no,
                "summary": f"{class_name}.{method_name} failed: {details}",
                "details": details
            }
        
        # Test class search fallback
        test_class_match = re.search(r"([A-Za-z0-9_]+Test)\.([A-Za-z0-9_]+)", output)
        if test_class_match:
            c_name = test_class_match.group(1).strip()
            m_name = test_class_match.group(2).strip()
            return {
                "error_type": "TEST_FAILURE",
                "failed_file": f"{c_name}.java",
                "class_name": c_name,
                "method_name": m_name,
                "summary": f"Test failure in {c_name}.{m_name}",
                "details": output.strip()
            }

    # 3. Fallback with first Java file mention in output
    java_any = re.search(r"([A-Za-z0-9_]+(?:Controller|Service|Repository|Entity|Test)\.java)", output)
    return {
        "error_type": "UNKNOWN",
        "failed_file": java_any.group(1) if java_any else "src/main/java",
        "summary": "Build or test failure requiring adaptive repair",
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

