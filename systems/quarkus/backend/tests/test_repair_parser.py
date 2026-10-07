import pytest
from app.orchestrator.repair import parse_maven_errors, can_retry, format_repair_prompt

SAMPLE_COMPILATION_ERROR = """
[INFO] -------------------------------------------------------------
[ERROR] COMPILATION ERROR : 
[INFO] -------------------------------------------------------------
[ERROR] /workspace/src/main/java/com/corp/order/service/OrderServiceImpl.java:[28,15] cannot find symbol
  symbol:   method setStatus(OrderStatus)
  location: variable order of type com.corp.order.model.entity.Order
[INFO] 1 error
[INFO] -------------------------------------------------------------
"""

SAMPLE_SUREFIRE_FAILURE = """
[ERROR] Failures: 
[ERROR]   OrderServiceTest.shouldCreateOrder:45 expected: <SUCCESS> but was: <PENDING>
[INFO] 
[ERROR] Tests run: 5, Failures: 1, Errors: 0, Skipped: 0
"""

def test_parse_compilation_error():
    diag = parse_maven_errors(SAMPLE_COMPILATION_ERROR)
    assert diag["error_type"] == "COMPILATION"
    assert "OrderServiceImpl.java" in diag["failed_file"]
    assert "cannot find symbol" in diag["summary"]

def test_parse_surefire_failure():
    diag = parse_maven_errors(SAMPLE_SUREFIRE_FAILURE)
    assert diag["error_type"] == "TEST_FAILURE"
    assert "OrderServiceTest.shouldCreateOrder" in diag["summary"]
    assert "expected: <SUCCESS> but was: <PENDING>" in diag["details"]

def test_retry_boundary_limit_at_3():
    assert can_retry(current_attempt=1, max_attempts=3) is True
    assert can_retry(current_attempt=2, max_attempts=3) is True
    assert can_retry(current_attempt=3, max_attempts=3) is False
    assert can_retry(current_attempt=4, max_attempts=3) is False

