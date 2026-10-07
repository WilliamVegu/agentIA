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
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-parent</artifactId>
        <version>3.15.1</version>
      </parent>
      <dependencies>
        <dependency>
          <groupId>io.quarkus</groupId>
          <artifactId>quarkus-rest</artifactId>
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
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-parent</artifactId>
    <version>3.15.1</version>
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
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-parent</artifactId>
        <version>3.15.1</version>
      </parent>
      <dependencies>
        <dependency>
          <groupId>io.quarkus</groupId>
          <artifactId>quarkus-rest</artifactId>
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
        "package com.corp.x.controller;\n@Provider\npublic class GlobalExceptionHandler {}\n"
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
            "package com.corp.x.controller;\n@Provider\npublic class GlobalExceptionHandler {}\n"
        ),
    }
    verdict = normalize_verdict(files, stage_scope=("src/main/java/*/model/entity/*.java",))
    lombok = [v for v in verdict.violations if v.rule_id == "STACK_LOMBOK_RESTRICTION"]
    assert lombok, "the prohibited-annotation rule must fire"
    assert lombok[0].severity == "HIGH", f"expected the strictest severity, got {lombok[0].severity}"
    assert lombok[0].blocking


def test_whole_project_rule_is_accumulated_not_local():
    """FR-006: a stage must not be blamed for a rule only the project can satisfy.

    With no @Provider anywhere, family B reports the omission against
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
            "package com.corp.x.controller;\n@Provider\npublic class GlobalExceptionHandler {}\n"
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
            "package com.corp.x.controller;\n@Provider\npublic class GlobalExceptionHandler {}\n"
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


# =========================================================================
# T030-T035 — User Story 2: no non-compliant artifact is ever persisted
#
# Injection happens AT THE MODEL BOUNDARY (via the T017 fake client), never by
# observing session outcomes. That distinction is load-bearing: the platform's
# sandbox verifier can report synthetic success without executing a build, so a
# session reaching a "success" state proves nothing about compliance. Every
# adversarial assertion below therefore reads the WORKSPACE, not the status.
#
# Imports for this section are added here rather than in the header block so the
# T014/T049 and T029 sections above stay exactly as they were.
# =========================================================================
from app.models.session import SessionPhase, SessionStatus  # noqa: E402
from app.orchestrator.stages.runner import run_stages  # noqa: E402
from app.services.security_service import (  # noqa: E402
    audit_workspace,
    scan_architecture_compliance,
)

MINIMAL = "minimal"          # one entity: keeps the per-entity partial-set rule quiet


def _leaked_key_literal() -> str:
    """A credential-shaped value assembled at runtime.

    Built by concatenation so this file contains no literal that a secret scanner
    (TruffleHog / GitGuardian, named in the constitution's audit section) would
    flag, while still matching the credential pattern the rule must catch.
    """
    return "AIza" + "Sy" + "x" * 33


def _stage_state(blueprint: dict, workspace: Path, **extra) -> dict:
    state = _model_state(blueprint, workspace)
    state.update(extra)
    return state


def _no_artifact_reached_the_workspace(workspace: Path, result: dict) -> None:
    """Guardrail: assert on the FILESYSTEM, not on session status.

    A session terminal status is produced by the sandbox verifier, which can
    report synthetic success; the workspace is the only trustworthy witness of
    what was actually persisted.
    """
    files = sorted(p.relative_to(workspace).as_posix() for p in workspace.rglob("*") if p.is_file())
    assert files == [], f"artifacts from the violating response reached the workspace: {files}"
    assert result["generated_files"] == {}, "the violating response was merged into generated_files"


# ---------------------------------------------------------------------------
# T033 — adversarial fault injection, one scripted case per constitutional rule
# ---------------------------------------------------------------------------
def test_adversarial_layer_isolation_persists_nothing(monkeypatch, tmp_path):
    """Principle I: a controller reaching directly into the repository layer.

    The scripted response is a controller that imports the repository and an
    advice class (so the *whole-project* rule cannot also fire and mask the
    result). The violation is LOCAL to the CONTROLLER stage, so it must reject
    the candidate set and consume a correction attempt.
    """
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    violating = fm.violating_artifacts("LAYER_ISOLATION", blueprint)
    _script(monkeypatch, *[fm.canonical_json_response(violating)] * 3)

    result = run_stage(_stage_state(blueprint, workspace), "CONTROLLER")

    _no_artifact_reached_the_workspace(workspace, result)

    entry = journal_mod.stage_entry(result["generation_journal"], "CONTROLLER")
    assert entry["outcome"] == journal_mod.OUTCOME_EXHAUSTED
    assert entry["request_count"] == 3, "one initial request plus two corrections"
    rule_ids = {
        v["rule_id"]
        for v in (entry["initial_verdict"] or {}).get("violations", [])
    }
    assert "PRINCIPLE_I_LAYER_ISOLATION" in rule_ids, (
        f"the layer-isolation rule did not fire; verdict carried {sorted(rule_ids)}"
    )


def test_adversarial_contract_immutability_persists_nothing(monkeypatch, tmp_path):
    """Principle II: a request contract declared as a class instead of a record."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    violating = fm.violating_artifacts("CONTRACT_IMMUTABILITY", blueprint)
    _script(monkeypatch, *[fm.canonical_json_response(violating)] * 3)

    result = run_stage(_stage_state(blueprint, workspace), "DOMAIN")

    _no_artifact_reached_the_workspace(workspace, result)
    rule_ids = {
        v["rule_id"]
        for v in (journal_mod.stage_entry(result["generation_journal"], "DOMAIN")["initial_verdict"] or {}).get("violations", [])
    }
    assert "PRINCIPLE_II_IMMUTABLE_DTOS" in rule_ids, f"expected the DTO rule; got {sorted(rule_ids)}"


def test_adversarial_prohibited_annotation_persists_nothing(monkeypatch, tmp_path):
    """Stack rule: a prohibited Lombok annotation on a JPA entity.

    Family A rates this MEDIUM and family B rates it HIGH; the adapter keeps the
    strictest, which is what makes it blocking.
    """
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    violating = fm.violating_artifacts("PROHIBITED_ANNOTATION", blueprint)
    _script(monkeypatch, *[fm.canonical_json_response(violating)] * 3)

    result = run_stage(_stage_state(blueprint, workspace), "DOMAIN")

    _no_artifact_reached_the_workspace(workspace, result)
    entry = journal_mod.stage_entry(result["generation_journal"], "DOMAIN")
    lombok = [
        v for v in (entry["initial_verdict"] or {}).get("violations", [])
        if v["rule_id"] == "STACK_LOMBOK_RESTRICTION"
    ]
    assert lombok, "the prohibited-annotation rule did not fire"
    assert lombok[0]["severity"] == "HIGH", "the strictest severity was not kept"
    assert lombok[0]["blocking"] is True


def test_adversarial_embedded_credential_persists_nothing(monkeypatch, tmp_path):
    """FR-018: a leaked API key inside generated source.

    The secret is placed *inside the stage's artifact scope* so the credential
    rule is what fires, rather than the out-of-scope rule masking it.
    """
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    leaked = {
        "src/main/java/com/corp/notes/controller/NoteController.java": (
            "package com.corp.notes.controller;\n\n"
            "public class NoteController {\n"
            f'    private static final String API_KEY = "{_leaked_key_literal()}";\n'
            "}\n"
        ),
        "src/main/java/com/corp/notes/controller/GlobalExceptionHandler.java": (
            "package com.corp.notes.controller;\n\n"
            "@Provider\npublic class GlobalExceptionHandler {}\n"
        ),
    }
    _script(monkeypatch, *[fm.canonical_json_response(leaked)] * 3)

    result = run_stage(_stage_state(blueprint, workspace), "CONTROLLER")

    _no_artifact_reached_the_workspace(workspace, result)
    entry = journal_mod.stage_entry(result["generation_journal"], "CONTROLLER")
    credentials = [
        v for v in (entry["initial_verdict"] or {}).get("violations", [])
        if v["rule_id"] == "CREDENTIAL_IN_ARTIFACT"
    ]
    assert credentials, "the credential rule did not fire"
    assert credentials[0]["severity"] == "CRITICAL"
    assert credentials[0]["blocking"] is True


def test_adversarial_unlisted_dependency_persists_nothing(monkeypatch, tmp_path):
    """FR-017: build configuration declaring a dependency outside the allowlist.

    The scaffolder is the only stage that emits build configuration, and its
    failure mode is a hermetic-build violation rather than a code-quality one.
    """
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    violating = fm.violating_artifacts("DEPENDENCY_ALLOWLIST", blueprint)
    _script(monkeypatch, *[fm.canonical_json_response(violating)] * 3)

    result = run_stage(_stage_state(blueprint, workspace), "SCAFFOLDER")

    _no_artifact_reached_the_workspace(workspace, result)
    assert not (workspace / "pom.xml").exists(), "an unlisted pom.xml reached the workspace"
    rule_ids = {
        v["rule_id"]
        for v in (journal_mod.stage_entry(result["generation_journal"], "SCAFFOLDER")["initial_verdict"] or {}).get("violations", [])
    }
    assert "DEPENDENCY_NOT_ALLOWED" in rule_ids, f"expected the allowlist rule; got {sorted(rule_ids)}"


def test_adversarial_missing_error_handler_is_accumulated_not_charged(monkeypatch, tmp_path):
    """Principle III whole-project rule — the deliberate exception to T033's set.

    T033 lists "missing centralized error handler" among the adversarial cases,
    and T030 (with guardrail 4) makes it the canonical ACCUMULATED case: a stage
    running before the controller stage cannot satisfy the rule, so it is NOT
    rejected and its artifacts DO persist. The two instructions are
    irreconcilable for this one rule; T030/FR-006 is the more specific rule and
    is followed here.

    What is asserted instead is that the omission is not lost: it is recorded as
    ACCUMULATED and is still surfaced by the project-level audit.
    """
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    in_scope_no_advice = fm.compliant_artifacts("DOMAIN", blueprint)   # entity + DTO, no advice
    _script(monkeypatch, fm.canonical_json_response(in_scope_no_advice))

    result = run_stage(_stage_state(blueprint, workspace), "DOMAIN")

    entry = journal_mod.stage_entry(result["generation_journal"], "DOMAIN")
    assert entry["outcome"] == journal_mod.OUTCOME_SUCCEEDED, "an accumulated rule rejected the stage"
    assert entry["request_count"] == 1, "an accumulated rule consumed a correction attempt"

    violations = (entry["final_verdict"] or {}).get("violations", [])
    recorded = [v for v in violations if v["rule_id"] == "PRINCIPLE_III_CENTRALIZED_ERRORS"]
    assert recorded, "the whole-project omission was not recorded at all"
    assert all(v["attribution"] == "ACCUMULATED" for v in recorded)
    assert (entry["final_verdict"] or {}).get("accumulated_count") == len(recorded)

    # Not lost: the existing project-level audit still surfaces the omission.
    persisted = {
        path: (workspace / path).read_text(encoding="utf-8")
        for path in result["generated_files"]
    }
    audited = scan_architecture_compliance(persisted)
    assert any(
        v.principle.value == "PRINCIPLE_III_CENTRALIZED_ERRORS" for v in audited
    ), "the omission was silently dropped: the project-level audit did not find it"

    # And it must reach the SESSION-level quality gate that the pipeline actually
    # consults, which is the surface an operator sees.
    report = audit_workspace(str(workspace), "accumulated-case", blueprint["serviceName"])
    assert report.qualityGate.status == "BLOCKED", (
        "the session quality gate did not block despite the missing error handler"
    )


# ---------------------------------------------------------------------------
# T034 — the whole-project rule specifically
# ---------------------------------------------------------------------------
def test_stage_that_cannot_satisfy_the_whole_project_rule_is_not_rejected(monkeypatch, tmp_path):
    """A DOMAIN stage runs before CONTROLLER, so it cannot emit the advice class."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    _script(monkeypatch, fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", blueprint)))

    result = run_stage(_stage_state(blueprint, workspace), "DOMAIN")

    assert result.get("status") != SessionStatus.BLOCKED.value, (
        "the stage was rejected for a rule only the accumulated set can satisfy"
    )
    assert result["generated_files"], "the stage's own artifacts should have persisted"


def test_whole_project_rule_does_not_fire_without_java_files(monkeypatch, tmp_path):
    """The rule is about Java sources; a stage emitting none cannot breach it."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    yaml_only = {"src/main/resources/application.yml": "spring:\n  application:\n    name: x\n"}
    _script(monkeypatch, fm.canonical_json_response(yaml_only))

    result = run_stage(_stage_state(blueprint, workspace), "SCAFFOLDER")

    entry = journal_mod.stage_entry(result["generation_journal"], "SCAFFOLDER")
    violations = (entry["final_verdict"] or {}).get("violations", [])
    assert not [v for v in violations if v["rule_id"] == "PRINCIPLE_III_CENTRALIZED_ERRORS"], (
        "the whole-project rule fired with no Java sources in the set"
    )


def test_absent_project_wide_artifact_is_surfaced_at_session_level(monkeypatch, tmp_path):
    """ACCUMULATED violations are recorded, not discarded (FR-006 both directions)."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    _script(monkeypatch, fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", blueprint)))

    result = run_stage(_stage_state(blueprint, workspace), "DOMAIN")

    journal = result["generation_journal"]
    entry = journal_mod.stage_entry(journal, "DOMAIN")
    assert (entry["final_verdict"] or {}).get("accumulated_count", 0) >= 1, (
        "an accumulated violation must remain visible at session level"
    )
    # And the journal as a whole still carries it, so an operator can see why the
    # project as a whole is not compliant.
    assert "PRINCIPLE_III_CENTRALIZED_ERRORS" in json.dumps(journal)


# ---------------------------------------------------------------------------
# T035 — budget exhaustion, terminal-state parity, counter independence
# ---------------------------------------------------------------------------
def test_exhaustion_uses_exactly_two_correction_attempts(monkeypatch, tmp_path):
    """T031: one initial request plus at most two corrections, then stop."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    model = _script(
        monkeypatch,
        *[fm.canonical_json_response(fm.violating_artifacts("PROHIBITED_ANNOTATION", blueprint))] * 5,
    )

    result = run_stage(_stage_state(blueprint, workspace), "DOMAIN")

    entry = journal_mod.stage_entry(result["generation_journal"], "DOMAIN")
    assert entry["request_count"] == 1 + journal_mod.MAX_CORRECTION_ATTEMPTS == 3
    assert entry["corrections_used"] == journal_mod.MAX_CORRECTION_ATTEMPTS
    assert len(entry["correction_attempts"]) == journal_mod.MAX_CORRECTION_ATTEMPTS
    assert model.call_count == 3, "the stage made more model calls than its budget allows"
    _no_artifact_reached_the_workspace(workspace, result)


def test_exhaustion_reaches_the_same_terminal_state_as_the_repair_loop(monkeypatch, tmp_path):
    """FR-010: no new state name — the repair loop's own terminal state is reused."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    _script(
        monkeypatch,
        *[fm.canonical_json_response(fm.violating_artifacts("PROHIBITED_ANNOTATION", blueprint))] * 3,
    )

    result = run_stage(_stage_state(blueprint, workspace), "DOMAIN")

    # Drive the sandbox repair loop to ITS exhaustion and read the terminal state
    # it actually writes, rather than restating the expected values. Comparing
    # against a constant would pass even if repair_node changed; this fails.
    from app.orchestrator.nodes.repair_node import repair_node

    repair_terminal = repair_node({
        "session_id": "fr010-parity",
        "workspace_path": str(tmp_path),
        "generated_files": {},
        "logs": [],
        "repair_attempts": 3,          # increments to 4, past the cap of 3
        "max_repair_attempts": 3,
        "last_diagnostic": {"failed_file": "X.java", "summary": "boom", "line_number": 1},
    })
    assert repair_terminal["status"] == SessionStatus.BLOCKED.value, (
        "the repair loop did not reach its own exhaustion, so parity was not tested"
    )

    # FR-010: the generation loop reuses that exact terminal state. No new name.
    assert result["status"] == repair_terminal["status"]
    assert result["current_phase"] == repair_terminal["current_phase"]


def test_generation_exhaustion_does_not_touch_the_sandbox_repair_budget(monkeypatch, tmp_path):
    """FR-009 / SC-009: the two budgets are independent."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    _script(
        monkeypatch,
        *[fm.canonical_json_response(fm.violating_artifacts("PROHIBITED_ANNOTATION", blueprint))] * 3,
    )

    result = run_stage(
        _stage_state(blueprint, workspace, repair_attempts=0, max_repair_attempts=3),
        "DOMAIN",
    )

    assert result["generation_journal"]["total_requests"] == 3, (
        "the generation budget should have been spent independently of the repair budget"
    )

    # Drive the sandbox repair loop on the state the generation loop left behind.
    # This is what makes the independence check falsifiable: asserting only that
    # the injected counter is unchanged would pass even if the runner never read
    # it. If generation exhaustion had consumed repair budget, the repair loop
    # would block immediately instead of proceeding to its first attempt.
    from app.orchestrator.nodes.repair_node import repair_node

    repair_after = repair_node({
        "session_id": "fr009-independence",
        "workspace_path": str(workspace),
        "generated_files": dict(result.get("generated_files") or {}),
        "logs": [],
        "repair_attempts": result.get("repair_attempts", 0),
        "max_repair_attempts": result.get("max_repair_attempts", 3),
        "last_diagnostic": {"failed_file": "X.java", "summary": "boom", "line_number": 1},
    })
    assert repair_after.get("status") != SessionStatus.BLOCKED.value, (
        "the generation loop consumed the sandbox repair budget: the repair loop "
        "blocked on its first attempt"
    )
    assert result.get("repair_attempts") == 0, "the generation loop wrote the repair counter"
    assert repair_after["repair_attempts"] == 1, (
        "the repair loop should have taken its first of three attempts on a full budget"
    )


def test_session_never_exceeds_the_request_budget(monkeypatch, tmp_path):
    """SC-005/SC-007: five stages, each forced through one correction, stay in budget."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    attempts: dict = {}

    def responder(request: str) -> str:
        payload = _payload_from_request(request)
        stage = payload["stage"]
        attempts[stage] = attempts.get(stage, 0) + 1
        if attempts[stage] == 1:
            # First attempt is rejected (the entity path is out of scope for four
            # of the five stages and forbidden within DOMAIN) so a correction is
            # issued; the second attempt is compliant.
            return fm.canonical_json_response(
                fm.violating_artifacts("PROHIBITED_ANNOTATION", blueprint)
            )
        return fm.canonical_json_response(fm.compliant_artifacts(stage, blueprint))

    _script_responder(monkeypatch, responder)
    result = run_stages(_stage_state(blueprint, workspace))

    total = result["generation_journal"]["total_requests"]
    assert total <= journal_mod.MAX_REQUESTS_PER_SESSION == 15, f"budget exceeded: {total}"
    assert len(result["generation_journal"]["entries"]) == len(STAGE_ORDER), (
        "not every stage ran, so the budget bound was not exercised"
    )
    assert total == 2 * len(STAGE_ORDER), f"expected one correction per stage, got {total} requests"
    journal_mod.assert_within_budget(result["generation_journal"])


def test_budget_guard_refuses_a_request_beyond_the_documented_maximum():
    """The cap is enforced, not merely documented."""
    journal = journal_mod.new_journal("budget", journal_mod.GENERATION_MODE_MODEL, provider="p", model="m")
    for index in range(len(STAGE_ORDER)):
        journal_mod.record_stage_entry(
            journal,
            stage=STAGE_ORDER[index],
            outcome=journal_mod.OUTCOME_CORRECTED,
            request_count=3,     # 1 initial + 2 corrections: the worst case per stage
            corrections_used=journal_mod.MAX_CORRECTION_ATTEMPTS,
        )
    assert journal["total_requests"] == journal_mod.MAX_REQUESTS_PER_SESSION == 15

    with pytest.raises(journal_mod.JournalBudgetError):
        journal_mod.record_stage_entry(
            journal, stage="DOMAIN", outcome=journal_mod.OUTCOME_SUCCEEDED, request_count=1
        )


def test_no_unbounded_retries_on_a_permanently_non_compliant_response(monkeypatch, tmp_path):
    """SC-007: the loop terminates; it does not retry indefinitely."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    model = _script_responder(
        monkeypatch,
        lambda request: fm.canonical_json_response(
            fm.violating_artifacts("PROHIBITED_ANNOTATION", blueprint)
        ),
    )

    result = run_stages(_stage_state(blueprint, workspace))

    assert result["status"] == SessionStatus.BLOCKED.value
    assert result["generation_journal"]["total_requests"] <= journal_mod.MAX_REQUESTS_PER_SESSION
    assert model.calls, "no request was issued at all"
    _no_artifact_reached_the_workspace(workspace, result)


def test_five_exhausting_stages_reach_exactly_the_session_ceiling(monkeypatch, tmp_path):
    """SC-005/SC-007 at session level: the 15-request ceiling is actually reached.

    A single always-non-compliant session blocks after its first stage (3
    requests), so it never approaches the ceiling - asserting "3 <= 15" witnesses
    nothing. Here the same journal is threaded through all five stages, each
    exhausting its own budget, which lands on exactly 15 and proves the cap is
    the binding constraint rather than an incidental headroom.
    """
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    _script_responder(
        monkeypatch,
        lambda request: fm.canonical_json_response(
            fm.violating_artifacts("PROHIBITED_ANNOTATION", blueprint)
        ),
    )

    state = _stage_state(blueprint, workspace)
    for stage in STAGE_ORDER:                 # one session, five stages
        state = run_stage(state, stage)

    journal = state["generation_journal"]
    assert len(journal["entries"]) == len(STAGE_ORDER), "not every stage ran"
    assert all(e["request_count"] == 3 for e in journal["entries"])
    assert journal["total_requests"] == journal_mod.MAX_REQUESTS_PER_SESSION == 15
    journal_mod.assert_within_budget(journal)

    # The very next request is refused: 15 is the cap, not a coincidence.
    with pytest.raises(journal_mod.JournalBudgetError):
        journal_mod.record_stage_entry(
            journal, stage="DOMAIN", outcome=journal_mod.OUTCOME_SUCCEEDED, request_count=1
        )


# =========================================================================
# T036-T040 — User Story 3: attribution, boundedness, durable history
#
# Imports for this section are added here rather than in the header block so the
# T014/T049, T029 and T030-T035 sections above stay exactly as they were.
# =========================================================================
import uuid  # noqa: E402
from dataclasses import replace as _dc_replace  # noqa: E402

from app.models.session import GenerationSessionDB, SessionLocal  # noqa: E402

PROVENANCE_FIELDS = {
    "artifact_path",
    "stage",
    "generation_mode",
    "provider",
    "model",
    "instruction_set_revision",
    "attempt_ordinal",
    "created_at",
}


@pytest.fixture
def persisted_session():
    """A real session row, so journal persistence has something to write to.

    Removed afterwards so the suite leaves no rows behind.
    """
    session_id = f"t036-{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    try:
        db.add(
            GenerationSessionDB(
                id=session_id,
                spec_id="spec-t036",
                spec_name="t036",
                status=SessionStatus.RUNNING,
                phase=SessionPhase.INITIALIZATION,
            )
        )
        db.commit()
    finally:
        db.close()

    yield session_id

    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# T039 — provenance completeness, mode stickiness, budget, credentials
# ---------------------------------------------------------------------------
def test_provenance_is_complete_for_every_generated_artifact(monkeypatch, tmp_path):
    """SC-006: at least 99% of generated artifacts carry a complete record."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    _script(monkeypatch, fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", blueprint)))

    result = run_stage(
        _stage_state(blueprint, workspace, instruction_set_revision="test-rev-0001"), "DOMAIN"
    )

    generated = set(result["generated_files"])
    records = result["artifact_provenance"]
    assert generated, "nothing was generated, so coverage is meaningless"

    covered = {r["artifact_path"] for r in records} & generated
    assert len(covered) / len(generated) >= 0.99, (
        f"provenance coverage {len(covered)}/{len(generated)} is below the 99% floor"
    )

    for record in records:
        assert PROVENANCE_FIELDS <= set(record), (
            f"provenance record is missing {sorted(PROVENANCE_FIELDS - set(record))}"
        )
        assert record["created_at"], "created_at was not stamped"
        assert record["stage"] == "DOMAIN"
        if record["generation_mode"] == journal_mod.GENERATION_MODE_MODEL:
            # In MODEL mode all three identity fields must be present (SC-006).
            assert record["provider"], "MODEL provenance is missing the provider"
            assert record["model"], "MODEL provenance is missing the model"
            assert record["instruction_set_revision"], "MODEL provenance is missing the revision"


def test_deterministic_provenance_records_no_model_identity(monkeypatch, tmp_path):
    """T036: offline artifacts are never miscounted as model-generated.

    The keys are present but None rather than omitted, because the pre-existing
    offline-parity test asserts ``record["provider"] is None``; the requirement is
    that no *value* — and in particular no placeholder string such as
    "deterministic" or "N/A" — is recorded.
    """
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    state = _stage_state(blueprint, workspace)
    state["generation_mode"] = journal_mod.GENERATION_MODE_DETERMINISTIC
    state["llm_provider"] = None
    state["llm_model"] = None

    result = run_stages(state)

    records = result["artifact_provenance"]
    assert records, "the offline path recorded no provenance at all"
    for record in records:
        assert record["provider"] is None, f"offline provenance carried {record['provider']!r}"
        assert record["model"] is None, f"offline provenance carried {record['model']!r}"
        assert record["generation_mode"] == journal_mod.GENERATION_MODE_DETERMINISTIC

    stored = json.dumps(records)
    for placeholder in ("deterministic", "N/A", "n/a", "none"):
        assert f'"{placeholder}"' not in stored, f"a placeholder {placeholder!r} was recorded"


def test_model_session_never_transitions_to_deterministic(monkeypatch, tmp_path):
    """T039: the mode is decided once and never downgraded, even on exhaustion."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)

    # A successful MODEL run.
    _script(monkeypatch, fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", blueprint)))
    ok = run_stage(_stage_state(blueprint, workspace), "DOMAIN")
    assert ok["generation_mode"] == journal_mod.GENERATION_MODE_MODEL
    assert ok["generation_journal"]["generation_mode"] == journal_mod.GENERATION_MODE_MODEL

    # An exhausting MODEL run: it blocks, it does not quietly become offline.
    _script(
        monkeypatch,
        *[fm.canonical_json_response(fm.violating_artifacts("PROHIBITED_ANNOTATION", blueprint))] * 3,
    )
    blocked = run_stage(_stage_state(blueprint, _ws(tmp_path, "blocked")), "DOMAIN")
    assert blocked["status"] == SessionStatus.BLOCKED.value
    assert blocked["generation_mode"] == journal_mod.GENERATION_MODE_MODEL, (
        "a MODEL session fell back to DETERMINISTIC instead of blocking"
    )


def test_credentials_never_reach_the_journal_provenance_or_artifacts(monkeypatch, tmp_path):
    """FR-018 / Principle VI: the session key must not leak into any record."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    secret = "sk-t039-must-not-leak-000000000000"
    _script(monkeypatch, fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", blueprint)))

    result = run_stage(_stage_state(blueprint, workspace, llm_api_key=secret), "DOMAIN")

    assert secret not in json.dumps(result["generation_journal"]), "the key reached the journal"
    assert secret not in json.dumps(result["artifact_provenance"]), "the key reached provenance"
    for path, content in result["generated_files"].items():
        assert secret not in content, f"the key reached the generated artifact {path}"

    # In state, the key is confined to the one field that carries it to the client.
    for key, value in result.items():
        if key == "llm_api_key":
            continue
        assert secret not in json.dumps(value, default=str), f"the key leaked into state[{key!r}]"


# ---------------------------------------------------------------------------
# T040 — correction-history retention
# ---------------------------------------------------------------------------
def test_exhausted_session_retains_the_full_correction_history(monkeypatch, tmp_path, persisted_session):
    """SC-008 / T038: history is retained in full AND survives the process."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    responses = [
        fm.canonical_json_response(fm.violating_artifacts("PROHIBITED_ANNOTATION", blueprint))
    ] * 3
    _script(monkeypatch, *responses)

    result = run_stage(
        _stage_state(blueprint, workspace, session_id=persisted_session), "DOMAIN"
    )
    assert result["status"] == SessionStatus.BLOCKED.value

    entry = journal_mod.stage_entry(result["generation_journal"], "DOMAIN")
    assert entry["outcome"] == journal_mod.OUTCOME_EXHAUSTED
    assert entry["initial_response"] == responses[0], "the first response was discarded on exhaustion"
    assert entry["initial_verdict"] is not None, "the first violation set was discarded"
    assert len(entry["correction_attempts"]) == journal_mod.MAX_CORRECTION_ATTEMPTS
    for attempt in entry["correction_attempts"]:
        assert attempt["response"], "a rejected response was discarded"
        assert attempt["verdict"] is not None, "a rejection verdict was discarded"

    # Durability: read back through a FRESH database session, not the in-memory
    # object that was just written.
    stored = journal_mod.load_generation_journal(persisted_session)
    assert stored is not None, "the journal did not survive beyond process life"
    assert stored["total_requests"] == entry["request_count"]
    stored_entry = journal_mod.stage_entry(stored, "DOMAIN")
    assert stored_entry["initial_response"] == responses[0]
    assert len(stored_entry["correction_attempts"]) == journal_mod.MAX_CORRECTION_ATTEMPTS


def test_oscillating_violations_are_both_retained(monkeypatch, tmp_path):
    """T040: a later attempt introducing a different violation stays visible."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    first = fm.violating_artifacts("PROHIBITED_ANNOTATION", blueprint)      # STACK_LOMBOK_RESTRICTION
    second = fm.violating_artifacts("CONTRACT_IMMUTABILITY", blueprint)     # PRINCIPLE_II_IMMUTABLE_DTOS
    _script(
        monkeypatch,
        fm.canonical_json_response(first),
        fm.canonical_json_response(second),
        fm.canonical_json_response(first),
    )

    result = run_stage(_stage_state(blueprint, workspace), "DOMAIN")
    assert result["status"] == SessionStatus.BLOCKED.value

    entry = journal_mod.stage_entry(result["generation_journal"], "DOMAIN")
    initial_rules = {
        v["rule_id"] for v in (entry["initial_verdict"] or {}).get("violations", [])
    }
    attempt_rules = [
        {v["rule_id"] for v in (a["verdict"] or {}).get("violations", [])}
        for a in entry["correction_attempts"]
    ]
    assert "STACK_LOMBOK_RESTRICTION" in initial_rules
    assert "PRINCIPLE_II_IMMUTABLE_DTOS" in attempt_rules[0], (
        "the second attempt's different violation was not recorded"
    )
    assert attempt_rules[0] != initial_rules, "the oscillation was flattened"
    assert len(entry["correction_attempts"]) == journal_mod.MAX_CORRECTION_ATTEMPTS


def test_journal_is_persisted_on_the_success_path(monkeypatch, tmp_path, persisted_session):
    """T038: every exit path, not only exhaustion."""
    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    _script(monkeypatch, fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", blueprint)))

    result = run_stage(
        _stage_state(blueprint, workspace, session_id=persisted_session), "DOMAIN"
    )
    assert result.get("status") != SessionStatus.BLOCKED.value

    stored = journal_mod.load_generation_journal(persisted_session)
    assert stored is not None, "a successful run did not persist its journal"
    assert journal_mod.stage_entry(stored, "DOMAIN")["outcome"] in (
        journal_mod.OUTCOME_SUCCEEDED,
        journal_mod.OUTCOME_CORRECTED,
    )
    provenance = journal_mod.load_artifact_provenance(persisted_session)
    assert provenance, "provenance was not persisted alongside the journal"
    assert all(PROVENANCE_FIELDS <= set(r) for r in provenance)


def test_journal_is_persisted_when_a_stage_raises(monkeypatch, tmp_path, persisted_session):
    """T038: the exception path, where a naive implementation would lose everything."""
    from app.orchestrator.stages import runner as runner_mod

    blueprint = _blueprint(MINIMAL)
    workspace = _ws(tmp_path)
    _script(monkeypatch, fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", blueprint)))

    def _boom(state, instruction):
        raise RuntimeError("model transport exploded")

    monkeypatch.setitem(
        runner_mod.MODEL_STAGE_IMPLEMENTATIONS,
        "DOMAIN",
        _dc_replace(runner_mod.MODEL_STAGE_IMPLEMENTATIONS["DOMAIN"], build_request=_boom),
    )

    with pytest.raises(RuntimeError):
        run_stage(_stage_state(blueprint, workspace, session_id=persisted_session), "DOMAIN")

    stored = journal_mod.load_generation_journal(persisted_session)
    assert stored is not None, "the journal was lost when a stage raised"
    assert stored["session_id"] == persisted_session
