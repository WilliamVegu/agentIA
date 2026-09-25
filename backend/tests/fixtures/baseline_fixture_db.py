"""
Synthetic SQLite test database fixture generator for Historical Baseline Analysis.
"""

import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS generation_sessions (
    id VARCHAR(36) PRIMARY KEY,
    spec_id VARCHAR(36),
    spec_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    phase VARCHAR(30) NOT NULL,
    queue_position INTEGER DEFAULT 0,
    repair_attempts INTEGER DEFAULT 0,
    current_lifecycle_phase VARCHAR(50) DEFAULT 'INITIAL',
    lifecycle_mode VARCHAR(50) DEFAULT 'GUIDED_STEP',
    phase_progress_json TEXT,
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);
"""

SAMPLE_ERRORS = {
    "jakarta": (
        "[ERROR] /workspace/src/main/java/com/agentia/order/model/Order.java:[14,28] "
        "package javax.persistence does not exist\n"
        "[ERROR] /workspace/src/main/java/com/agentia/order/dto/OrderRequest.java:[8,32] "
        "package javax.validation.constraints does not exist"
    ),
    "layer": (
        "[ERROR] Constitutional Violation: Principle I (Layer Isolation)\n"
        "OrderController.java accesses OrderRepository directly on line 42. "
        "Controllers MUST NOT access Repositories or JPA entities directly."
    ),
    "exception": (
        "[ERROR] Constitutional Violation: Principle III (Centralized Exception Handling)\n"
        "OrderController.java contains inline try-catch block handling OrderNotFoundException "
        "instead of delegating to @RestControllerAdvice."
    ),
    "pom": (
        "[ERROR] BUILD FAILURE\n"
        "[ERROR] Non-resolvable parent POM for com.agentia:order-service:1.0.0: "
        "Could not resolve dependencies in offline mode pom.xml"
    ),
    "mockito": (
        "[ERROR] OrderServiceTest.shouldCreateOrder:52 org.mockito.exceptions.misusing.UnnecessaryStubbingException: "
        "Unnecessary stubbings detected in test class OrderServiceTest. "
        "Strictness.STRICT_STUBS detected unused stubbing on orderRepository.save()"
    ),
    "assertion": (
        "[ERROR] OrderControllerTest.createOrder:64 expected: <201 CREATED> but was: <400 BAD_REQUEST>\n"
        "[ERROR] OrderServiceTest.calculateTotal:80 expected: <150.00> but was: <120.00>"
    ),
    "generic_compilation": (
        "[ERROR] /workspace/src/main/java/com/agentia/order/service/OrderService.java:[32,15] "
        "cannot find symbol\n"
        "  symbol:   variable totalAmount\n"
        "  location: class com.agentia.order.service.OrderService"
    )
}


def create_fixture_database(db_path: Path, session_count: int = 50) -> Path:
    """
    Creates a populated SQLite test database with realistic synthetic generation sessions.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_TABLE_SQL)

        now = datetime.now(timezone.utc)

        # 1. Add 28 VERIFIED sessions (various repair attempts)
        for i in range(28):
            sid = str(uuid.uuid4())
            repairs = 0 if i < 16 else (1 if i < 24 else 2)
            cursor.execute(
                """
                INSERT INTO generation_sessions (
                    id, spec_id, spec_name, status, phase, repair_attempts,
                    current_lifecycle_phase, lifecycle_mode, created_at, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    f"spec-{i+1:03d}",
                    f"Microservice Spec {i+1}",
                    "COMPLETED",
                    "VERIFIED",
                    repairs,
                    "COMPLETED",
                    "AUTO_PILOT",
                    (now - timedelta(hours=50 - i)).isoformat(),
                    (now - timedelta(hours=50 - i, minutes=-2)).isoformat(),
                    (now - timedelta(hours=50 - i, minutes=-15)).isoformat(),
                )
            )

        # 2. Add 16 BLOCKED sessions (exhausted repairs with domain errors)
        blocked_error_keys = ["mockito", "layer", "jakarta", "exception", "pom", "assertion", "generic_compilation"]
        for i in range(16):
            sid = str(uuid.uuid4())
            err_key = blocked_error_keys[i % len(blocked_error_keys)]
            err_msg = SAMPLE_ERRORS[err_key]
            cursor.execute(
                """
                INSERT INTO generation_sessions (
                    id, spec_id, spec_name, status, phase, repair_attempts,
                    current_lifecycle_phase, lifecycle_mode, created_at, started_at, completed_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    f"spec-blk-{i+1:03d}",
                    f"Blocked Spec {i+1}",
                    "BLOCKED",
                    "SELF_REPAIR_LOOP",
                    3,  # exhausted
                    "CODE_TESTS",
                    "AUTO_PILOT",
                    (now - timedelta(hours=20 - i)).isoformat(),
                    (now - timedelta(hours=20 - i, minutes=-1)).isoformat(),
                    (now - timedelta(hours=20 - i, minutes=-10)).isoformat(),
                    err_msg,
                )
            )

        # 3. Add 4 FAILED sessions
        for i in range(4):
            sid = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO generation_sessions (
                    id, spec_id, spec_name, status, phase, repair_attempts,
                    current_lifecycle_phase, lifecycle_mode, created_at, started_at, completed_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    f"spec-fail-{i+1:03d}",
                    f"Failed Spec {i+1}",
                    "BLOCKED",
                    "FAILED",
                    1,
                    "SANDBOX_BUILD",
                    "GUIDED_STEP",
                    (now - timedelta(hours=5 - i)).isoformat(),
                    (now - timedelta(hours=5 - i, minutes=-1)).isoformat(),
                    (now - timedelta(hours=5 - i, minutes=-3)).isoformat(),
                    SAMPLE_ERRORS["pom"],
                )
            )

        # 4. Add 2 in-flight RUNNING sessions
        for i in range(2):
            sid = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO generation_sessions (
                    id, spec_id, spec_name, status, phase, repair_attempts,
                    current_lifecycle_phase, lifecycle_mode, created_at, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    f"spec-run-{i+1:03d}",
                    f"Running Spec {i+1}",
                    "RUNNING",
                    "CODE_GENERATION",
                    0,
                    "CODE_TESTS",
                    "AUTO_PILOT",
                    now.isoformat(),
                    now.isoformat(),
                )
            )

        conn.commit()
    finally:
        conn.close()

    return db_path
