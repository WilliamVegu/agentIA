"""The stage execution boundary (task T016).

This is the single place a generation stage is invoked, and the only place that
owns mode selection, request/correction budgeting, compliance gating, provenance
recording, and correction-journal accumulation. Both execution paths call it,
which is what makes FR-022 true by construction rather than by discipline.

CONTRACT (see contracts/stage-execution.md)
-------------------------------------------
* ``generation_mode`` is resolved from state and **fails loudly when absent**.
  It is never defaulted: guessing the mode would run an entire session against
  the wrong implementation and could silently emit pre-migration output.
* ``DETERMINISTIC`` invokes the retained node implementation with **no
  validation gate** and ``request_count = 0``. The asymmetry is deliberate
  (FR-013): deterministic output is compliant by construction, and gating it
  would change offline behaviour.
* ``MODEL`` builds a request, calls ``LLMFactory.get_chat_model``, extracts
  artifacts, validates the accumulated set, and persists only on pass.
* Journal entries and provenance are appended on **every** exit path, including
  exhaustion.

RETENTION MODEL (FR-011)
------------------------
Every rejected response is retained, including the initial one:

* attempt 0 (the initial request) -> ``initial_response`` + ``initial_verdict``
  on the stage entry;
* attempts 1..2 (corrections) -> one ``CorrectionAttemptRecord`` each.

That keeps ``attempt_ordinal`` within 1..2 as the data model requires while
still satisfying FR-011's "the violation set and the model's response at each
attempt". Nothing is discarded on exhaustion.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from app.models.session import SessionPhase, SessionStatus
from app.orchestrator.stages import instructions as instructions_mod
from app.orchestrator.stages import journal as journal_mod
from app.orchestrator.stages.compliance import (
    ATTRIBUTION_LOCAL,
    SEVERITY_BLOCKING,
    ComplianceViolation,
    blocking_local_violations,
    check_dependency_allowlist,
    normalize_verdict,
)
from app.services.llm_factory import LLMFactory

# The retained deterministic implementations live in ``stages/deterministic``
# after T020. They are NOT imported from ``orchestrator/nodes``: those node
# modules now delegate *to this seam*, so importing them here would be circular.
from app.orchestrator.stages.deterministic import (
    controller as _det_controller,
    domain as _det_domain,
    scaffolder as _det_scaffolder,
    service as _det_service,
    test_synthesis as _det_test,
)

STAGE_ORDER: Tuple[str, ...] = instructions_mod.STAGE_ORDER

#: Workspace-relative glob patterns each stage owns. Used for FR-006 attribution:
#: a violation inside these patterns is LOCAL to the stage; anything else is
#: ACCUMULATED and must not reject the stage.
STAGE_ARTIFACT_SCOPES: Mapping[str, Tuple[str, ...]] = {
    "SCAFFOLDER": (
        "pom.xml",
        "src/main/resources/application.yml",
        "src/main/java/*Application.java",
    ),
    "DOMAIN": (
        "src/main/java/*/model/entity/*.java",
        "src/main/java/*/model/dto/*.java",
    ),
    "SERVICE": (
        "src/main/java/*/repository/*.java",
        "src/main/java/*/service/*.java",
        "src/main/java/*/service/impl/*.java",
        "src/main/java/*/exception/*.java",
    ),
    "CONTROLLER": ("src/main/java/*/controller/*.java",),
    "TEST": ("src/test/java/*/*.java",),
}

#: Retained deterministic implementations, keyed by stage. These carry the
#: original f-string logic unchanged (moved verbatim from the node modules in
#: T020), so the offline path is byte-for-byte what it was before this feature.
DETERMINISTIC_STAGE_IMPLEMENTATIONS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "SCAFFOLDER": _det_scaffolder.emit,
    "DOMAIN": _det_domain.emit,
    "SERVICE": _det_service.emit,
    "CONTROLLER": _det_controller.emit,
    "TEST": _det_test.emit,
}

#: Model-driven implementations, registered by the Phase 3 stages (T024-T028).
#: Empty until then, which is why a MODEL session cannot complete in this phase
#: and raises rather than silently producing deterministic output.
MODEL_STAGE_IMPLEMENTATIONS: Dict[str, "ModelStageImplementation"] = {}


class GenerationModeError(RuntimeError):
    """Raised when ``generation_mode`` is absent or not a known mode."""


class StageImplementationMissing(RuntimeError):
    """Raised when no implementation is registered for a stage in the active mode."""


@dataclass(frozen=True)
class ModelStageImplementation:
    """Protocol a model-driven stage must satisfy.

    ``build_request`` renders the instruction plus the blueprint-derived payload.
    ``extract`` maps a raw response onto workspace-relative artifacts and reports
    whether extraction succeeded. ``build_client`` constructs the chat model and
    is supplied by the stage itself, so each stage carries its own direct
    ``LLMFactory.get_chat_model`` call in its request-construction path rather
    than delegating that to the seam.
    """

    stage: str
    build_request: Callable[[Mapping[str, Any], str], str]
    extract: Callable[[str, Mapping[str, Any], str], Tuple[Dict[str, str], bool]]
    build_client: Optional[Callable[[Mapping[str, Any], Optional[str]], Any]] = None


def register_model_stage(implementation: ModelStageImplementation) -> None:
    """Register a model-driven stage implementation."""
    if implementation.stage not in STAGE_ORDER:
        raise ValueError(f"unknown stage {implementation.stage!r}")
    MODEL_STAGE_IMPLEMENTATIONS[implementation.stage] = implementation


def unregister_model_stage(stage: str) -> None:
    MODEL_STAGE_IMPLEMENTATIONS.pop(stage, None)


_MODEL_STAGES_LOADED = False


def ensure_model_stages_registered() -> None:
    """Import and register the five model stages on first use.

    The import is deferred to break an import cycle: the model stage modules
    import ``ModelStageImplementation`` and the payload/extraction helpers from
    this module, so this module must not import them at module load time.

    Registration uses set-if-absent semantics, so an implementation a test
    registered explicitly is never clobbered by the built-in ones.
    """
    global _MODEL_STAGES_LOADED
    if _MODEL_STAGES_LOADED:
        return
    from app.orchestrator.stages.model import register_all_model_stages  # noqa: PLC0415

    register_all_model_stages()
    _MODEL_STAGES_LOADED = True


# ---------------------------------------------------------------------------
# Mode resolution (guardrail 5)
# ---------------------------------------------------------------------------
def resolve_generation_mode(state: Mapping[str, Any]) -> str:
    """Read the session's generation mode.

    Fails loudly when absent. A missing mode is a defect in the caller, not a
    reason to guess.
    """
    if "generation_mode" not in state or state.get("generation_mode") is None:
        raise GenerationModeError(
            "generation_mode is absent from the generation state. The stage execution "
            "boundary refuses to default it: an entire session would otherwise run "
            "against the wrong implementation. Set it once at session start "
            "(see pipeline_runner.select_generation_mode / routes_session)."
        )
    mode = state["generation_mode"]
    if mode not in journal_mod.VALID_GENERATION_MODES:
        raise GenerationModeError(
            f"generation_mode {mode!r} is not one of {journal_mod.VALID_GENERATION_MODES}"
        )
    return mode


@dataclass(frozen=True)
class GenerationModeSelection:
    """The session's generation mode and the identity that produced it."""

    mode: str
    provider: Optional[str] = None
    model: Optional[str] = None
    reason: str = ""


def select_generation_mode(
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    *,
    force_deterministic: bool = False,
    offline_requested: bool = False,
) -> GenerationModeSelection:
    """Decide the generation mode ONCE per session, before any stage runs.

    Decision order (plan.md Constraint 3):

    1. An explicit operator request for deterministic generation wins even when
       credentials are present. This is required, not a convenience: the frozen
       baseline capture depends on being able to force the offline path while
       credentials are configured.
    2. An explicit offline/mock selection forces deterministic mode.
    3. Otherwise, attempt to construct the model client. If it cannot be
       constructed, fall back to deterministic mode.

    Note what this function does NOT do: it never inspects a *rejected response*
    to decide the mode. Falling back after a rejection would silently emit
    pre-migration boilerplate while reporting success, and would make the SC-001
    comparison unmeasurable.
    """
    if force_deterministic:
        return GenerationModeSelection(
            mode=journal_mod.GENERATION_MODE_DETERMINISTIC,
            reason="explicit operator request for deterministic generation",
        )

    if offline_requested or LLMFactory.is_mock(api_key, provider):
        return GenerationModeSelection(
            mode=journal_mod.GENERATION_MODE_DETERMINISTIC,
            reason="explicit offline/mock selection",
        )

    detected = LLMFactory.detect_provider(api_key, provider)
    resolved_model = LLMFactory.resolve_model_name(detected, model_name)

    try:
        client = LLMFactory.get_chat_model(
            api_key=api_key,
            provider=provider,
            model_name=model_name,
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001
        return GenerationModeSelection(
            mode=journal_mod.GENERATION_MODE_DETERMINISTIC,
            reason=f"model client construction failed: {type(exc).__name__}: {exc}",
        )

    if client is None:
        return GenerationModeSelection(
            mode=journal_mod.GENERATION_MODE_DETERMINISTIC,
            reason="no model client constructible",
        )

    return GenerationModeSelection(
        mode=journal_mod.GENERATION_MODE_MODEL,
        provider=detected,
        model=resolved_model,
        reason="model client constructible",
    )


def with_session_generation_mode(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Caller-boundary helper: populate ``generation_mode`` when the caller has not.

    **This is deliberately NOT used by ``run_stage``.** The seam still fails
    loudly on an absent mode. The helper exists so that *caller boundaries* — the
    graph entry, the node entry points when invoked directly, and the pipeline
    runners — can compute the mode once and hand it downstream, which is what a
    caller boundary is for.

    Putting the default here rather than in ``run_stage`` is the difference
    between "the entry point decides the session's mode" and "the seam guesses",
    and only the former is safe: a guess inside the seam would run an entire
    session against the wrong implementation with nothing to catch it.
    """
    prepared = dict(state)
    if prepared.get("generation_mode") is not None:
        return prepared

    selection = select_generation_mode(
        api_key=prepared.get("llm_api_key"),
        provider=prepared.get("llm_provider"),
        model_name=prepared.get("llm_model"),
        force_deterministic=bool(prepared.get("force_deterministic", False)),
    )
    prepared["generation_mode"] = selection.mode
    if selection.mode == journal_mod.GENERATION_MODE_MODEL:
        if prepared.get("llm_provider") is None:
            prepared["llm_provider"] = selection.provider
        if prepared.get("llm_model") is None:
            prepared["llm_model"] = selection.model
    else:
        # A DETERMINISTIC session records no model identity at all, so it can
        # never be miscounted as model-generated.
        prepared["llm_provider"] = None
        prepared["llm_model"] = None

    if not prepared.get("instruction_set_revision"):
        try:
            prepared["instruction_set_revision"] = instructions_mod.load_instruction_set().revision
        except Exception:  # noqa: BLE001
            # The deterministic path does not read instructions; the MODEL path
            # loads them itself and fails loudly if they are unusable.
            prepared["instruction_set_revision"] = ""
    return prepared


# ---------------------------------------------------------------------------
# Persistence and provenance
# ---------------------------------------------------------------------------
def artifact_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def persist_artifacts(workspace_path: str, artifacts: Mapping[str, str]) -> Tuple[str, ...]:
    """Write an accepted candidate set. Returns the paths written.

    All-or-nothing by convention: the caller only reaches here once the whole
    candidate set has passed validation (FR-004, FR-007).
    """
    base = Path(workspace_path)
    written = []
    for rel_path, content in sorted(artifacts.items()):
        target = base / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(rel_path)
    return tuple(written)


def _provenance_records(
    state: Mapping[str, Any],
    stage: str,
    written: Sequence[str],
    attempt_ordinal: int,
) -> list:
    mode = state.get("generation_mode")
    is_model = mode == journal_mod.GENERATION_MODE_MODEL
    # T036: only MODEL-mode artifacts carry a provider and model. A DETERMINISTIC
    # session records None for both — never a placeholder string such as
    # "deterministic" or "N/A" — so offline artifacts cannot be miscounted as
    # model-generated. The keys stay present (set to None) rather than being
    # omitted, because the pre-existing offline-parity test asserts
    # `record["provider"] is None`; dropping the key would break a test this
    # feature is forbidden from modifying.
    provider = state.get("llm_provider") if is_model else None
    model = state.get("llm_model") if is_model else None
    generated = state.get("generated_files", {}) or {}
    return [
        {
            "artifact_path": rel_path,
            "stage": stage,
            "generation_mode": mode,
            "provider": provider,
            "model": model,
            "instruction_set_revision": state.get("instruction_set_revision", ""),
            "attempt_ordinal": attempt_ordinal,
            "created_at": journal_mod.now_iso(),
            "content_digest": artifact_digest(generated.get(rel_path, "")),
        }
        for rel_path in written
    ]


def _ensure_journal(state: Dict[str, Any]) -> Dict[str, Any]:
    existing = state.get("generation_journal")
    if isinstance(existing, dict):
        return existing
    is_model = state.get("generation_mode") == journal_mod.GENERATION_MODE_MODEL
    created = journal_mod.new_journal(
        session_id=state.get("session_id", "unknown"),
        generation_mode=state["generation_mode"],
        instruction_set_revision=state.get("instruction_set_revision", "") or "",
        provider=state.get("llm_provider") if is_model else None,
        model=state.get("llm_model") if is_model else None,
    )
    state["generation_journal"] = created
    return created


def _mark_human_intervention_required(state: Dict[str, Any]) -> None:
    """Move the session to the human-intervention terminal state.

    The status and phase are taken from the **same** ``SessionStatus`` /
    ``SessionPhase`` members the sandbox repair loop uses on exhaustion
    (``repair_node``), so FR-010's "same terminal state" is structural rather
    than a string that happens to match. The existing human-intervention path and
    unlock console therefore handle both exhaustions uniformly.
    """
    state["status"] = SessionStatus.BLOCKED.value
    state["current_phase"] = SessionPhase.FAILED.value


def _append_log(state: Dict[str, Any], line: str) -> None:
    state.setdefault("logs", []).append(line)


def _isolate_state(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Copy state and the containers the retained nodes mutate in place.

    This keeps ``run_stage`` non-destructive for its caller: the retained nodes
    mutate ``generated_files`` and ``logs`` in place, and that mutation must not
    leak back out through a shared reference.
    """
    isolated = dict(state)
    isolated["generated_files"] = dict(state.get("generated_files") or {})
    isolated["logs"] = list(state.get("logs") or [])
    isolated["artifact_provenance"] = list(state.get("artifact_provenance") or [])
    return isolated


# ---------------------------------------------------------------------------
# T022 — task payload construction
# ---------------------------------------------------------------------------
#: Which earlier stages' artifacts a stage may see. A stage sees only the union
#: of its declared dependencies' scopes, never the whole workspace: exposing
#: artifacts a stage does not own would let it reason about, and silently
#: depend on, code outside its responsibility.
STAGE_PRIOR_STAGES: Mapping[str, Tuple[str, ...]] = {
    "SCAFFOLDER": (),
    "DOMAIN": ("SCAFFOLDER",),
    "SERVICE": ("SCAFFOLDER", "DOMAIN"),
    "CONTROLLER": ("SCAFFOLDER", "DOMAIN", "SERVICE"),
    "TEST": ("SCAFFOLDER", "DOMAIN", "SERVICE", "CONTROLLER"),
}

#: Upper bound on a rendered request. Exceeding it is NEVER resolved by trimming:
#: a trimmed payload would silently drop blueprint content the model is required
#: to honour, which is worse than failing loudly.
MAX_PAYLOAD_CHARS = 200_000

#: Rule identifier for an artifact emitted outside its stage's artifact scope.
RULE_OUT_OF_SCOPE_ARTIFACT = "OUT_OF_SCOPE_ARTIFACT"

#: Rule identifier for a candidate set too small to cover the declared entities.
RULE_PARTIAL_CANDIDATE_SET = "PARTIAL_CANDIDATE_SET"

#: Stages whose artifact contract scales with the number of declared domain
#: entities. A response covering fewer entities than the blueprint declares is a
#: partial set, which T023 forbids persisting silently.
PER_ENTITY_STAGES: Tuple[str, ...] = ("DOMAIN", "SERVICE", "CONTROLLER", "TEST")


class PayloadTooLargeError(RuntimeError):
    """Raised when a rendered stage request would exceed ``MAX_PAYLOAD_CHARS``."""


def _in_scope(path: str, scope: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in scope)


def _scope_patterns(stages: Sequence[str]) -> Tuple[str, ...]:
    return tuple(pattern for stage in stages for pattern in STAGE_ARTIFACT_SCOPES[stage])


def paths_in_scope(paths: Sequence[str], stages: Sequence[str]) -> Tuple[str, ...]:
    patterns = _scope_patterns(stages)
    return tuple(p for p in paths if _in_scope(p, patterns))


def prior_artifact_paths(stage: str, generated_files: Mapping[str, str]) -> Tuple[str, ...]:
    """Paths the stage may see: prior stages' scopes ∩ already-persisted files.

    ``generated_files`` contains only *persisted* artifacts by construction — the
    seam adds to it exclusively after a candidate set passed validation — so a
    rejected response can never reach a later stage through this path.
    """
    return tuple(sorted(paths_in_scope(sorted(generated_files), STAGE_PRIOR_STAGES[stage])))


def build_stage_payload(state: Mapping[str, Any], stage: str) -> Dict[str, Any]:
    """Project the blueprint into the payload a stage's request carries.

    Carries service identity, package, entities with their attributes and
    declared constraints, user stories, and acceptance scenarios — the content
    the deterministic emitters discarded, and precisely what SC-001 measures.
    """
    blueprint = dict(state.get("blueprint") or {})

    entities = [
        {
            "name": entity.get("name"),
            "tableName": entity.get("tableName") or entity.get("table_name"),
            "attributes": [
                {
                    "name": attribute.get("name"),
                    "type": attribute.get("type"),
                    "nullable": attribute.get("nullable"),
                    "isPrimaryKey": bool(
                        attribute.get("isPrimaryKey") or attribute.get("is_identifier")
                    ),
                    "validationRules": list(attribute.get("validationRules") or []),
                }
                for attribute in (entity.get("attributes") or [])
            ],
        }
        for entity in (blueprint.get("entities") or [])
    ]

    user_stories = [
        {
            "id": story.get("id"),
            "priority": story.get("priority"),
            "role": story.get("role"),
            "intent": story.get("intent"),
            "benefit": story.get("benefit"),
            "scenarios": [
                {
                    "scenarioId": scenario.get("scenarioId") or scenario.get("scenario_id"),
                    "given": scenario.get("given"),
                    "when": scenario.get("when"),
                    "then": scenario.get("then"),
                }
                for scenario in (story.get("scenarios") or [])
            ],
        }
        for story in (blueprint.get("userStories") or blueprint.get("user_stories") or [])
    ]

    generated = dict(state.get("generated_files") or {})
    visible = prior_artifact_paths(stage, generated)

    return {
        "stage": stage,
        "instruction_set_revision": state.get("instruction_set_revision", ""),
        "service_name": blueprint.get("serviceName") or blueprint.get("service_name"),
        "package_name": blueprint.get("packageName") or blueprint.get("package_name"),
        "base_port": blueprint.get("basePort") or blueprint.get("base_port"),
        "entities": entities,
        "user_stories": user_stories,
        "prior_artifacts": {path: generated[path] for path in visible},
    }


def render_stage_request(state: Mapping[str, Any], stage: str, instruction: str) -> str:
    """Render the full request text: instruction, payload, and owned paths.

    :raises PayloadTooLargeError: when the rendered request exceeds the bound.
        The caller records this as an unusable attempt rather than sending a
        truncated payload.
    """
    payload = build_stage_payload(state, stage)
    request = (
        f"{instruction}\n\n"
        f"## Task payload\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}\n\n"
        f"## Output paths you own\n"
        f"{json.dumps(list(STAGE_ARTIFACT_SCOPES[stage]), indent=2)}\n"
    )
    if len(request) > MAX_PAYLOAD_CHARS:
        raise PayloadTooLargeError(
            f"rendered request for stage {stage!r} is {len(request)} characters, above the "
            f"bound of {MAX_PAYLOAD_CHARS}. The payload is never trimmed: dropping blueprint "
            f"content would silently change what the model is asked to honour."
        )
    return request


# ---------------------------------------------------------------------------
# T023 — model response extraction
# ---------------------------------------------------------------------------
#: One fenced block. The fence info string may carry a language tag followed by
#: the workspace-relative path the block belongs to.
_FENCED_BLOCK_RE = re.compile(r"```[ \t]*(?P<info>[^\n`]*)\n(?P<body>.*?)```", re.DOTALL)


def _is_safe_relative_path(path: str) -> bool:
    normalized = path.replace("\\", "/").strip()
    if not normalized or normalized.startswith("/"):
        return False
    if re.match(r"^[A-Za-z]:", normalized):     # windows drive letter
        return False
    return ".." not in normalized.split("/")


def _block_path(info: str) -> str:
    """Extract the artifact path from a fence info string.

    Accepts ``path`` or ``<language> path``; returns "" when no path-like token
    is present.
    """
    tokens = [token for token in info.replace("\t", " ").split(" ") if token]
    if not tokens:
        return ""
    candidate = tokens[-1]
    return candidate if ("/" in candidate or candidate.endswith((".java", ".xml", ".yml", ".yaml", ".sql"))) else ""


def extract_artifacts(response_text: str) -> Tuple[Dict[str, str], bool]:
    """Map a raw model response onto workspace-relative artifacts.

    Accepts two transports:

    1. a JSON object ``{"artifacts": {path: content}}``;
    2. one or more fenced blocks, each with its path on the fence line.

    Returns ``({}, False)`` — never a partial set — for an absent, truncated, or
    unmappable response, and for an ambiguous one (a fenced block without a path
    when more than one artifact is implied). Silence is deliberately not an
    option: a partial candidate set must never reach persistence.
    """
    if not response_text or not response_text.strip():
        return {}, False

    # --- Transport 1: JSON artifact map -------------------------------------
    try:
        payload = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        payload = None
    if isinstance(payload, dict):
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, dict) or not artifacts:
            return {}, False
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in artifacts.items()):
            return {}, False
        if not all(_is_safe_relative_path(path) for path in artifacts):
            return {}, False
        return dict(artifacts), True

    # --- Transport 2: fenced blocks -----------------------------------------
    if response_text.count("```") % 2 != 0:
        return {}, False                        # an opening fence was never closed
    blocks = _FENCED_BLOCK_RE.findall(response_text)
    if not blocks:
        return {}, False

    artifacts: Dict[str, str] = {}
    for info, body in blocks:
        path = _block_path(info)
        if not path or not _is_safe_relative_path(path):
            # Ambiguous: several artifacts cannot be told apart without paths.
            return {}, False
        artifacts[path] = body

    return (artifacts, True) if artifacts else ({}, False)


def out_of_scope_violations(
    candidate: Mapping[str, str], stage: str
) -> Tuple[ComplianceViolation, ...]:
    """Flag paths a stage emitted outside its own artifact scope.

    Attributed LOCAL by construction, not resolved by pattern matching: a path
    outside the scope is by definition outside every scope pattern, so the
    generic resolver would call it ACCUMULATED and let it through. It is the
    stage's own fault and must reject the candidate set (FR-021: a stage
    inventing paths would break the index contract).
    """
    scope = STAGE_ARTIFACT_SCOPES[stage]
    return tuple(
        ComplianceViolation(
            artifact_path=path,
            rule_id=RULE_OUT_OF_SCOPE_ARTIFACT,
            severity=SEVERITY_BLOCKING,
            message=(
                f"{path!r} is outside the {stage} stage's artifact scope. A stage must emit "
                f"only the paths it owns, because downstream verification, artifact listing "
                f"and export all depend on the path contract."
            ),
            suggested_fix=f"Emit only these paths: {list(scope)}",
            attribution=ATTRIBUTION_LOCAL,
            contributing_sources=("runner.out_of_scope_violations",),
        )
        for path in sorted(candidate)
        if not _in_scope(path, scope)
    )


def partial_candidate_violations(
    candidate: Mapping[str, str], stage: str, state: Mapping[str, Any]
) -> Tuple[ComplianceViolation, ...]:
    """Flag a response that covers fewer entities than the blueprint declares.

    This is the "the reverse" half of T023's ambiguity rule: one artifact where
    several were requested. It is checked against the blueprint's own entity
    count, which is the independent source of truth, and only for stages whose
    output scales per entity — a blanket expected-count check would need the
    instructions' Output contract to be machine-readable, which it is not yet.
    """
    if stage not in PER_ENTITY_STAGES:
        return ()
    entity_count = len((state.get("blueprint") or {}).get("entities") or [])
    if entity_count <= 1 or len(candidate) >= entity_count:
        return ()
    return (
        ComplianceViolation(
            artifact_path=f"<{stage}>",
            rule_id=RULE_PARTIAL_CANDIDATE_SET,
            severity=SEVERITY_BLOCKING,
            message=(
                f"response carries {len(candidate)} artifact(s) for {entity_count} declared "
                f"domain entities. A partial set must not be persisted silently."
            ),
            suggested_fix="Emit artifacts for every declared entity in the payload.",
            attribution=ATTRIBUTION_LOCAL,
            contributing_sources=("runner.partial_candidate_violations",),
        ),
    )


# ---------------------------------------------------------------------------
# Deterministic path — no gate, request_count = 0
# ---------------------------------------------------------------------------
def _run_deterministic_stage(
    state: Dict[str, Any],
    stage: str,
    journal: Dict[str, Any],
) -> Dict[str, Any]:
    implementation = DETERMINISTIC_STAGE_IMPLEMENTATIONS.get(stage)
    if implementation is None:
        raise StageImplementationMissing(f"no deterministic implementation registered for stage {stage!r}")

    before = set(state.get("generated_files", {}) or {})
    _append_log(state, f"[STAGE:{stage}] deterministic path (no model request, no gate)")

    returned = implementation(state)
    if isinstance(returned, dict):
        # Consume returned state rather than relying on in-place mutation. The
        # retained nodes currently mutate as well, but depending on that aliasing
        # is the hazard recorded in research.md D8.
        merged = dict(state.get("generated_files", {}) or {})
        merged.update(returned.get("generated_files", {}) or {})
        returned = dict(returned)
        returned["generated_files"] = merged
        state.update(returned)

    written = tuple(sorted(set(state.get("generated_files", {}) or {}) - before))

    journal_mod.record_stage_entry(
        journal,
        stage=stage,
        outcome=journal_mod.OUTCOME_SUCCEEDED,
        request_count=0,                      # deterministic: no model request
        persisted_artifact_paths=written,
    )
    state.setdefault("artifact_provenance", []).extend(
        _provenance_records(state, stage, written, attempt_ordinal=0)
    )
    _append_log(state, f"[STAGE:{stage}] persisted {len(written)} artifacts (offline path)")
    return state


# ---------------------------------------------------------------------------
# Model path — request, gate, bounded correction
# ---------------------------------------------------------------------------
def _build_model_client(state: Mapping[str, Any], api_key: Optional[str] = None):
    """Construct the chat model.

    Guardrail 1: the model path MUST call ``LLMFactory.get_chat_model``. It is
    called even on the path that has no registered implementation, so the model
    branch can never silently degenerate into the deterministic one.
    """
    return LLMFactory.get_chat_model(
        api_key=api_key if api_key is not None else state.get("llm_api_key"),
        provider=state.get("llm_provider"),
        model_name=state.get("llm_model"),
        temperature=0.2,
    )


def _correction_feedback(violations: Sequence[ComplianceViolation]) -> str:
    lines = ["The previous response was rejected by compliance validation. Fix every item:"]
    for v in violations:
        lines.append(f"- [{v.rule_id}] {v.artifact_path}: {v.message}")
        if v.suggested_fix:
            lines.append(f"  suggested fix: {v.suggested_fix}")
    return "\n".join(lines)


def _run_model_stage(
    state: Dict[str, Any],
    stage: str,
    journal: Dict[str, Any],
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_model_stages_registered()
    implementation = MODEL_STAGE_IMPLEMENTATIONS.get(stage)

    if implementation is None:
        # Guardrail 1: even this failure path constructs the client, so the model
        # branch can never silently degenerate into the deterministic one.
        if _build_model_client(state, api_key=api_key) is None:
            raise GenerationModeError(
                f"session is in MODEL mode but LLMFactory.get_chat_model returned no client for "
                f"stage {stage!r}. Mode selection should have chosen DETERMINISTIC; this is an "
                f"inconsistent session state, not a reason to fall back."
            )
        raise StageImplementationMissing(
            f"no model-driven implementation registered for stage {stage!r}. The boundary "
            f"refuses to substitute deterministic generation."
        )

    # The stage owns its own LLMFactory.get_chat_model call. There is deliberately
    # no shared fallback: routing construction through the seam is exactly what
    # would let the model path silently degrade into a single implementation
    # again, which the per-stage ownership exists to prevent.
    if implementation.build_client is None:
        raise StageImplementationMissing(
            f"stage {stage!r} supplies no build_client. Every model stage must construct its "
            f"own client with a direct LLMFactory.get_chat_model call in its request-"
            f"construction path."
        )
    client = implementation.build_client(state, api_key)

    if client is None:
        raise GenerationModeError(
            f"session is in MODEL mode but LLMFactory.get_chat_model returned no client for "
            f"stage {stage!r}."
        )

    instruction_set = instructions_mod.load_instruction_set()
    instruction = instruction_set.for_stage(stage)
    scope = STAGE_ARTIFACT_SCOPES[stage]

    persisted_paths: Tuple[str, ...] = ()
    corrections: list = []
    initial_response: Optional[str] = None
    initial_verdict: Optional[Dict[str, Any]] = None
    requests_used = 0
    previous_digest: Optional[str] = None
    feedback: Optional[str] = None
    blocking_violations: Tuple[ComplianceViolation, ...] = ()
    last_verdict_dict: Optional[Dict[str, Any]] = None

    # attempt 0 = the initial request; 1..MAX = corrections.
    for attempt in range(0, journal_mod.MAX_CORRECTION_ATTEMPTS + 1):
        try:
            request = implementation.build_request(state, instruction)
        except PayloadTooLargeError as exc:
            # The attempt is consumed and the session blocks: the payload is a pure
            # function of the blueprint, so a retry would build the identical
            # oversized request. Nothing is persisted and the reason is journalled.
            #
            # request_count is deliberately 0: no model request was issued, and the
            # session budget counts model calls (SC-005), not attempts. Recording a
            # request that never left the process would inflate that accounting.
            journal_mod.record_stage_entry(
                journal,
                stage=stage,
                outcome=journal_mod.OUTCOME_UNUSABLE_RESPONSE,
                request_count=0,
                persisted_artifact_paths=[],
            )
            entry = journal_mod.stage_entry(journal, stage)
            if entry is not None:
                entry["payload_error"] = str(exc)
                entry["attempt_consumed"] = True   # an attempt, not a model call
            state["generation_journal"] = journal
            _mark_human_intervention_required(state)
            state["error"] = f"[{stage}] {exc}"
            _append_log(state, f"[STAGE:{stage}] payload too large; session blocked, nothing persisted")
            return state

        if feedback:
            request = f"{request}\n\n{feedback}"

        request_digest = journal_mod.digest_request(request)
        requests_used += 1

        response = client.invoke(request)
        response_text = getattr(response, "content", None) or str(response)
        candidate, extraction_ok = implementation.extract(response_text, state, instruction)

        if not extraction_ok:
            # An unusable response consumes an attempt and is never persisted
            # (FR-014). It is retained like any other rejected attempt.
            blocking_violations = ()
            last_verdict_dict = None
            if attempt == 0:
                initial_response = response_text
                initial_verdict = None
            else:
                corrections.append(
                    journal_mod.build_correction_attempt(
                        attempt_ordinal=attempt,
                        request=request,
                        response=response_text,
                        verdict=None,
                        outcome=journal_mod.OUTCOME_UNUSABLE_RESPONSE,
                        previous_request_digest=previous_digest,
                    )
                )
            previous_digest = request_digest
            feedback = "The previous response could not be parsed as source artifacts. Return only the requested files."
            _append_log(state, f"[STAGE:{stage}] attempt {attempt}: unusable response")
            continue

        accumulated = dict(state.get("generated_files", {}) or {})
        accumulated.update(candidate)

        extra: list = list(out_of_scope_violations(candidate, stage))
        extra.extend(partial_candidate_violations(candidate, stage, state))
        if stage == "SCAFFOLDER" and "pom.xml" in candidate:
            extra.extend(
                check_dependency_allowlist(
                    candidate["pom.xml"], artifact_path="pom.xml", stage_scope=scope
                )
            )

        verdict = normalize_verdict(accumulated, stage_scope=scope, extra_violations=extra)
        last_verdict_dict = verdict.to_dict()
        blocking_violations = blocking_local_violations(verdict)

        if not blocking_violations:
            written = persist_artifacts(state["workspace_path"], candidate)
            state["generated_files"] = accumulated
            persisted_paths = written
            # A stage that needed at least one correction is CORRECTED, even when
            # no individual correction was itself rejected. Deriving the outcome
            # from len(corrections) instead would report SUCCEEDED for a stage
            # whose initial response failed validation, under-reporting exactly
            # the signal the journal exists to capture.
            outcome = (
                journal_mod.OUTCOME_CORRECTED if attempt > 0
                else journal_mod.OUTCOME_SUCCEEDED
            )
            journal_mod.record_stage_entry(
                journal,
                stage=stage,
                outcome=outcome,
                request_count=requests_used,
                initial_verdict=initial_verdict,
                correction_attempts=corrections,
                persisted_artifact_paths=written,
                corrections_used=attempt,
            )
            entry = journal_mod.stage_entry(journal, stage)
            if entry is not None:
                entry["initial_response"] = initial_response
                entry["final_verdict"] = last_verdict_dict
            state.setdefault("artifact_provenance", []).extend(
                _provenance_records(state, stage, written, attempt_ordinal=attempt)
            )
            _append_log(
                state,
                f"[STAGE:{stage}] persisted {len(written)} artifacts after {requests_used} request(s)",
            )
            if verdict.accumulated_count:
                _append_log(
                    state,
                    f"[STAGE:{stage}] {verdict.accumulated_count} accumulated-attribution "
                    f"violation(s) recorded but not charged to this stage (FR-006)",
                )
            state["generation_journal"] = journal
            return state

        # Rejected: retain the attempt, then feed the violations into the retry.
        if attempt == 0:
            initial_response = response_text
            initial_verdict = last_verdict_dict
        else:
            corrections.append(
                journal_mod.build_correction_attempt(
                    attempt_ordinal=attempt,
                    request=request,
                    response=response_text,
                    verdict=last_verdict_dict,
                    outcome=journal_mod.OUTCOME_EXHAUSTED,
                    previous_request_digest=previous_digest,
                )
            )
        previous_digest = request_digest
        feedback = _correction_feedback(blocking_violations)
        _append_log(
            state,
            f"[STAGE:{stage}] attempt {attempt}: rejected with "
            f"{len(blocking_violations)} blocking local violation(s)",
        )

    # Exhausted: nothing persisted, everything retained (FR-011), session blocked.
    journal_mod.record_stage_entry(
        journal,
        stage=stage,
        outcome=journal_mod.OUTCOME_EXHAUSTED,
        request_count=requests_used,
        initial_verdict=initial_verdict,
        correction_attempts=corrections,
        persisted_artifact_paths=list(persisted_paths),
        corrections_used=journal_mod.MAX_CORRECTION_ATTEMPTS,
    )
    entry = journal_mod.stage_entry(journal, stage)
    if entry is not None:
        entry["initial_response"] = initial_response
        entry["final_verdict"] = last_verdict_dict
    state["generation_journal"] = journal
    _mark_human_intervention_required(state)
    state["error"] = (
        f"[{stage}] correction budget exhausted after "
        f"{journal_mod.MAX_CORRECTION_ATTEMPTS} correction attempts; human intervention required"
    )
    _append_log(
        state,
        f"[STAGE:{stage}] exhausted correction budget; session blocked, no artifact persisted",
    )
    return state


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def run_stage(
    state: Dict[str, Any],
    stage: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute one generation stage against ``state`` and return updated state.

    Callers MUST consume the returned value. They must not rely on this function
    mutating dictionaries retrieved from the input state.
    """
    if stage not in STAGE_ORDER:
        raise ValueError(f"unknown stage {stage!r}; expected one of {STAGE_ORDER}")

    isolated = _isolate_state(state)
    mode = resolve_generation_mode(isolated)     # fails loudly when absent
    journal = _ensure_journal(isolated)

    result = isolated
    try:
        journal_mod.assert_within_budget(journal)
        if mode == journal_mod.GENERATION_MODE_DETERMINISTIC:
            result = _run_deterministic_stage(isolated, stage, journal)
        else:
            result = _run_model_stage(isolated, stage, journal, api_key=api_key)
    except journal_mod.JournalBudgetError as exc:
        # T037: budget exhaustion terminates the session in the human-intervention
        # state rather than escaping as an unhandled exception. The recorded
        # history is kept intact.
        _mark_human_intervention_required(isolated)
        isolated["error"] = f"[{stage}] {exc}"
        _append_log(
            isolated,
            f"[STAGE:{stage}] session request budget exhausted; human intervention required",
        )
        result = isolated
    finally:
        # T038: the journal is persisted on EVERY exit path — success, failure,
        # exhaustion, and an exception propagating out of a stage — so the
        # correction history survives beyond process life (SC-008). An exception
        # still propagates; the finally block only guarantees the write happens.
        journal_mod.persist_generation_journal(
            session_id=result.get("session_id") or isolated.get("session_id"),
            journal=journal,
            provenance=result.get("artifact_provenance") or isolated.get("artifact_provenance"),
        )
    return result


def run_stages(
    state: Dict[str, Any],
    stages: Sequence[str] = STAGE_ORDER,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Run several stages in order, threading the returned state forward."""
    current = dict(state)
    for stage in stages:
        current = run_stage(current, stage, api_key=api_key)
        if current.get("status") == SessionStatus.BLOCKED.value:
            break
    return current
