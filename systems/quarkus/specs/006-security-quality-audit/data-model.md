# Data Model: Security Vulnerability Auditing & Code Quality Standards

**Feature**: `006-security-quality-audit`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. Domain Entities & Schemas

```mermaid
classDiagram
    class SecurityQualityAuditReport {
        +string sessionId
        +string serviceName
        +QualityGateVerdict qualityGate
        +CodeQualityMetrics metrics
        +List~SecurityVulnerabilityFinding~ vulnerabilities
        +List~StandardsComplianceViolation~ violations
        +datetime auditedAt
    }

    class QualityGateVerdict {
        +QualityGateStatus status
        +int score
        +int criticalCount
        +int highCount
        +int mediumCount
        +int lowCount
        +bool canExport
        +string summaryMessage
    }

    class SecurityVulnerabilityFinding {
        +string id
        +string title
        +VulnerabilityCategory category
        +SeverityLevel severity
        +string cweId
        +string owaspCategory
        +string filePath
        +int lineNumber
        +string codeSnippet
        +string description
        +string remediationGuidance
        +bool autoFixAvailable
    }

    class StandardsComplianceViolation {
        +string id
        +ConstitutionPrinciple principle
        +SeverityLevel severity
        +string filePath
        +string offendingElement
        +string ruleDescription
        +string suggestedFix
        +bool autoFixAvailable
    }

    class CodeQualityMetrics {
        +float averageCyclomaticComplexity
        +int maxCyclomaticComplexity
        +int totalMethodsAudited
        +int methodsExceedingThreshold
        +int totalLinesOfCode
        +float duplicationPercentage
        +float testAssertionDensity
        +int totalCodeSmells
    }

    class QualityGateStatus {
        <<enumeration>>
        PASS
        WARNING
        BLOCKED
    }

    class SeverityLevel {
        <<enumeration>>
        CRITICAL
        HIGH
        MEDIUM
        LOW
    }

    class VulnerabilityCategory {
        <<enumeration>>
        SAST_INJECTION
        SAST_DESERIALIZATION
        SAST_ACCESS_CONTROL
        SAST_DATA_EXPOSURE
        SECRET_LEAK
        CVE_DEPENDENCY
    }

    class ConstitutionPrinciple {
        <<enumeration>>
        PRINCIPLE_I_LAYER_ISOLATION
        PRINCIPLE_II_IMMUTABLE_DTOS
        PRINCIPLE_III_CENTRALIZED_ERRORS
        PRINCIPLE_IV_OFFLINE_DETERMINISM
        PRINCIPLE_V_QUALITY_GATES
        PRINCIPLE_VI_ZERO_SECRETS
        STACK_LOMBOK_RESTRICTION
    }

    SecurityQualityAuditReport *-- QualityGateVerdict
    SecurityQualityAuditReport *-- CodeQualityMetrics
    SecurityQualityAuditReport o-- SecurityVulnerabilityFinding
    SecurityQualityAuditReport o-- StandardsComplianceViolation
    QualityGateVerdict --> QualityGateStatus
    SecurityVulnerabilityFinding --> SeverityLevel
    SecurityVulnerabilityFinding --> VulnerabilityCategory
    StandardsComplianceViolation --> SeverityLevel
    StandardsComplianceViolation --> ConstitutionPrinciple
```

---

## 2. JSON Schema Definitions

### 2.1 `QualityGateVerdict`
Represents the overarching security and quality decision governing whether code is allowed to be exported or published.

```json
{
  "status": "BLOCKED",
  "score": 68,
  "criticalCount": 1,
  "highCount": 1,
  "mediumCount": 2,
  "lowCount": 0,
  "canExport": false,
  "summaryMessage": "Quality Gate BLOCKED: 1 Critical secret leak and 1 High SQL injection risk detected."
}
```

### 2.2 `SecurityVulnerabilityFinding`
Represents an actionable security defect identified in source code or dependencies.

```json
{
  "id": "SEC-VULN-001",
  "title": "SQL Injection in Repository Query",
  "category": "SAST_INJECTION",
  "severity": "HIGH",
  "cweId": "CWE-89",
  "owaspCategory": "A03:2021-Injection",
  "filePath": "src/main/java/com/corp/order/repository/OrderRepository.java",
  "lineNumber": 18,
  "codeSnippet": "@Query(\"SELECT o FROM Order o WHERE o.customer = '\" + customerName + \"'\")",
  "description": "Dynamic string concatenation in Spring Data @Query enables SQL/JPQL injection attacks.",
  "remediationGuidance": "Use parameterized queries: @Query(\"SELECT o FROM Order o WHERE o.customer = :customerName\")",
  "autoFixAvailable": true
}
```

### 2.3 `StandardsComplianceViolation`
Represents a breach of constitutional guidelines, Clean Code principles, or architectural rules.

```json
{
  "id": "CONST-VIOL-001",
  "principle": "PRINCIPLE_II_IMMUTABLE_DTOS",
  "severity": "HIGH",
  "filePath": "src/main/java/com/corp/order/dto/CreateOrderRequest.java",
  "offendingElement": "public class CreateOrderRequest",
  "ruleDescription": "Constitution Principle II Violation: Request DTOs MUST be immutable Java Records with Jakarta validation.",
  "suggestedFix": "Convert class to public record CreateOrderRequest(@NotBlank String customerEmail, @NotNull BigDecimal totalAmount)",
  "autoFixAvailable": true
}
```

### 2.4 `CodeQualityMetrics`
Captures structural maintainability metrics across all compiled or generated classes.

```json
{
  "averageCyclomaticComplexity": 2.4,
  "maxCyclomaticComplexity": 14,
  "totalMethodsAudited": 28,
  "methodsExceedingThreshold": 1,
  "totalLinesOfCode": 450,
  "duplicationPercentage": 1.2,
  "testAssertionDensity": 2.8,
  "totalCodeSmells": 2
}
```

---

## 3. Interaction & Lifecycle Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as Developer / Web Studio
    participant API as FastAPI Security Service
    participant SAST as Static Rule Analyzer
    participant CVE as Local CVE Database
    participant Arch as Architecture Inspector
    participant Gate as Quality Gate Evaluator

    User->>API: POST /api/v1/security/audit (sourceFiles, pomXml)
    activate API
    API->>SAST: Scan source code for OWASP patterns & secrets
    SAST-->>API: List of SAST & Secret findings
    API->>CVE: Inspect pom.xml dependencies against local dictionary
    CVE-->>API: List of dependency CVE findings
    API->>Arch: Evaluate 4 layers, Records, @RestControllerAdvice, Lombok
    Arch-->>API: List of Constitution & Maintainability violations
    API->>Gate: Compute composite Quality Gate score & status
    Gate-->>API: QualityGateVerdict (PASS / WARNING / BLOCKED)
    API-->>User: SecurityQualityAuditReport
    deactivate API

    opt If Quality Gate is BLOCKED and Auto-Fix is Requested
        User->>API: POST /api/v1/security/remediate (findingId, filePath)
        activate API
        API->>API: Apply surgical patch (e.g. convert DTO to Record, parameterize SQL)
        API-->>User: Remediated source code & updated QualityGateVerdict
        deactivate API
    end
```

