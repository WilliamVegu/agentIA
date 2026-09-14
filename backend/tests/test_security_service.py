import pytest
from app.models.security_quality import (
    CodeQualityMetrics,
    ConstitutionPrinciple,
    QualityGateStatus,
    SeverityLevel,
    VulnerabilityCategory,
)
from app.services.security_service import (
    apply_surgical_remediation,
    calculate_code_metrics,
    evaluate_quality_gate,
    load_offline_cve_database,
    scan_architecture_compliance,
    scan_dependencies_cve,
    scan_sast_vulnerabilities,
    scan_secrets,
)


def test_offline_cve_database_loads():
    entries = load_offline_cve_database()
    assert len(entries) >= 5
    artifact_ids = [e["artifactId"] for e in entries]
    assert "snakeyaml" in artifact_ids
    assert "spring-webmvc" in artifact_ids
    assert "jackson-databind" in artifact_ids


# ---------------------------------------------------------------------------
# US1: Secrets & SAST tests
# ---------------------------------------------------------------------------
def test_scan_secrets_detects_all_patterns():
    files = {
        "src/main/resources/application.yml": """
server:
  port: 8080
security:
  openai-key: sk-proj-abc12345678901234567890abcdef
  groq-key: gsk_1234567890abcdefghijklmnopqrstuvwxyz1234
  aws-key: AKIAIOSFODNN7EXAMPLE
  jwt: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozGzT
  github-pat: ghp_1234567890abcdefghijklmnopqrstuvwx
""",
        "src/main/resources/key.pem": """
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Y1v...
-----END RSA PRIVATE KEY-----
""",
    }

    findings = scan_secrets(files)
    assert len(findings) >= 5
    categories = [f.category for f in findings]
    assert all(c == VulnerabilityCategory.SECRET_LEAK for c in categories)
    severities = [f.severity for f in findings]
    assert all(s == SeverityLevel.CRITICAL for s in severities)


def test_scan_sast_detects_sql_injection():
    files = {
        "src/main/java/com/corp/repository/OrderRepository.java": """
package com.corp.repository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

@Repository
public interface OrderRepository {
    @Query("SELECT o FROM Order o WHERE o.customer = '" + customerName + "'")
    List<Order> findByCustomer(String customerName);
}
"""
    }

    findings = scan_sast_vulnerabilities(files)
    assert len(findings) == 1
    assert findings[0].category == VulnerabilityCategory.SAST_INJECTION
    assert findings[0].severity == SeverityLevel.HIGH
    assert findings[0].cweId == "CWE-89"
    assert findings[0].autoFixAvailable is True


def test_scan_sast_detects_missing_valid_and_path_traversal():
    files = {
        "src/main/java/com/corp/controller/OrderController.java": """
package com.corp.controller;
import org.springframework.web.bind.annotation.*;
import java.io.File;

@RestController
public class OrderController {
    @PostMapping("/orders")
    public ResponseEntity<?> create(@RequestBody CreateOrderRequest req) {
        File file = new File("/tmp/" + req.filename);
        return ResponseEntity.ok().build();
    }
}
"""
    }

    findings = scan_sast_vulnerabilities(files)
    assert len(findings) == 2
    titles = [f.title for f in findings]
    assert any("Missing Jakarta @Valid" in t for t in titles)
    assert any("Potential Path Traversal" in t for t in titles)


# ---------------------------------------------------------------------------
# US2: Hermetic SCA tests
# ---------------------------------------------------------------------------
def test_scan_dependencies_cve_detects_vulnerable_versions():
    pom = """
<project>
  <dependencies>
    <dependency>
      <groupId>org.yaml</groupId>
      <artifactId>snakeyaml</artifactId>
      <version>1.30</version>
    </dependency>
    <dependency>
      <groupId>org.apache.logging.log4j</groupId>
      <artifactId>log4j-core</artifactId>
      <version>2.14.1</version>
    </dependency>
  </dependencies>
</project>
"""
    findings = scan_dependencies_cve(pom)
    assert len(findings) == 2
    assert any("CVE-2022-25857" in f.title for f in findings)
    assert any("CVE-2021-44228" in f.title for f in findings)
    log4j_finding = next(f for f in findings if "log4j-core" in f.title)
    assert log4j_finding.severity == SeverityLevel.CRITICAL


def test_scan_dependencies_cve_passes_safe_versions():
    pom = """
<project>
  <dependencies>
    <dependency>
      <groupId>org.yaml</groupId>
      <artifactId>snakeyaml</artifactId>
      <version>2.0</version>
    </dependency>
    <dependency>
      <groupId>org.apache.logging.log4j</groupId>
      <artifactId>log4j-core</artifactId>
      <version>2.17.1</version>
    </dependency>
  </dependencies>
</project>
"""
    findings = scan_dependencies_cve(pom)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# US3: Architecture & Quality Metrics tests
# ---------------------------------------------------------------------------
def test_scan_architecture_detects_violations():
    files = {
        "src/main/java/com/corp/controller/OrderController.java": """
package com.corp.controller;
import com.corp.repository.OrderRepository;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OrderController {
    private OrderRepository repository;
}
""",
        "src/main/java/com/corp/dto/OrderRequest.java": """
package com.corp.dto;

public class OrderRequest {
    private String item;
}
""",
        "src/main/java/com/corp/model/Order.java": """
package com.corp.model;
import lombok.Data;

@Data
public class Order {
    private Long id;
}
"""
    }

    violations = scan_architecture_compliance(files)
    assert len(violations) >= 3
    principles = [v.principle for v in violations]
    assert ConstitutionPrinciple.PRINCIPLE_I_LAYER_ISOLATION in principles
    assert ConstitutionPrinciple.PRINCIPLE_II_IMMUTABLE_DTOS in principles
    assert ConstitutionPrinciple.STACK_LOMBOK_RESTRICTION in principles
    # Also detects missing @RestControllerAdvice
    assert ConstitutionPrinciple.PRINCIPLE_III_CENTRALIZED_ERRORS in principles


def test_calculate_code_metrics():
    files = {
        "src/main/java/com/corp/service/OrderService.java": """
package com.corp.service;

public class OrderService {
    public void process(int a) {
        if (a > 10) {
            System.out.println("high");
        } else if (a > 5) {
            System.out.println("mid");
        } else {
            System.out.println("low");
        }
    }
}
""",
        "src/test/java/com/corp/service/OrderServiceTest.java": """
package com.corp.service;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

public class OrderServiceTest {
    @Test
    public void testProcess() {
        assertThat(true).isTrue();
    }
}
"""
    }

    metrics = calculate_code_metrics(files)
    assert metrics.totalMethodsAudited >= 1
    assert metrics.averageCyclomaticComplexity >= 2.0
    assert metrics.testAssertionDensity >= 1.0


# ---------------------------------------------------------------------------
# US4: Quality Gate & Surgical Remediation tests
# ---------------------------------------------------------------------------
def test_evaluate_quality_gate_blocking():
    # If CRITICAL or HIGH issue exists, status must be BLOCKED and canExport=False
    metrics = CodeQualityMetrics()
    secret_findings = scan_secrets({"src/app.yml": "secret: sk-proj-12345678901234567890abcdef"})
    verdict = evaluate_quality_gate(secret_findings, [], metrics)

    assert verdict.status == QualityGateStatus.BLOCKED
    assert verdict.canExport is False
    assert verdict.criticalCount >= 1
    assert verdict.score < 100


def test_evaluate_quality_gate_pass():
    metrics = CodeQualityMetrics()
    verdict = evaluate_quality_gate([], [], metrics)
    assert verdict.status == QualityGateStatus.PASS
    assert verdict.canExport is True
    assert verdict.score == 100


def test_apply_surgical_remediation():
    # Test DTO conversion
    dto_code = """package com.corp.dto;

public class CreateOrderRequest {
    private String customerEmail;
    private BigDecimal amount;
}
"""
    orig, rem, diff = apply_surgical_remediation("CONST-VIOL-001", "src/main/java/com/corp/dto/CreateOrderRequest.java", dto_code)
    assert "public record CreateOrderRequest(String customerEmail, BigDecimal amount)" in rem
    assert len(diff) > 0

    # Test Lombok @Data replacement
    lombok_code = """package com.corp.model;
import lombok.Data;

@Data
public class Order {
}
"""
    orig, rem, diff = apply_surgical_remediation("CONST-VIOL-002", "src/main/java/com/corp/model/Order.java", lombok_code)
    assert "@Getter" in rem
    assert "@Setter" in rem
    assert "@Builder" in rem
    assert "@Data" not in rem

