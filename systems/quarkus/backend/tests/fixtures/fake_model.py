"""Scripted fake model client for the model path (task T017).

WHY THIS IS NOT THE EXISTING MOCK PROVIDER
------------------------------------------
``LLMFactory`` already has a ``MOCK`` provider, but it returns **no client** —
that is precisely the trigger for the deterministic fallback. Reusing it to test
the model path would exercise the fallback instead of the model path, silently.

This fake returns well-formed, scriptable responses, which MOCK categorically
cannot. It makes **no network call** (Constitution Principle VI), so the model
path is exercisable in CI without credentials.

It is a test fixture. It is deliberately not registered anywhere in the
application.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.orchestrator.stages.runner import ModelStageImplementation


# ---------------------------------------------------------------------------
# The client
# ---------------------------------------------------------------------------
@dataclass
class FakeResponse:
    content: str
    # --- Feature 013 (T001): ADDITIVE usage metadata, defaulted to None so every
    # --- pre-existing construction and assertion in this file and across the
    # --- suite is unchanged. When None, the response reports no usage at all,
    # --- which is the unknown-usage path the cost recorder must handle by
    # --- recording an explicit marker rather than a zero.
    usage_metadata: Optional[Dict[str, Any]] = None
    response_metadata: Optional[Dict[str, Any]] = None


@dataclass
class ScriptedChatModel:
    """Minimal stand-in for a LangChain chat model.

    Implements just the surface the stage execution boundary uses: ``invoke``
    returning an object with a ``.content`` attribute. Every request is recorded
    so tests can assert what the boundary actually sent.

    Deliberately implements **only** the synchronous entry point and no
    ``ainvoke`` — the recording wrapper (feature 013) must cope with a client
    that implements one invocation form, not both.
    """

    responses: List[str] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)
    default_response: str = ""
    raise_on_invoke: Optional[Exception] = None
    # --- Feature 013 (T001): ADDITIVE. When set, every response carries this
    # --- usage metadata, so the cost recorder has real token counts to price.
    # --- Defaulted to None, which leaves existing behaviour byte-identical.
    usage_metadata: Optional[Dict[str, Any]] = None
    response_metadata: Optional[Dict[str, Any]] = None

    def invoke(self, request: Any) -> FakeResponse:
        if self.raise_on_invoke is not None:
            raise self.raise_on_invoke
        text = str(request)
        self.calls.append(text)
        content = self.responses.pop(0) if self.responses else self.default_response
        return FakeResponse(
            content=content,
            usage_metadata=self.usage_metadata,
            response_metadata=self.response_metadata,
        )

    # Convenience for assertions
    @property
    def call_count(self) -> int:
        return len(self.calls)


def make_scripted_model(*responses: str, default_response: str = "") -> ScriptedChatModel:
    return ScriptedChatModel(responses=list(responses), default_response=default_response)


# ---------------------------------------------------------------------------
# Feature 013 (T001): usage-reporting fake
# ---------------------------------------------------------------------------
def build_usage_metadata(
    input_tokens: int,
    output_tokens: int,
    cache_hit_input_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Build the usage metadata a real provider response carries.

    ``input_tokens`` is the **total** prompt token count, matching what providers
    report. DeepSeek additionally reports how many of those were served from
    cache; the cost recorder reads that to price the call, and defaults the whole
    prompt to cache-miss when it is absent.
    """
    metadata: Dict[str, Any] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
    if cache_hit_input_tokens is not None:
        # Mirrors the provider's ``response_metadata.token_usage`` shape, which is
        # where the prompt-cache-hit count lives.
        metadata["input_token_details"] = {"cache_read": cache_hit_input_tokens}
    return metadata


def make_usage_reporting_model(
    *responses: str,
    input_tokens: int = 1000,
    output_tokens: int = 250,
    cache_hit_input_tokens: Optional[int] = None,
    default_response: str = "",
) -> ScriptedChatModel:
    """A scripted model whose responses report real token usage.

    Additive: ``make_scripted_model`` is unchanged and still reports **no** usage,
    which is the unknown-usage path. Use this one when a test needs a priced call.
    """
    return ScriptedChatModel(
        responses=list(responses),
        default_response=default_response,
        usage_metadata=build_usage_metadata(input_tokens, output_tokens, cache_hit_input_tokens),
        response_metadata={"token_usage": {"prompt_cache_hit_tokens": cache_hit_input_tokens or 0}},
    )


# ---------------------------------------------------------------------------
# Request/response transport used by the fixture stages
# ---------------------------------------------------------------------------
def canonical_json_response(artifacts: Mapping[str, str]) -> str:
    """Serialize a candidate artifact set the way the fake stage expects it."""
    return json.dumps({"artifacts": dict(artifacts)}, indent=2, sort_keys=True)


def json_build_request(state: Mapping[str, Any], instruction: str) -> str:
    """A trivially-simple request builder.

    Phase 3 replaces this with the real payload builder (T022) and the authored
    instructions. Here it only needs to be non-empty and to include the
    instruction so tests can assert the instruction reached the model.
    """
    blueprint = state.get("blueprint", {}) or {}
    return (
        f"{instruction}\n\n"
        f"SERVICE: {blueprint.get('serviceName')}\n"
        f"PACKAGE: {blueprint.get('packageName')}\n"
        f"ENTITIES: {[e.get('name') for e in blueprint.get('entities', [])]}"
    )


def json_extract(
    response_text: str, state: Mapping[str, Any], instruction: str
) -> Tuple[Dict[str, str], bool]:
    """Parse a candidate artifact set out of a response.

    Returns ``({}, False)`` for anything that is not a JSON object with an
    ``artifacts`` map — the unusable-response path (FR-014).
    """
    try:
        payload = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        return {}, False
    if not isinstance(payload, dict):
        return {}, False
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        return {}, False
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in artifacts.items()):
        return {}, False
    return dict(artifacts), True


def make_stage_implementation(stage: str) -> ModelStageImplementation:
    """A fixture stage implementation wired to the JSON transport above."""
    return ModelStageImplementation(
        stage=stage,
        build_request=json_build_request,
        extract=json_extract,
    )


# ---------------------------------------------------------------------------
# Deterministic sample artifacts
# ---------------------------------------------------------------------------
def _pkg_path(blueprint: Mapping[str, Any]) -> str:
    return str(blueprint.get("packageName") or "com.corp.sample").replace(".", "/")


def _first_entity(blueprint: Mapping[str, Any]) -> str:
    entities = blueprint.get("entities") or [{"name": "Sample"}]
    return str(entities[0].get("name") or "Sample")


def _pkg(blueprint: Mapping[str, Any]) -> str:
    return str(blueprint.get("packageName") or "com.corp.sample")


def compliant_artifacts(stage: str, blueprint: Mapping[str, Any]) -> Dict[str, str]:
    """Artifacts that satisfy every rule the gate checks for that stage.

    The set includes ``@Provider`` in the controller stage so the
    whole-project error-handler rule is satisfied by accumulation, which is the
    behaviour FR-006 exists to protect.
    """
    pkg = _pkg(blueprint)
    path = _pkg_path(blueprint)
    entity = _first_entity(blueprint)

    if stage == "SCAFFOLDER":
        return {
            "pom.xml": (
                "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                "<project xmlns=\"http://maven.apache.org/POM/4.0.0\">\n"
                "  <modelVersion>4.0.0</modelVersion>\n"
                "  <parent>\n"
                "    <groupId>io.quarkus</groupId>\n"
                "    <artifactId>quarkus-parent</artifactId>\n"
                "    <version>3.15.1</version>\n"
                "  </parent>\n"
                "  <dependencies>\n"
                "    <dependency>\n"
                "      <groupId>io.quarkus</groupId>\n"
                "      <artifactId>quarkus-rest</artifactId>\n"
                "    </dependency>\n"
                "  </dependencies>\n"
                "  <build>\n"
                "    <plugins>\n"
                "      <plugin>\n"
                "        <groupId>org.apache.maven.plugins</groupId>\n"
                "        <artifactId>maven-compiler-plugin</artifactId>\n"
                "      </plugin>\n"
                "    </plugins>\n"
                "  </build>\n"
                "</project>\n"
            ),
            "src/main/resources/application.properties": f"quarkus.application.name={blueprint.get('serviceName')}\n",
        }

    if stage == "DOMAIN":
        return {
            f"src/main/java/{path}/model/entity/{entity}.java": (
                f"package {pkg}.model.entity;\n\n"
                f"public class {entity} {{\n    private Long id;\n}}\n"
            ),
            f"src/main/java/{path}/model/dto/{entity}Response.java": (
                f"package {pkg}.model.dto;\n\n"
                f"public record {entity}Response(Long id) {{}}\n"
            ),
        }

    if stage == "SERVICE":
        return {
            f"src/main/java/{path}/service/{entity}Service.java": (
                f"package {pkg}.service;\n\npublic interface {entity}Service {{}}\n"
            ),
        }

    if stage == "CONTROLLER":
        return {
            f"src/main/java/{path}/controller/{entity}Controller.java": (
                f"package {pkg}.controller;\n\n"
                f"import {pkg}.service.{entity}Service;\n\n"
                f"public class {entity}Controller {{\n"
                f"    private final {entity}Service service;\n"
                f"    public {entity}Controller({entity}Service service) {{ this.service = service; }}\n"
                f"}}\n"
            ),
            f"src/main/java/{path}/controller/GlobalExceptionHandler.java": (
                f"package {pkg}.controller;\n\n"
                f"@Provider\npublic class GlobalExceptionHandler {{}}\n"
            ),
        }

    if stage == "TEST":
        return {
            f"src/test/java/{path}/service/{entity}ServiceTest.java": (
                f"package {pkg}.service;\n\npublic class {entity}ServiceTest {{}}\n"
            ),
        }

    raise ValueError(f"no fixture artifacts for stage {stage!r}")


# ---------------------------------------------------------------------------
# Violation builders — one per rule the gate checks
# ---------------------------------------------------------------------------
def violate_layer_isolation(blueprint: Mapping[str, Any]) -> Dict[str, str]:
    """Principle I: a controller reaching directly into the repository layer."""
    pkg, path, entity = _pkg(blueprint), _pkg_path(blueprint), _first_entity(blueprint)
    return {
        f"src/main/java/{path}/controller/{entity}Controller.java": (
            f"package {pkg}.controller;\n\n"
            f"import {pkg}.repository.{entity}Repository;\n\n"
            f"public class {entity}Controller {{\n"
            f"    private {entity}Repository repository;\n"
            f"}}\n"
        ),
        # Include the advice so the *whole-project* rule cannot also fire; this
        # isolates the layer-isolation rule being tested.
        f"src/main/java/{path}/controller/GlobalExceptionHandler.java": (
            f"package {pkg}.controller;\n\n@Provider\npublic class GlobalExceptionHandler {{}}\n"
        ),
    }


def violate_contract_immutability(blueprint: Mapping[str, Any]) -> Dict[str, str]:
    """Principle II: a request contract declared as a class, not a record."""
    pkg, path, entity = _pkg(blueprint), _pkg_path(blueprint), _first_entity(blueprint)
    return {
        f"src/main/java/{path}/model/dto/Create{entity}Request.java": (
            f"package {pkg}.model.dto;\n\n"
            f"public class Create{entity}Request {{\n    private String name;\n}}\n"
        ),
    }


def violate_centralized_errors(blueprint: Mapping[str, Any]) -> Dict[str, str]:
    """Principle III, whole-project rule: no @Provider anywhere.

    The violation is reported against ``src/main/java``, which is outside every
    stage's artifact scope, so it resolves to ACCUMULATED and must not reject the
    stage that happens to be running.
    """
    pkg, path, entity = _pkg(blueprint), _pkg_path(blueprint), _first_entity(blueprint)
    return {
        f"src/main/java/{path}/controller/{entity}Controller.java": (
            f"package {pkg}.controller;\n\npublic class {entity}Controller {{}}\n"
        ),
    }


def violate_prohibited_annotation(blueprint: Mapping[str, Any]) -> Dict[str, str]:
    """Stack rule: a prohibited Lombok annotation on a JPA entity.

    Family A rates this MEDIUM and family B rates it HIGH; the adapter keeps the
    strictest, which makes it blocking.
    """
    pkg, path, entity = _pkg(blueprint), _pkg_path(blueprint), _first_entity(blueprint)
    return {
        f"src/main/java/{path}/model/entity/{entity}.java": (
            f"package {pkg}.model.entity;\n\n"
            f"@Data\npublic class {entity} {{\n    private Long id;\n}}\n"
        ),
    }


def violate_credential(blueprint: Mapping[str, Any]) -> Dict[str, str]:
    """FR-018: a credential embedded in a generated artifact."""
    pkg, path = _pkg(blueprint), _pkg_path(blueprint)
    return {
        f"src/main/java/{path}/Config.java": (
            f"package {pkg};\n\n"
            f"public class Config {{\n"
            f"    private static final String KEY = \"AIzaSyA1234567890abcdefghijklmnopqrstuv\";\n"
            f"}}\n"
        ),
    }


def violate_dependency_allowlist(blueprint: Mapping[str, Any]) -> Dict[str, str]:
    """FR-017: a dependency the offline build environment cannot resolve."""
    return {
        "pom.xml": (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<project xmlns=\"http://maven.apache.org/POM/4.0.0\">\n"
            "  <modelVersion>4.0.0</modelVersion>\n"
            "  <parent>\n"
            "    <groupId>io.quarkus</groupId>\n"
            "    <artifactId>quarkus-parent</artifactId>\n"
            "    <version>3.15.1</version>\n"
            "  </parent>\n"
            "  <dependencies>\n"
            "    <dependency>\n"
            "      <groupId>com.example.unlisted</groupId>\n"
            "      <artifactId>not-cached-anywhere</artifactId>\n"
            "    </dependency>\n"
            "  </dependencies>\n"
            "</project>\n"
        ),
    }


#: Rule key -> builder. Keys match the rule identifiers the adapter emits where
#: a single family owns the rule, and are descriptive where the rule is
#: whole-project or gate-local.
VIOLATION_BUILDERS = {
    "LAYER_ISOLATION": violate_layer_isolation,
    "CONTRACT_IMMUTABILITY": violate_contract_immutability,
    "CENTRALIZED_ERRORS": violate_centralized_errors,
    "PROHIBITED_ANNOTATION": violate_prohibited_annotation,
    "CREDENTIAL": violate_credential,
    "DEPENDENCY_ALLOWLIST": violate_dependency_allowlist,
}


def violating_artifacts(rule: str, blueprint: Mapping[str, Any]) -> Dict[str, str]:
    try:
        builder = VIOLATION_BUILDERS[rule]
    except KeyError:
        raise KeyError(f"unknown violation rule {rule!r}; known: {sorted(VIOLATION_BUILDERS)}") from None
    return builder(blueprint)
