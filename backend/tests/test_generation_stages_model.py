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


# =========================================================================
# T029 — model-path behaviour (User Story 1)
#
# Scope: the five model-driven stages (T024-T028) as dispatched by the stage
# execution boundary, driven by the scripted fake client from T017.
#
# Every test here runs against the fake client: NO test makes a network call
# (Constitution Principle VI). The fake is deliberately not the platform's mock
# provider — mock returns no client, which is the deterministic-fallback trigger,
# so using it would exercise the offline path instead of the model path.
#
# T033-T035 (Phase 4) extend this file with adversarial fault injection and the
# journal/budget checks.
#
# Imports for this section are added here rather than in the header block so the
# T014/T049 section above stays exactly as it was.
# =========================================================================
import re  # noqa: E402

from app.orchestrator.stages import journal as journal_mod  # noqa: E402
from app.orchestrator.stages.runner import (  # noqa: E402
    STAGE_ORDER,
    build_stage_payload,
    render_stage_request,
    run_stage,
)
from app.services.llm_factory import LLMFactory  # noqa: E402
from tests.fixtures import fake_model as fm  # noqa: E402

CORPUS_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "baseline_blueprints"
BASELINE_JSON = REPO_ROOT / "reports" / "baselines" / "011-pre-migration-generation-baseline.json"


def _blueprint(name: str) -> dict:
    return json.loads((CORPUS_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _model_state(blueprint: dict, workspace: Path) -> dict:
    return {
        "session_id": "t029",
        "blueprint": blueprint,
        "workspace_path": str(workspace),
        "generated_files": {},
        "logs": [],
        "generation_mode": journal_mod.GENERATION_MODE_MODEL,
        "llm_provider": "deepseek",
        "llm_model": "deepseek-flash",
        "llm_api_key": "sk-fake-key-for-tests",
    }


def _script(monkeypatch, *responses: str) -> fm.ScriptedChatModel:
    """Point the factory at a scripted fake and return it so calls can be read."""
    model = fm.make_scripted_model(*responses)
    monkeypatch.setattr(LLMFactory, "get_chat_model", staticmethod(lambda **kwargs: model))
    return model


def _ws(tmp_path, name="ws") -> Path:
    workspace = tmp_path / name
    workspace.mkdir()
    return workspace


# ---------------------------------------------------------------------------
# 1. A well-formed response passes and is persisted
# ---------------------------------------------------------------------------
def test_well_formed_response_is_persisted(monkeypatch, tmp_path):
    blueprint = _blueprint("constrained")
    workspace = _ws(tmp_path)
    artifacts = fm.compliant_artifacts("DOMAIN", blueprint)
    _script(monkeypatch, fm.canonical_json_response(artifacts))

    result = run_stage(_model_state(blueprint, workspace), "DOMAIN")

    assert result.get("status") != "BLOCKED"
    assert result["generated_files"], "accepted artifacts were not merged into state"
    for relative_path in result["generated_files"]:
        assert (workspace / relative_path).is_file(), f"{relative_path} was not written to disk"

    entry = journal_mod.stage_entry(result["generation_journal"], "DOMAIN")
    assert entry["outcome"] == journal_mod.OUTCOME_SUCCEEDED
    assert entry["request_count"] == 1
    assert entry["corrections_used"] == 0


# ---------------------------------------------------------------------------
# 2. Guardrail: every stage constructs its own client via get_chat_model
# ---------------------------------------------------------------------------
def test_every_model_stage_calls_get_chat_model_directly(monkeypatch, tmp_path):
    """Each of the five stages must call get_chat_model *from its own module*.

    Recording only the call count would not falsify the guardrail: the seam's own
    helper calls the same function, so a stage that omitted its call would still
    produce one. This records the immediate caller's module name instead, so the
    assertion fails if construction happens anywhere but the stage module.
    """
    import inspect

    blueprint = _blueprint("minimal")
    callers: list = []

    class _Spy:
        def invoke(self, request):
            return fm.FakeResponse(content="")   # unusable on purpose

    def _spy(**kwargs):
        frame = inspect.stack()[1]
        callers.append(frame.frame.f_globals.get("__name__", "<unknown>"))
        return _Spy()

    monkeypatch.setattr(LLMFactory, "get_chat_model", staticmethod(_spy))

    expected = {
        "SCAFFOLDER": "scaffolder",
        "DOMAIN": "domain",
        "SERVICE": "service",
        "CONTROLLER": "controller",
        "TEST": "test",
    }
    for stage, module in expected.items():
        before = len(callers)
        run_stage(_model_state(blueprint, _ws(tmp_path, stage)), stage)
        new_callers = callers[before:]
        assert new_callers, f"stage {stage} never called LLMFactory.get_chat_model"
        assert any(
            caller.endswith(f"stages.model.{module}") for caller in new_callers
        ), (
            f"stage {stage} did not construct its client in its own module; "
            f"callers were {new_callers}"
        )


# ---------------------------------------------------------------------------
# 3. Declared constraints reach the request (the SC-001 signal)
# ---------------------------------------------------------------------------
def test_declared_constraints_reach_the_model_request(monkeypatch, tmp_path):
    """The payload carries what the deterministic baseline dropped.

    The baseline artifact is the independent source of truth for the contrast:
    the same blueprint's pre-migration output contained none of these rules.
    """
    blueprint = _blueprint("constrained")
    model = _script(monkeypatch, fm.canonical_json_response(
        fm.compliant_artifacts("DOMAIN", blueprint)
    ))

    run_stage(_model_state(blueprint, _ws(tmp_path)), "DOMAIN")

    assert model.calls, "no request was sent to the model"
    request = model.calls[0]

    for rule in ("@Email", "@Min", "@Max", "@Pattern", "@Size"):
        assert rule in request, f"declared constraint {rule} never reached the model"
    # Note: the constrained blueprint's entity is Member with `email`, not
    # `customerEmail` (that attribute belongs to pair-b's Invoice).
    for attribute in ("email", "displayName", "age", "membershipCode"):
        assert attribute in request, f"declared attribute {attribute} never reached the model"
    # Acceptance scenarios are carried too, not just the entity shape.
    assert "scenarioId" in request and "AC-1.1" in request

    # Contrast against the frozen baseline: pre-migration output carried none of
    # these rules, which is exactly why SC-001 is measurable.
    baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    entry = next(e for e in baseline["per_blueprint"] if e["blueprint_id"] == "constrained")
    assert entry["constraint_trace"]["format_constraints_untraced"], (
        "baseline no longer shows untraced constraints; the SC-001 contrast is invalid"
    )
    for rule in ("@Email", "@Min", "@Max", "@Pattern", "@Size"):
        assert not any(
            rule in record["content"]
            for record in (entry.get("comparison_subset_content") or {}).values()
        ), f"baseline output unexpectedly contained {rule}"


def test_paired_blueprints_produce_differing_requests(monkeypatch, tmp_path):
    """Pair-a and pair-b differ only in constraints/scenarios, so their requests must differ."""
    requests = {}
    for name in ("pair-a", "pair-b"):
        blueprint = _blueprint(name)
        model = _script(monkeypatch, fm.canonical_json_response(
            fm.compliant_artifacts("DOMAIN", blueprint)
        ))
        run_stage(_model_state(blueprint, _ws(tmp_path, name)), "DOMAIN")
        requests[name] = model.calls[0]

    assert requests["pair-a"] != requests["pair-b"], (
        "paired blueprints produced identical requests, so declared constraints and "
        "scenarios are still not reaching the model"
    )
    for rule in ("@Email", "@NotBlank", "@Positive", "@DecimalMin"):
        assert rule in requests["pair-b"]
        assert rule not in requests["pair-a"]


# ---------------------------------------------------------------------------
# 4. Unextractable responses consume an attempt and persist nothing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "response",
    [
        "",                                    # absent
        "   \n  ",                             # blank
        "```java src/main/java/x/A.java\npublic class A {}\n",   # truncated fence
        "I'm afraid I can't help with that.",  # prose only, nothing extractable
        '{"artifacts": []}',                   # malformed shape
    ],
)
def test_unextractable_responses_persist_nothing(monkeypatch, tmp_path, response):
    blueprint = _blueprint("minimal")
    workspace = _ws(tmp_path)
    _script(monkeypatch, response)

    result = run_stage(_model_state(blueprint, workspace), "DOMAIN")

    assert result["generated_files"] == {}, "an unusable response produced artifacts"
    assert list(workspace.rglob("*.java")) == [], "an unusable response wrote files to disk"
    assert result.get("status") == "BLOCKED"

    entry = journal_mod.stage_entry(result["generation_journal"], "DOMAIN")
    # Every attempt was unusable, so the budget is exhausted and the stage outcome
    # is EXHAUSTED. The per-attempt UNUSABLE_RESPONSE records are what T023
    # produces, and FR-011 requires them (and the first response) to be retained.
    assert entry["outcome"] == journal_mod.OUTCOME_EXHAUSTED
    assert entry["request_count"] >= 1, "an unusable response must consume an attempt"
    assert entry.get("initial_response") is not None, "the first unusable response was discarded"
    assert entry["correction_attempts"], "no per-attempt records were retained"
    assert all(
        attempt["outcome"] == journal_mod.OUTCOME_UNUSABLE_RESPONSE
        for attempt in entry["correction_attempts"]
    )


def test_fenced_block_with_a_path_is_extracted(monkeypatch, tmp_path):
    """The prose-wrapped transport works too, and commentary is discarded."""
    blueprint = _blueprint("minimal")
    workspace = _ws(tmp_path)
    path = "src/main/java/com/corp/notes/model/entity/Note.java"
    response = (
        "Sure! Here is the entity you asked for.\n\n"
        f"```java {path}\n"
        "package com.corp.notes.model.entity;\n\n"
        "public class Note {\n    private Long id;\n}\n"
        "```\n\n"
        "Let me know if you'd like the DTO next.\n"
    )
    _script(monkeypatch, response)

    result = run_stage(_model_state(blueprint, workspace), "DOMAIN")

    assert result.get("status") != "BLOCKED"
    written = (workspace / path).read_text(encoding="utf-8")
    assert written.startswith("package com.corp.notes.model.entity;")
    assert "Sure! Here is" not in written, "surrounding commentary leaked into the artifact"
    assert "Let me know" not in written


# ---------------------------------------------------------------------------
# 5. Out-of-scope artifact paths are rejected
# ---------------------------------------------------------------------------
def test_out_of_scope_paths_are_rejected(monkeypatch, tmp_path):
    """A stage inventing paths would break the FR-021 index contract."""
    blueprint = _blueprint("minimal")
    workspace = _ws(tmp_path)
    out_of_scope = {
        "src/main/java/com/corp/notes/controller/NoteController.java": "package x;\n",
    }
    _script(monkeypatch, fm.canonical_json_response(out_of_scope))

    result = run_stage(_model_state(blueprint, workspace), "DOMAIN")

    assert result["generated_files"] == {}, "an out-of-scope artifact was persisted"
    assert not (workspace / next(iter(out_of_scope))).exists()
    assert result.get("status") == "BLOCKED"
    assert "OUT_OF_SCOPE_ARTIFACT" in json.dumps(
        journal_mod.stage_entry(result["generation_journal"], "DOMAIN")["initial_verdict"]
    )


# ---------------------------------------------------------------------------
# Payload construction rules (T022)
# ---------------------------------------------------------------------------
def test_payload_includes_only_prior_stage_artifacts():
    """Earlier stages' artifacts are visible; unrelated ones are not."""
    blueprint = _blueprint("minimal")
    state = _model_state(blueprint, Path("/tmp/does-not-matter"))
    state["generated_files"] = {
        "pom.xml": "POM",                                                        # SCAFFOLDER
        "src/main/java/com/corp/notes/model/entity/Note.java": "ENTITY",         # DOMAIN
        "src/test/java/com/corp/notes/service/NoteServiceTest.java": "TEST",     # TEST
    }

    service_payload = build_stage_payload(state, "SERVICE")
    visible = set(service_payload["prior_artifacts"])
    assert "pom.xml" in visible, "SERVICE depends on SCAFFOLDER"
    assert "src/main/java/com/corp/notes/model/entity/Note.java" in visible, "SERVICE depends on DOMAIN"
    assert "src/test/java/com/corp/notes/service/NoteServiceTest.java" not in visible, (
        "TEST runs after SERVICE; its artifacts must not leak backwards"
    )

    scaffolder_payload = build_stage_payload(state, "SCAFFOLDER")
    assert scaffolder_payload["prior_artifacts"] == {}, "SCAFFOLDER depends on nothing"


def test_oversized_payload_blocks_without_persisting(monkeypatch, tmp_path):
    """An oversized payload blocks rather than being silently trimmed."""
    from app.orchestrator.stages import runner as runner_mod

    blueprint = _blueprint("minimal")
    workspace = _ws(tmp_path)
    _script(monkeypatch, fm.canonical_json_response(
        fm.compliant_artifacts("DOMAIN", blueprint)
    ))

    monkeypatch.setattr(runner_mod, "MAX_PAYLOAD_CHARS", 50)
    result = run_stage(_model_state(blueprint, workspace), "DOMAIN")

    assert result["generated_files"] == {}
    assert result.get("status") == "BLOCKED"
    entry = journal_mod.stage_entry(result["generation_journal"], "DOMAIN")
    assert entry["outcome"] == journal_mod.OUTCOME_UNUSABLE_RESPONSE
    assert "payload_error" in entry
    # An attempt was consumed, but no model request was issued: the session budget
    # counts model calls (SC-005), so it must not be inflated by a request that
    # never left the process.
    assert entry["attempt_consumed"] is True
    assert entry["request_count"] == 0
    assert result["generation_journal"]["total_requests"] == 0


# ---------------------------------------------------------------------------
# Artifacts, not just prompts: a payload-aware fake model
# ---------------------------------------------------------------------------
# The scripted responses above come from fixtures, so they would be emitted
# whether or not the payload carried anything. To assert that declared
# constraints reach the *generated artifacts* (T029's wording) the fake below
# derives its output from the payload it receives. If the payload stopped
# carrying a declared constraint, the emitted annotation would disappear with it
# and the assertion would fail — which is what makes it a real check.
class _ResponderModel:
    def __init__(self, responder):
        self._responder = responder
        self.calls: list = []

    def invoke(self, request):
        text = str(request)
        self.calls.append(text)
        return fm.FakeResponse(content=self._responder(text))


def _payload_from_request(request: str) -> dict:
    """Pull the JSON payload back out of a rendered request."""
    marker = "## Task payload"
    assert marker in request, "the request carries no task payload"
    body = request.split(marker, 1)[1]
    body = body.split("## Output paths you own", 1)[0]
    return json.loads(body.strip())


_JAVA_TYPES = {
    "string": "String", "long": "Long", "integer": "Integer", "int": "Integer",
    "bigdecimal": "java.math.BigDecimal", "double": "Double", "boolean": "Boolean",
    "localdatetime": "java.time.LocalDateTime", "uuid": "java.util.UUID",
}


def _payload_aware_responder(stage: str):
    """A fake 'model' that honours the payload for the given stage."""

    def respond(request: str) -> str:
        payload = _payload_from_request(request)
        package = payload["package_name"]
        path = package.replace(".", "/")
        artifacts: dict = {}

        for entity in payload["entities"]:
            name = entity["name"]

            if stage == "DOMAIN":
                fields = []
                for attribute in entity["attributes"]:
                    for rule in attribute["validationRules"]:
                        fields.append(f"    {rule}")
                    java_type = _JAVA_TYPES.get(str(attribute["type"]).lower(), "String")
                    fields.append(f"    private {java_type} {attribute['name']};")
                artifacts[f"src/main/java/{path}/model/entity/{name}.java"] = (
                    f"package {package}.model.entity;\n\n"
                    f"public class {name} {{\n" + "\n".join(fields) + "\n}\n"
                )
                params = ", ".join(
                    f"{_JAVA_TYPES.get(str(a['type']).lower(), 'String')} {a['name']}"
                    for a in entity["attributes"] if not a["isPrimaryKey"]
                )
                artifacts[f"src/main/java/{path}/model/dto/Create{name}Request.java"] = (
                    f"package {package}.model.dto;\n\npublic record Create{name}Request({params}) {{}}\n"
                )
                response_params = ", ".join(
                    f"{_JAVA_TYPES.get(str(a['type']).lower(), 'String')} {a['name']}"
                    for a in entity["attributes"]
                )
                artifacts[f"src/main/java/{path}/model/dto/{name}Response.java"] = (
                    f"package {package}.model.dto;\n\npublic record {name}Response({response_params}) {{}}\n"
                )

            elif stage == "TEST":
                methods = []
                for story in payload["user_stories"]:
                    for scenario in story["scenarios"]:
                        scenario_id = scenario["scenarioId"]
                        method = "should" + "".join(
                            part.capitalize() for part in re.split(r"[^A-Za-z0-9]+", scenario_id) if part
                        )
                        methods.append(
                            f"    @Test\n    void {method}() {{\n"
                            f"        // {scenario_id}: {scenario['then']}\n    }}\n"
                        )
                artifacts[f"src/test/java/{path}/service/{name}ServiceTest.java"] = (
                    f"package {package}.service;\n\npublic class {name}ServiceTest {{\n"
                    + "\n".join(methods) + "\n}\n"
                )

        return fm.canonical_json_response(artifacts)

    return respond


def _script_responder(monkeypatch, responder) -> _ResponderModel:
    model = _ResponderModel(responder)
    monkeypatch.setattr(LLMFactory, "get_chat_model", staticmethod(lambda **kwargs: model))
    return model


def test_declared_constraints_reach_generated_entity_artifacts(monkeypatch, tmp_path):
    """T029: constraints appear in the generated entity artifacts, not just the prompt."""
    blueprint = _blueprint("constrained")
    workspace = _ws(tmp_path)
    _script_responder(monkeypatch, _payload_aware_responder("DOMAIN"))

    result = run_stage(_model_state(blueprint, workspace), "DOMAIN")
    assert result.get("status") != "BLOCKED", result.get("error")

    entity_name = "src/main/java/com/corp/member/model/entity/Member.java"
    entity = (workspace / entity_name).read_text(encoding="utf-8")
    for rule in ("@Email", "@Min", "@Max", "@Pattern", "@Size"):
        assert rule in entity, f"declared constraint {rule} is missing from the generated entity"

    # The same blueprint through the deterministic path carries none of them —
    # the contrast SC-001 measures, taken from the frozen baseline artifact.
    baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    entry = next(e for e in baseline["per_blueprint"] if e["blueprint_id"] == "constrained")
    baseline_entity = next(
        content["content"] for path, content in entry["comparison_subset_content"].items()
        if path.endswith("Member.java")
    )
    for rule in ("@Email", "@Min", "@Max", "@Pattern", "@Size"):
        assert rule not in baseline_entity


def test_declared_scenarios_reach_generated_test_artifacts(monkeypatch, tmp_path):
    """T026/T029: one test per declared acceptance scenario, not a fixed method set."""
    blueprint = _blueprint("constrained")
    workspace = _ws(tmp_path)
    _script_responder(monkeypatch, _payload_aware_responder("TEST"))

    result = run_stage(_model_state(blueprint, workspace), "TEST")
    assert result.get("status") != "BLOCKED", result.get("error")

    declared_scenarios = sum(len(s["scenarios"]) for s in blueprint["userStories"])
    test_file = (workspace / "src/test/java/com/corp/member/service/MemberServiceTest.java").read_text(
        encoding="utf-8"
    )
    assert test_file.count("@Test") == declared_scenarios, (
        "the generated suite does not track the declared acceptance scenarios"
    )
    for scenario in (s for story in blueprint["userStories"] for s in story["scenarios"]):
        assert scenario["scenarioId"] in test_file


def test_partial_candidate_set_is_rejected(monkeypatch, tmp_path):
    """T023 'the reverse': one artifact where several entities were requested."""
    blueprint = _blueprint("multi-entity")     # declares Product and Category
    workspace = _ws(tmp_path)
    partial = {
        "src/main/java/com/corp/catalog/model/entity/Product.java": "package x;\npublic class Product {}\n",
    }
    _script(monkeypatch, fm.canonical_json_response(partial))

    result = run_stage(_model_state(blueprint, workspace), "DOMAIN")

    assert result["generated_files"] == {}, "a partial candidate set was persisted"
    assert result.get("status") == "BLOCKED"
    verdict = journal_mod.stage_entry(result["generation_journal"], "DOMAIN")["initial_verdict"]
    assert "PARTIAL_CANDIDATE_SET" in json.dumps(verdict)
