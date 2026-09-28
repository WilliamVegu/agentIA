"""Compliance adapter and allowlist rule tests.

Scope: T014 (verdict normalization) and T049 (dependency-allowlist enforcement).
These are the unit-level checks for the two rules implemented in
``app/orchestrator/stages/compliance.py``.

This file is created by T049 because that task directs its allowlist test here;
T029 extends the same file with the model-path behaviour tests, and T033-T035 add
the end-to-end fault injection. It deliberately contains only what T014 and T049
own, so those later tasks have room to add without rewriting.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.orchestrator.stages.compliance import (  # noqa: E402
    ATTRIBUTION_ACCUMULATED,
    ATTRIBUTION_LOCAL,
    RULE_CREDENTIAL_IN_ARTIFACT,
    RULE_DEPENDENCY_NOT_ALLOWED,
    blocking_local_violations,
    check_artifact_credentials,
    check_dependency_allowlist,
    load_dependency_allowlist,
    normalize_verdict,
)

ALLOWLIST_PATH = REPO_ROOT / "backend" / "app" / "resources" / "dependency_allowlist.json"
CONTROLLER_SCOPE = ("src/main/java/*/controller/*.java",)


def _allowlisted_pom() -> str:
    return """
    <project xmlns="http://maven.apache.org/POM/4.0.0">
      <modelVersion>4.0.0</modelVersion>
      <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.3</version>
      </parent>
      <dependencies>
        <dependency>
          <groupId>org.springframework.boot</groupId>
          <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
      </dependencies>
      <build>
        <plugins>
          <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-compiler-plugin</artifactId>
          </plugin>
        </plugins>
      </build>
    </project>
    """


UNLISTED_DEP_POM = """
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.3</version>
  </parent>
  <dependencies>
    <dependency>
      <groupId>com.example.unlisted</groupId>
      <artifactId>not-cached-anywhere</artifactId>
    </dependency>
  </dependencies>
</project>
"""


# ---------------------------------------------------------------------------
# T049 — dependency allowlist enforcement
# ---------------------------------------------------------------------------
def test_allowlist_rule_fires_on_unlisted_dependency():
    violations = check_dependency_allowlist(
        UNLISTED_DEP_POM, artifact_path="pom.xml", stage_scope=("pom.xml",)
    )
    assert violations, "an unlisted dependency must produce a violation"
    assert all(v.rule_id == RULE_DEPENDENCY_NOT_ALLOWED for v in violations)
    assert all(v.blocking for v in violations), "the allowlist rule is BLOCKING"
    assert all(v.attribution == ATTRIBUTION_LOCAL for v in violations)
    assert "com.example.unlisted:not-cached-anywhere" in violations[0].message


def test_allowlist_rule_passes_on_allowlisted_dependency():
    assert check_dependency_allowlist(
        _allowlisted_pom(), artifact_path="pom.xml", stage_scope=("pom.xml",)
    ) == []


def test_allowlist_rule_rejects_non_deterministic_version_selectors():
    pom = """
    <project xmlns="http://maven.apache.org/POM/4.0.0">
      <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.3</version>
      </parent>
      <dependencies>
        <dependency>
          <groupId>org.springframework.boot</groupId>
          <artifactId>spring-boot-starter-web</artifactId>
          <version>1.0.0-SNAPSHOT</version>
        </dependency>
      </dependencies>
    </project>
    """
    violations = check_dependency_allowlist(pom, stage_scope=("pom.xml",))
    assert violations
    assert all(v.blocking for v in violations)
    assert any("SNAPSHOT" in v.message for v in violations)


def test_allowlist_rule_rejects_additional_remote_repository():
    pom = _allowlisted_pom().replace(
        "</project>",
        "  <repositories><repository><id>x</id><url>https://example.invalid</url></repository></repositories>\n</project>",
    )
    violations = check_dependency_allowlist(pom, stage_scope=("pom.xml",))
    assert any("remote repository" in v.message for v in violations)


def test_allowlist_rule_flags_malformed_pom():
    violations = check_dependency_allowlist("<project><unclosed>", stage_scope=("pom.xml",))
    assert violations and violations[0].blocking


def test_allowlist_file_loads_and_is_outside_instructions_dir():
    data = load_dependency_allowlist()
    assert data["dependencies"], "the allowlist must declare dependencies"
    assert "instructions" not in str(ALLOWLIST_PATH), (
        "the allowlist must live outside the instructions directory so editing it "
        "does not perturb the instruction-set revision"
    )
    # Sanity: every declared dependency carries the coordinates the rule compares.
    for dep in data["dependencies"]:
        assert dep["groupId"] and dep["artifactId"]


# ---------------------------------------------------------------------------
# T014 — verdict normalization
# ---------------------------------------------------------------------------
CONTROLLER_IMPORTING_REPOSITORY = {
    "src/main/java/com/corp/x/controller/XController.java": (
        "package com.corp.x.controller;\n"
        "import com.corp.x.repository.XRepository;\n"
        "public class XController { private XRepository repository; }\n"
    ),
    "src/main/java/com/corp/x/controller/GlobalExceptionHandler.java": (
        "package com.corp.x.controller;\n@RestControllerAdvice\npublic class GlobalExceptionHandler {}\n"
    ),
}


def test_adapter_invokes_both_validator_families():
    """Guardrail 3: both families are consulted, and both are credited."""
    verdict = normalize_verdict(
        CONTROLLER_IMPORTING_REPOSITORY, stage_scope=CONTROLLER_SCOPE
    )
    assert len(verdict.sources) == 2, f"expected both families, got {verdict.sources}"
    assert any("test_analysis_service" in s for s in verdict.sources)
    assert any("security_service" in s for s in verdict.sources)


def test_adapter_deduplicates_same_rule_and_unions_sources():
    verdict = normalize_verdict(
        CONTROLLER_IMPORTING_REPOSITORY, stage_scope=CONTROLLER_SCOPE
    )
    layer = [v for v in verdict.violations if v.rule_id == "PRINCIPLE_I_LAYER_ISOLATION"]
    assert len(layer) == 1, "the same rule reported by both families must collapse to one row"
    assert len(layer[0].contributing_sources) == 2, (
        "both reporting families must remain visible after the merge"
    )


def test_adapter_keeps_the_strictest_severity_on_collision():
    """Family A rates a Lombok violation MEDIUM, family B rates it HIGH.

    The merged verdict must keep HIGH, which makes it blocking. This is the
    deliberate tightening recorded in contracts/compliance-verdict.md §5.
    """
    files = {
        "src/main/java/com/corp/x/model/entity/X.java": (
            "package com.corp.x.model.entity;\n@Data\npublic class X {}\n"
        ),
        "src/main/java/com/corp/x/controller/GlobalExceptionHandler.java": (
            "package com.corp.x.controller;\n@RestControllerAdvice\npublic class GlobalExceptionHandler {}\n"
        ),
    }
    verdict = normalize_verdict(files, stage_scope=("src/main/java/*/model/entity/*.java",))
    lombok = [v for v in verdict.violations if v.rule_id == "STACK_LOMBOK_RESTRICTION"]
    assert lombok, "the prohibited-annotation rule must fire"
    assert lombok[0].severity == "HIGH", f"expected the strictest severity, got {lombok[0].severity}"
    assert lombok[0].blocking


def test_whole_project_rule_is_accumulated_not_local():
    """FR-006: a stage must not be blamed for a rule only the project can satisfy.

    With no @RestControllerAdvice anywhere, family B reports the omission against
    'src/main/java', which is outside every stage's artifact scope.
    """
    files = {
        "src/main/java/com/corp/x/domain/X.java": "package com.corp.x.domain;\npublic class X {}\n",
    }
    verdict = normalize_verdict(files, stage_scope=("src/main/java/*/domain/*.java",))
    missing_advice = [
        v for v in verdict.violations if v.rule_id == "PRINCIPLE_III_CENTRALIZED_ERRORS"
    ]
    assert missing_advice, "the whole-project rule must still be reported"
    assert all(v.attribution == ATTRIBUTION_ACCUMULATED for v in missing_advice)
    assert blocking_local_violations(verdict) == (), (
        "an accumulated violation must not reject the stage that cannot satisfy it"
    )
    assert verdict.passed, "the stage itself has no local blocking violation"


def test_local_violations_do_reject_and_are_returned():
    verdict = normalize_verdict(
        CONTROLLER_IMPORTING_REPOSITORY, stage_scope=CONTROLLER_SCOPE
    )
    blockers = blocking_local_violations(verdict)
    assert blockers and all(v.attribution == ATTRIBUTION_LOCAL for v in blockers)
    assert not verdict.passed
    assert verdict.local_blocking_count == len(blockers)


def test_clean_artifact_set_passes():
    files = {
        "src/main/java/com/corp/x/controller/GlobalExceptionHandler.java": (
            "package com.corp.x.controller;\n@RestControllerAdvice\npublic class GlobalExceptionHandler {}\n"
        ),
    }
    verdict = normalize_verdict(files, stage_scope=CONTROLLER_SCOPE)
    assert verdict.passed
    assert blocking_local_violations(verdict) == ()


# ---------------------------------------------------------------------------
# FR-018 — credential rule (added because neither validator family checks secrets)
# ---------------------------------------------------------------------------
def test_credential_rule_flags_embedded_secret():
    files = {
        "src/main/java/com/corp/x/Config.java": (
            'package com.corp.x;\npublic class Config { static final String K = '
            '"AIzaSyA1234567890abcdefghijklmnopqrstuv"; }\n'
        )
    }
    violations = check_artifact_credentials(files)
    assert violations
    assert violations[0].rule_id == RULE_CREDENTIAL_IN_ARTIFACT
    assert violations[0].blocking


def test_credential_rule_is_part_of_the_verdict():
    files = {
        "src/main/java/com/corp/x/controller/GlobalExceptionHandler.java": (
            "package com.corp.x.controller;\n@RestControllerAdvice\npublic class GlobalExceptionHandler {}\n"
        ),
        "src/main/java/com/corp/x/Config.java": (
            'package com.corp.x;\npublic class Config { static final String K = '
            '"sk-abcdefghijklmnopqrstuvwx"; }\n'
        ),
    }
    verdict = normalize_verdict(files, stage_scope=("src/main/java/*/Config.java",))
    assert not verdict.passed
    assert any(v.rule_id == RULE_CREDENTIAL_IN_ARTIFACT for v in verdict.violations)
