import pytest
from app.services.test_analysis_service import test_analysis_service
from app.models.test_analysis import TestType, DiagnosticCategory, DiagnosticSeverity, PatchType, RepairOutcome

@pytest.fixture
def sample_blueprint():
    return {
        "specId": "spec-order-123",
        "serviceName": "order-service",
        "packageName": "com.corp.order",
        "entities": [
            {
                "name": "Order",
                "tableName": "orders",
                "attributes": [
                    {"name": "id", "javaType": "Long", "isPrimaryKey": True},
                    {"name": "orderNumber", "javaType": "String", "isPrimaryKey": False},
                    {"name": "totalAmount", "javaType": "BigDecimal", "isPrimaryKey": False}
                ]
            }
        ],
        "userStories": [
            {
                "id": "US-1",
                "role": "Customer",
                "intent": "create order",
                "benefit": "purchase goods",
                "scenarios": [
                    {
                        "scenarioId": "AC-1.1",
                        "given": "valid order details",
                        "when": "submitting checkout",
                        "then": "return 201 Created"
                    }
                ]
            }
        ]
    }

def test_synthesize_test_suites_hybrid(sample_blueprint):
    resp = test_analysis_service.synthesize_test_suites(
        blueprint=sample_blueprint,
        test_types=[TestType.UNIT, TestType.INTEGRATION_WEB, TestType.INTEGRATION_DB]
    )

    assert resp.serviceName == "order-service"
    assert resp.packageName == "com.corp.order"
    assert len(resp.suites) == 3
    assert resp.totalTestCases >= 5

    # Check Service Unit Test
    svc_test = next(s for s in resp.suites if s.testType == TestType.UNIT)
    assert svc_test.className == "OrderServiceTest"
    assert "@ExtendWith(MockitoExtension.class)" in svc_test.fullSourceCode
    assert "@Mock" in svc_test.fullSourceCode
    assert "assertThat" in svc_test.fullSourceCode

    # Check Controller Web Test
    web_test = next(s for s in resp.suites if s.testType == TestType.INTEGRATION_WEB)
    assert web_test.className == "OrderControllerTest"
    assert "@WebMvcTest(OrderController.class)" in web_test.fullSourceCode
    assert "mockMvc.perform(post(\"/api/v1/orders\")" in web_test.fullSourceCode

    # Check Context Integration Test
    db_test = next(s for s in resp.suites if s.testType == TestType.INTEGRATION_DB)
    assert db_test.className == "OrderIntegrationTest"
    assert "@SpringBootTest" in db_test.fullSourceCode
    assert "@ActiveProfiles(\"test\")" in db_test.fullSourceCode

def test_analyze_code_compliance_violations():
    source_files = {
        "src/main/java/com/corp/order/controller/OrderController.java": """package com.corp.order.controller;
import com.corp.order.repository.OrderRepository;
public class OrderController {
    private OrderRepository orderRepository;
}
""",
        "src/main/java/com/corp/order/dto/CreateOrderRequest.java": """package com.corp.order.dto;
public class CreateOrderRequest {
    private String name;
}
""",
        "src/main/java/com/corp/order/model/Order.java": """package com.corp.order.model;
import lombok.Data;
@Data
public class Order {
    private Long id;
}
"""
    }

    is_compliant, diags = test_analysis_service.analyze_code_compliance(source_files)
    assert is_compliant is False
    assert len(diags) == 3

    categories = [d.category for d in diags]
    assert all(c == DiagnosticCategory.CONSTITUTIONAL_VIOLATION for c in categories)

    summaries = [d.errorSummary for d in diags]
    assert any("Principle I Violation" in s for s in summaries)
    assert any("Principle II Violation" in s for s in summaries)
    assert any("Lombok Violation" in s for s in summaries)

def test_plan_surgical_repair_and_apply():
    broken_code = """package com.corp.order.service;

public class OrderServiceImpl {
    public void calculate() {
        var amount = BigDecimal.ZERO;
        var total = "90.00";
    }
}
"""
    source_files = {
        "src/main/java/com/corp/order/service/OrderServiceImpl.java": broken_code
    }

    # 1. Missing import diagnostic
    diag_comp = test_analysis_service.analyze_execution_and_code(
        raw_build_logs="[ERROR] OrderServiceImpl.java:[5,22] cannot find symbol: class BigDecimal",
        source_files=source_files
    )
    assert len(diag_comp.diagnostics) >= 1

    patches = test_analysis_service.plan_surgical_repair(diag_comp.diagnostics, source_files)
    assert len(patches) >= 1
    assert patches[0].patchType == PatchType.IMPORT_ADD

    updated_files, diff = test_analysis_service.apply_code_patch(source_files, patches[0])
    assert "import java.math.BigDecimal;" in updated_files["src/main/java/com/corp/order/service/OrderServiceImpl.java"]
    assert "+import java.math.BigDecimal;" in diff

def test_execute_repair_iteration_and_cap_at_5():
    source_files = {
        "src/main/java/com/corp/order/service/OrderServiceImpl.java": "public class OrderServiceImpl { public String val() { return \"90.00\"; } }"
    }

    raw_logs = "[ERROR]   OrderServiceTest.shouldMatch:45 expected: <80.00> but was: <90.00>"
    analysis = test_analysis_service.analyze_execution_and_code(raw_logs, source_files)

    # Iteration 1
    iter1 = test_analysis_service.execute_repair_iteration(
        session_id="session-1",
        iteration_number=1,
        diagnostics=analysis.diagnostics,
        source_files=source_files
    )
    assert iter1.iterationNumber == 1
    assert iter1.outcome == RepairOutcome.SUCCESS
    assert len(iter1.patchesApplied) >= 1
    assert "80.00" in iter1.diffSummary

    # Iteration 3 (Permitted and succeeds)
    iter3 = test_analysis_service.execute_repair_iteration(
        session_id="session-1",
        iteration_number=3,
        diagnostics=analysis.diagnostics,
        source_files=source_files
    )
    assert iter3.iterationNumber == 3
    assert iter3.outcome == RepairOutcome.SUCCESS

    # Iteration 5 (Exhaustion cap)
    iter5 = test_analysis_service.execute_repair_iteration(
        session_id="session-1",
        iteration_number=5,
        diagnostics=analysis.diagnostics,
        source_files=source_files
    )
    assert iter5.iterationNumber == 5
    assert iter5.outcome == RepairOutcome.FAILED_BLOCKED

    # Iteration 6 (Must raise ValueError / Constitution Principle V Violation)
    with pytest.raises(ValueError) as exc:
        test_analysis_service.execute_repair_iteration(
            session_id="session-1",
            iteration_number=6,
            diagnostics=analysis.diagnostics,
            source_files=source_files
        )
    assert "hard-capped at 5 iterations" in str(exc.value)


