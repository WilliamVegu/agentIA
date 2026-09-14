import difflib
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.models.security_quality import (
    CodeQualityMetrics,
    ConstitutionPrinciple,
    QualityGateStatus,
    QualityGateVerdict,
    SecurityQualityAuditReport,
    SecurityVulnerabilityFinding,
    SeverityLevel,
    StandardsComplianceViolation,
    VulnerabilityCategory,
)

# ---------------------------------------------------------------------------
# Pre-cached Offline CVE Database Loader (Constitution Principle IV)
# ---------------------------------------------------------------------------
_CVE_DB_PATH = Path(__file__).resolve().parent.parent / "resources" / "cve_database.json"

def load_offline_cve_database() -> List[dict]:
    """Loads the pre-cached offline CVE database without making network calls."""
    if _CVE_DB_PATH.exists():
        try:
            with open(_CVE_DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("entries", [])
        except Exception:
            return []
    return []


# ---------------------------------------------------------------------------
# High-Entropy Secret Detection (Constitution Principle VI)
# ---------------------------------------------------------------------------
SECRET_PATTERNS = [
    {
        "id": "SEC-SECRET-JWT",
        "title": "Hardcoded JSON Web Token (JWT)",
        "pattern": re.compile(r"eyJ[a-zA-Z0-9_-]{5,}\.eyJ[a-zA-Z0-9_-]{5,}\.[a-zA-Z0-9_-]+"),
        "description": "Exposed hardcoded JWT token detected. Violates Constitution Principle VI.",
        "remediationGuidance": "Remove token immediately. Inject tokens securely at runtime via environment variables.",
    },
    {
        "id": "SEC-SECRET-AI-KEY",
        "title": "Hardcoded AI Model API Key (OpenAI / Anthropic / Gemini / Groq)",
        "pattern": re.compile(r"(?:sk-[a-zA-Z0-9_-]{20,}|sk-ant-[a-zA-Z0-9_-]{20,}|AIza[0-9A-Za-z-_]{35}|gsk_[a-zA-Z0-9_-]{20,})"),
        "description": "Hardcoded LLM API key detected. Violates Constitution Principle VI.",
        "remediationGuidance": "Use ephemeral environment variables (${LLM_API_KEY}) or corporate secret managers.",
    },
    {
        "id": "SEC-SECRET-AWS-KEY",
        "title": "Hardcoded AWS Access Key ID",
        "pattern": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "description": "AWS Access Key ID discovered in source code or configuration.",
        "remediationGuidance": "Rotate AWS keys and configure IAM instance roles or environment credentials.",
    },
    {
        "id": "SEC-SECRET-GITHUB-PAT",
        "title": "Hardcoded GitHub Personal Access Token",
        "pattern": re.compile(r"(?:ghp_[a-zA-Z0-9]{30,}|github_pat_[a-zA-Z0-9_]{50,})"),
        "description": "GitHub Personal Access Token hardcoded in codebase.",
        "remediationGuidance": "Revoke PAT and configure CI/CD ephemeral authentication.",
    },
    {
        "id": "SEC-SECRET-PRIVATE-KEY",
        "title": "Hardcoded Cryptographic Private Key",
        "pattern": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "description": "Cryptographic private key file or string embedded in source repository.",
        "remediationGuidance": "Extract private keys into secure vaults (e.g. HashiCorp Vault, AWS Secrets Manager).",
    },
    {
        "id": "SEC-SECRET-PASSWORD",
        "title": "Plaintext Database/Service Password in Configuration",
        "pattern": re.compile(r"""(?i)(?:password|passwd)\s*[:=]\s*["']?([^\s"']{4,})["']?"""),
        "description": "Hardcoded plaintext password found in configuration property.",
        "remediationGuidance": "Replace plaintext passwords with external environment variable interpolations.",
        "filter": lambda val: not ("${" in val or "test" in val.lower() or "demo" in val.lower())
    }
]


def scan_secrets(files: Dict[str, str]) -> List[SecurityVulnerabilityFinding]:
    """Scans all source code, configuration files, and scripts for hardcoded credentials."""
    findings = []
    finding_idx = 1

    for file_path, content in files.items():
        # Exclude binaries or compiled output paths
        if any(skip in file_path.lower() for skip in ["target/", ".git/", ".class"]):
            continue

        lines = content.splitlines()
        for line_num, line in enumerate(lines, 1):
            # Check suppression comment
            if "@SuppressWarnings(\"audit:secret\")" in line or "// audit-ignore-secret" in line:
                continue

            for secret_rule in SECRET_PATTERNS:
                matches = secret_rule["pattern"].finditer(line)
                for match in matches:
                    matched_val = match.group(0)
                    custom_filter = secret_rule.get("filter")
                    if custom_filter and not custom_filter(matched_val):
                        continue

                    # Obfuscate secret in snippet
                    obfuscated = line.replace(matched_val, matched_val[:4] + "..." + matched_val[-4:] if len(matched_val) > 8 else "****")
                    findings.append(
                        SecurityVulnerabilityFinding(
                            id=f"SEC-SECRET-{finding_idx:03d}",
                            title=secret_rule["title"],
                            category=VulnerabilityCategory.SECRET_LEAK,
                            severity=SeverityLevel.CRITICAL,
                            cweId="CWE-798",
                            owaspCategory="A07:2021-Identification and Authentication Failures",
                            filePath=file_path,
                            lineNumber=line_num,
                            codeSnippet=obfuscated.strip(),
                            description=secret_rule["description"],
                            remediationGuidance=secret_rule["remediationGuidance"],
                            autoFixAvailable=False,
                        )
                    )
                    finding_idx += 1
    return findings


# ---------------------------------------------------------------------------
# Static Application Security Testing (SAST) Rule Engine
# ---------------------------------------------------------------------------
def scan_sast_vulnerabilities(files: Dict[str, str]) -> List[SecurityVulnerabilityFinding]:
    """Executes high-speed deterministic SAST pattern analysis on Java source files."""
    findings = []
    finding_idx = 1

    for file_path, content in files.items():
        if not file_path.endswith(".java"):
            continue

        lines = content.splitlines()
        for line_num, line in enumerate(lines, 1):
            if "@SuppressWarnings(\"audit:sast\")" in line or "// audit-ignore" in line:
                continue

            # 1. SQL Injection: Concatenation in @Query or createNativeQuery / createQuery
            if ("@Query(" in line or "createNativeQuery(" in line or "createQuery(" in line) and (" + " in line or "+=" in line):
                findings.append(
                    SecurityVulnerabilityFinding(
                        id=f"SEC-SAST-{finding_idx:03d}",
                        title="SQL/JPQL Injection via Dynamic String Concatenation",
                        category=VulnerabilityCategory.SAST_INJECTION,
                        severity=SeverityLevel.HIGH,
                        cweId="CWE-89",
                        owaspCategory="A03:2021-Injection",
                        filePath=file_path,
                        lineNumber=line_num,
                        codeSnippet=line.strip(),
                        description="Dynamic string concatenation within query definition permits SQL/JPQL injection attacks.",
                        remediationGuidance="Use parameterized queries with named parameters (e.g., :paramName) or native Spring Data query derivation.",
                        autoFixAvailable=True,
                    )
                )
                finding_idx += 1

            # 2. Path Traversal: Unvalidated File or Paths.get with request parameters
            if ("new File(" in line or "Paths.get(" in line) and any(param in line for param in ["req.", "request.", "path", "filename", "filePath", "name"]):
                if not any(safe in line for safe in ["normalize()", "toRealPath()", "contains(\"..\")"]):
                    findings.append(
                        SecurityVulnerabilityFinding(
                            id=f"SEC-SAST-{finding_idx:03d}",
                            title="Potential Path Traversal in File Operations",
                            category=VulnerabilityCategory.SAST_ACCESS_CONTROL,
                            severity=SeverityLevel.HIGH,
                            cweId="CWE-22",
                            owaspCategory="A01:2021-Broken Access Control",
                            filePath=file_path,
                            lineNumber=line_num,
                            codeSnippet=line.strip(),
                            description="Unsanitized user-controlled file path construction permits directory traversal ../ attacks.",
                            remediationGuidance="Normalize path and verify that the target path starts with the intended base directory using Path.startsWith().",
                            autoFixAvailable=False,
                        )
                    )
                    finding_idx += 1

            # 3. Missing Jakarta @Valid on Controller @RequestBody
            if "@RequestBody" in line and "@Valid" not in line and "Controller" in file_path:
                findings.append(
                    SecurityVulnerabilityFinding(
                        id=f"SEC-SAST-{finding_idx:03d}",
                        title="Missing Jakarta @Valid on Controller RequestBody",
                        category=VulnerabilityCategory.SAST_INJECTION,
                        severity=SeverityLevel.MEDIUM,
                        cweId="CWE-20",
                        owaspCategory="A04:2021-Insecure Design",
                        filePath=file_path,
                        lineNumber=line_num,
                        codeSnippet=line.strip(),
                        description="Controller method accepts @RequestBody without triggering Jakarta validation (@Valid).",
                        remediationGuidance="Add @Valid annotation before @RequestBody (e.g. @Valid @RequestBody CreateOrderRequest req).",
                        autoFixAvailable=True,
                    )
                )
                finding_idx += 1

            # 4. Insecure Deserialization
            if "ObjectInputStream" in line and "readObject()" in line:
                findings.append(
                    SecurityVulnerabilityFinding(
                        id=f"SEC-SAST-{finding_idx:03d}",
                        title="Insecure Java Native Deserialization",
                        category=VulnerabilityCategory.SAST_DESERIALIZATION,
                        severity=SeverityLevel.HIGH,
                        cweId="CWE-502",
                        owaspCategory="A08:2021-Software and Data Integrity Failures",
                        filePath=file_path,
                        lineNumber=line_num,
                        codeSnippet=line.strip(),
                        description="Unrestricted native ObjectInputStream deserialization allows remote code execution via gadget chains.",
                        remediationGuidance="Use safe serialization formats such as JSON (Jackson) or validate allowed classes with ObjectInputFilter.",
                        autoFixAvailable=False,
                    )
                )
                finding_idx += 1

            # 5. Sensitive Data Logging
            if any(log in line for log in ["log.info(", "log.debug(", "log.warn(", "System.out.print"]) and any(
                sensitive in line.lower() for sensitive in ["password", "token", "apikey", "secret", "creditcard", "ssn"]
            ):
                findings.append(
                    SecurityVulnerabilityFinding(
                        id=f"SEC-SAST-{finding_idx:03d}",
                        title="Sensitive Credential or PII Exposure in Logs",
                        category=VulnerabilityCategory.SAST_DATA_EXPOSURE,
                        severity=SeverityLevel.MEDIUM,
                        cweId="CWE-532",
                        owaspCategory="A09:2021-Security Logging and Monitoring Failures",
                        filePath=file_path,
                        lineNumber=line_num,
                        codeSnippet=line.strip(),
                        description="Potentially sensitive security credential or PII is written to application logs.",
                        remediationGuidance="Mask or omit sensitive fields before logging.",
                        autoFixAvailable=False,
                    )
                )
                finding_idx += 1

    return findings


# ---------------------------------------------------------------------------
# Hermetic Dependency Vulnerability Analysis (SCA) (Constitution Principle IV)
# ---------------------------------------------------------------------------
def scan_dependencies_cve(pom_content: Optional[str]) -> List[SecurityVulnerabilityFinding]:
    """Inspects Maven dependencies in pom.xml against the local pre-cached CVE database."""
    if not pom_content:
        return []

    cve_entries = load_offline_cve_database()
    if not cve_entries:
        return []

    findings = []
    finding_idx = 1

    # Extract dependency blocks
    dep_regex = re.compile(r"<dependency>\s*<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>(?:\s*<version>([^<]+)</version>)?", re.DOTALL)
    matches = dep_regex.finditer(pom_content)

    for match in matches:
        group_id = match.group(1).strip()
        artifact_id = match.group(2).strip()
        version = (match.group(3) or "").strip()

        for cve in cve_entries:
            if cve["groupId"] == group_id and cve["artifactId"] == artifact_id:
                version_pattern = cve.get("vulnerableVersionPattern")
                is_vulnerable = False
                if version_pattern and version:
                    if re.search(version_pattern, version):
                        is_vulnerable = True
                elif not version:
                    # Inherited or unspecified version matching known vulnerable dependency
                    is_vulnerable = True

                if is_vulnerable:
                    severity = SeverityLevel.CRITICAL if cve["severity"].upper() == "CRITICAL" else SeverityLevel.HIGH
                    findings.append(
                        SecurityVulnerabilityFinding(
                            id=f"SEC-CVE-{finding_idx:03d}",
                            title=f"Dependency Vulnerability: {cve['cveId']} in {group_id}:{artifact_id}",
                            category=VulnerabilityCategory.CVE_DEPENDENCY,
                            severity=severity,
                            cweId="CWE-1395",
                            owaspCategory="A06:2021-Vulnerable and Outdated Components",
                            filePath="pom.xml",
                            lineNumber=1,
                            codeSnippet=f"<groupId>{group_id}</groupId>\n<artifactId>{artifact_id}</artifactId>\n<version>{version}</version>",
                            description=cve["description"],
                            remediationGuidance=cve["remediationGuidance"],
                            autoFixAvailable=True,
                        )
                    )
                    finding_idx += 1

    return findings


# ---------------------------------------------------------------------------
# Architectural Standards Compliance (Constitution Principles I, II, III, Lombok)
# ---------------------------------------------------------------------------
def scan_architecture_compliance(files: Dict[str, str]) -> List[StandardsComplianceViolation]:
    """Verifies compliance with Constitution Principles I, II, III, and Project Lombok restrictions."""
    violations = []
    viol_idx = 1
    has_rest_controller_advice = False

    for file_path, content in files.items():
        if not file_path.endswith(".java"):
            continue

        if "@RestControllerAdvice" in content or "@ControllerAdvice" in content:
            has_rest_controller_advice = True

        # Principle I: Strict 4-Layer Unidirectional Flow
        # Controllers cannot import repositories or models directly
        if "controller" in file_path.lower() or file_path.endswith("Controller.java"):
            if "import " in content and (".repository." in content or "Repository;" in content):
                violations.append(
                    StandardsComplianceViolation(
                        id=f"CONST-VIOL-{viol_idx:03d}",
                        principle=ConstitutionPrinciple.PRINCIPLE_I_LAYER_ISOLATION,
                        severity=SeverityLevel.HIGH,
                        filePath=file_path,
                        offendingElement="Controller directly imports Repository",
                        ruleDescription="Constitution Principle I Violation: Controllers MUST only interact with Services, never directly with Repositories.",
                        suggestedFix="Delegate persistence calls through the Service interface layer.",
                        autoFixAvailable=False,
                    )
                )
                viol_idx += 1

            # Principle III: No ad-hoc try-catch in controllers returning error responses
            if "try {" in content and "catch (" in content and ("ResponseEntity.status(" in content or "HttpStatus." in content):
                violations.append(
                    StandardsComplianceViolation(
                        id=f"CONST-VIOL-{viol_idx:03d}",
                        principle=ConstitutionPrinciple.PRINCIPLE_III_CENTRALIZED_ERRORS,
                        severity=SeverityLevel.MEDIUM,
                        filePath=file_path,
                        offendingElement="Ad-hoc try-catch block in Controller",
                        ruleDescription="Constitution Principle III Violation: Controllers must not catch exceptions for custom error bodies; exceptions must bubble to @RestControllerAdvice.",
                        suggestedFix="Remove local try-catch and handle exceptions centrally in the @RestControllerAdvice handler.",
                        autoFixAvailable=False,
                    )
                )
                viol_idx += 1

        # Principle II: Immutable DTOs via Java Records
        if "dto" in file_path.lower() or "/dto/" in file_path:
            if "public class " in content and "public record " not in content:
                class_match = re.search(r"public\s+class\s+([A-Za-z0-9_]+)", content)
                offending = class_match.group(1) if class_match else "DTO Class"
                violations.append(
                    StandardsComplianceViolation(
                        id=f"CONST-VIOL-{viol_idx:03d}",
                        principle=ConstitutionPrinciple.PRINCIPLE_II_IMMUTABLE_DTOS,
                        severity=SeverityLevel.HIGH,
                        filePath=file_path,
                        offendingElement=f"Class {offending}",
                        ruleDescription="Constitution Principle II Violation: Request and Response DTOs MUST be implemented as immutable Java Records.",
                        suggestedFix=f"Convert 'public class {offending}' to 'public record {offending}(...)' with Jakarta validation annotations.",
                        autoFixAvailable=True,
                    )
                )
                viol_idx += 1

        # Stack Rule: Lombok Restrictions (@Data, @Value, @SneakyThrows strictly prohibited)
        for prohibited in ["@Data", "@Value", "@SneakyThrows"]:
            if prohibited in content:
                violations.append(
                    StandardsComplianceViolation(
                        id=f"CONST-VIOL-{viol_idx:03d}",
                        principle=ConstitutionPrinciple.STACK_LOMBOK_RESTRICTION,
                        severity=SeverityLevel.HIGH,
                        filePath=file_path,
                        offendingElement=prohibited,
                        ruleDescription=f"Constitution Stack Violation: Prohibited Lombok annotation {prohibited} detected.",
                        suggestedFix="Replace @Data with explicit @Getter @Setter @Builder @NoArgsConstructor @AllArgsConstructor.",
                        autoFixAvailable=True,
                    )
                )
                viol_idx += 1

    # Principle III: Check global presence of @RestControllerAdvice
    java_files = [f for f in files.keys() if f.endswith(".java")]
    if java_files and not has_rest_controller_advice:
        violations.append(
            StandardsComplianceViolation(
                id=f"CONST-VIOL-{viol_idx:03d}",
                principle=ConstitutionPrinciple.PRINCIPLE_III_CENTRALIZED_ERRORS,
                severity=SeverityLevel.HIGH,
                filePath="src/main/java",
                offendingElement="Missing @RestControllerAdvice",
                ruleDescription="Constitution Principle III Violation: A centralized exception handler annotated with @RestControllerAdvice is required.",
                suggestedFix="Implement a GlobalExceptionHandler class annotated with @RestControllerAdvice returning ProblemDetails (RFC 7807).",
                autoFixAvailable=False,
            )
        )
        viol_idx += 1

    return violations


# ---------------------------------------------------------------------------
# Quantitative Code Maintainability Metrics (Clean Code / SonarQube)
# ---------------------------------------------------------------------------
def calculate_code_metrics(files: Dict[str, str]) -> CodeQualityMetrics:
    """Calculates quantitative Clean Code maintainability metrics across Java files."""
    total_loc = 0
    total_methods = 0
    methods_exceeding = 0
    complexities = []
    test_assertions = 0
    total_test_methods = 0
    line_hashes = {}
    duplicate_lines = 0

    method_start_pattern = re.compile(r"^\s*(?:public|protected|private|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)\s*\{?")
    branch_keywords = [" if ", " if(", " else if ", " for ", " for(", " while ", " while(", " case ", " catch ", " && ", " || ", " ? "]

    for file_path, content in files.items():
        if not file_path.endswith(".java"):
            continue

        lines = content.splitlines()
        is_test_file = "test" in file_path.lower() or file_path.endswith("Test.java")

        in_method = False
        current_method_loc = 0
        current_method_complexity = 1

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue

            total_loc += 1

            # Simple duplication detection
            if len(stripped) > 20 and not is_test_file:
                if stripped in line_hashes:
                    duplicate_lines += 1
                else:
                    line_hashes[stripped] = True

            # Test assertions
            if is_test_file:
                if "@Test" in stripped:
                    total_test_methods += 1
                if any(assert_kw in stripped for assert_kw in ["assert", "verify(", "expect("]):
                    test_assertions += 1

            # Method detection
            if method_start_pattern.search(line):
                if in_method:
                    # Closing previous method
                    complexities.append(current_method_complexity)
                    if current_method_complexity > 10 or current_method_loc > 50:
                        methods_exceeding += 1
                    total_methods += 1

                in_method = True
                current_method_loc = 0
                current_method_complexity = 1
                continue

            if in_method:
                current_method_loc += 1
                for kw in branch_keywords:
                    if kw in f" {stripped} ":
                        current_method_complexity += 1

                if stripped == "}" and current_method_loc > 2:
                    complexities.append(current_method_complexity)
                    if current_method_complexity > 10 or current_method_loc > 50:
                        methods_exceeding += 1
                    total_methods += 1
                    in_method = False

    avg_complexity = round(sum(complexities) / len(complexities), 2) if complexities else 1.0
    max_complexity = max(complexities) if complexities else 1
    duplication_pct = round((duplicate_lines / total_loc * 100), 2) if total_loc > 0 else 0.0
    assertion_density = round(test_assertions / total_test_methods, 2) if total_test_methods > 0 else 0.0

    return CodeQualityMetrics(
        averageCyclomaticComplexity=avg_complexity,
        maxCyclomaticComplexity=max_complexity,
        totalMethodsAudited=total_methods,
        methodsExceedingThreshold=methods_exceeding,
        totalLinesOfCode=total_loc,
        duplicationPercentage=duplication_pct,
        testAssertionDensity=assertion_density,
        totalCodeSmells=methods_exceeding,
    )


# ---------------------------------------------------------------------------
# Composite Quality Gate Evaluation
# ---------------------------------------------------------------------------
def evaluate_quality_gate(
    vulnerabilities: List[SecurityVulnerabilityFinding],
    violations: List[StandardsComplianceViolation],
    metrics: CodeQualityMetrics,
) -> QualityGateVerdict:
    """Evaluates composite Quality Gate score and blocking status."""
    critical_count = sum(1 for v in vulnerabilities if v.severity == SeverityLevel.CRITICAL) + sum(
        1 for v in violations if v.severity == SeverityLevel.CRITICAL
    )
    high_count = sum(1 for v in vulnerabilities if v.severity == SeverityLevel.HIGH) + sum(
        1 for v in violations if v.severity == SeverityLevel.HIGH
    )
    medium_count = sum(1 for v in vulnerabilities if v.severity == SeverityLevel.MEDIUM) + sum(
        1 for v in violations if v.severity == SeverityLevel.MEDIUM
    )
    low_count = sum(1 for v in vulnerabilities if v.severity == SeverityLevel.LOW) + sum(
        1 for v in violations if v.severity == SeverityLevel.LOW
    )

    # Score calculation
    penalty = (critical_count * 30) + (high_count * 15) + (medium_count * 5) + (low_count * 2)
    if metrics.methodsExceedingThreshold > 0:
        penalty += min(metrics.methodsExceedingThreshold * 3, 15)
    score = max(0, 100 - penalty)

    if critical_count > 0 or high_count > 0:
        status = QualityGateStatus.BLOCKED
        can_export = False
        summary = f"Quality Gate BLOCKED: {critical_count} Critical and {high_count} High issues prevent export or publishing."
    elif medium_count > 0 or low_count > 0 or metrics.methodsExceedingThreshold > 0:
        status = QualityGateStatus.WARNING
        can_export = True
        summary = f"Quality Gate WARNING: {medium_count} Medium and {low_count} Low findings detected. Code export is permitted."
    else:
        status = QualityGateStatus.PASS
        can_export = True
        summary = "Quality Gate PASSED: Zero security flaws or constitutional violations. Clean code standards met."

    return QualityGateVerdict(
        status=status,
        score=score,
        criticalCount=critical_count,
        highCount=high_count,
        mediumCount=medium_count,
        lowCount=low_count,
        canExport=can_export,
        summaryMessage=summary,
    )


# ---------------------------------------------------------------------------
# Surgical 1-Click Remediation Engine
# ---------------------------------------------------------------------------
def apply_surgical_remediation(finding_id: str, file_path: str, source_code: str) -> Tuple[str, str, str]:
    """Generates a surgical patch correcting known patterns and returns (original, remediated, diff)."""
    original = source_code
    remediated = source_code

    # 1. Fix Lombok @Data -> @Getter @Setter @Builder @NoArgsConstructor @AllArgsConstructor
    if "@Data" in remediated:
        lombok_replacement = "@Getter\n@Setter\n@Builder\n@NoArgsConstructor\n@AllArgsConstructor"
        remediated = re.sub(r"@Data\b", lombok_replacement, remediated)

    # 2. Fix DTO Class -> Java Record
    if "dto" in file_path.lower() and "public class " in remediated:
        # Simple transformation of fields to record components
        class_match = re.search(r"public\s+class\s+(\w+)\s*\{([^}]+)\}", remediated, re.DOTALL)
        if class_match:
            record_name = class_match.group(1)
            body = class_match.group(2)
            # Find field declarations: private Type name;
            field_matches = re.findall(r"private\s+([\w<>\[\]]+)\s+(\w+)\s*;", body)
            if field_matches:
                params = ", ".join([f"{f_type} {f_name}" for f_type, f_name in field_matches])
                record_def = f"public record {record_name}({params}) {{\n}}"
                remediated = remediated[: class_match.start()] + record_def + remediated[class_match.end() :]

    # 3. Fix Missing @Valid before @RequestBody
    if "@RequestBody" in remediated and "@Valid @RequestBody" not in remediated:
        remediated = re.sub(r"@RequestBody\b", "@Valid @RequestBody", remediated)

    # 4. Fix SQL Injection in @Query
    if "@Query(" in remediated and " + " in remediated:
        # Replace string concatenation like '\" + name + \"' with ':name'
        remediated = re.sub(r"""['"]\s*\+\s*(\w+)\s*\+\s*['"]""", r":\1", remediated)

    # 5. Fix Dependency Vulnerability in pom.xml (e.g. snakeyaml 1.30 -> 2.0)
    if file_path.endswith("pom.xml"):
        for cve in load_offline_cve_database():
            artifact = cve["artifactId"]
            safe_ver = cve["safeVersion"]
            pattern = rf"(<artifactId>{artifact}</artifactId>\s*<version>)[^<]+(</version>)"
            remediated = re.sub(pattern, rf"\g<1>{safe_ver}\g<2>", remediated)

    # Compute unified diff
    diff_lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        remediated.splitlines(keepends=True),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    diff_text = "".join(diff_lines)

    return original, remediated, diff_text


# ---------------------------------------------------------------------------
# Workspace Audit Orchestrator
# ---------------------------------------------------------------------------
def audit_workspace(workspace_dir: str, session_id: str, service_name: str = "microservice") -> SecurityQualityAuditReport:
    """Scans all relevant files in a session workspace and computes the complete audit report."""
    ws_path = Path(workspace_dir)
    files: Dict[str, str] = {}
    pom_content: Optional[str] = None

    if ws_path.exists() and ws_path.is_dir():
        for root, _, filenames in os.walk(ws_path):
            for filename in filenames:
                file_abs = Path(root) / filename
                rel_path = file_abs.relative_to(ws_path).as_posix()
                if rel_path.endswith((".java", ".yml", ".yaml", ".properties", ".xml", ".sql", "Dockerfile")):
                    try:
                        with open(file_abs, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            files[rel_path] = content
                            if rel_path == "pom.xml" or rel_path.endswith("/pom.xml"):
                                pom_content = content
                    except Exception:
                        pass

    # Run all scanners
    secret_findings = scan_secrets(files)
    sast_findings = scan_sast_vulnerabilities(files)
    cve_findings = scan_dependencies_cve(pom_content)
    vulnerabilities = secret_findings + sast_findings + cve_findings

    violations = scan_architecture_compliance(files)
    metrics = calculate_code_metrics(files)
    quality_gate = evaluate_quality_gate(vulnerabilities, violations, metrics)

    report = SecurityQualityAuditReport(
        sessionId=session_id,
        serviceName=service_name,
        qualityGate=quality_gate,
        metrics=metrics,
        vulnerabilities=vulnerabilities,
        violations=violations,
    )

    # Cache report in workspace if possible
    try:
        report_file = ws_path / "security_audit_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
    except Exception:
        pass

    return report
