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

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from app.orchestrator.stages import instructions as instructions_mod
from app.orchestrator.stages import journal as journal_mod
from app.orchestrator.stages.compliance import (
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
    """Protocol a Phase 3 model-driven stage must satisfy.

    ``build_request`` renders the instruction plus the blueprint-derived payload.
    ``extract`` maps a raw response onto workspace-relative artifacts and reports
    whether extraction succeeded.
    """

    stage: str
    build_request: Callable[[Mapping[str, Any], str], str]
    extract: Callable[[str, Mapping[str, Any], str], Tuple[Dict[str, str], bool]]


def register_model_stage(implementation: ModelStageImplementation) -> None:
    """Register a model-driven stage implementation (used by T024-T028 and tests)."""
    if implementation.stage not in STAGE_ORDER:
        raise ValueError(f"unknown stage {implementation.stage!r}")
    MODEL_STAGE_IMPLEMENTATIONS[implementation.stage] = implementation


def unregister_model_stage(stage: str) -> None:
    MODEL_STAGE_IMPLEMENTATIONS.pop(stage, None)


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
    # DETERMINISTIC sessions record no provider or model rather than placeholders,
    # so they cannot be miscounted as model-generated.
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
    implementation = MODEL_STAGE_IMPLEMENTATIONS.get(stage)

    # Guardrail 1: always construct the client before deciding anything else.
    client = _build_model_client(state, api_key=api_key)

    if implementation is None:
        if client is None:
            raise GenerationModeError(
                f"session is in MODEL mode but LLMFactory.get_chat_model returned no client for "
                f"stage {stage!r}. Mode selection should have chosen DETERMINISTIC; this is an "
                f"inconsistent session state, not a reason to fall back."
            )
        raise StageImplementationMissing(
            f"no model-driven implementation registered for stage {stage!r}. The five model "
            f"stages are tasks T024-T028 (Phase 3); until they land, MODEL sessions cannot "
            f"complete. The boundary refuses to substitute deterministic generation."
        )

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
        request = implementation.build_request(state, instruction)
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

        extra: list = []
        if stage == "SCAFFOLDER" and "pom.xml" in candidate:
            extra = check_dependency_allowlist(
                candidate["pom.xml"], artifact_path="pom.xml", stage_scope=scope
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
    state["status"] = "BLOCKED"
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
    journal_mod.assert_within_budget(journal)

    if mode == journal_mod.GENERATION_MODE_DETERMINISTIC:
        return _run_deterministic_stage(isolated, stage, journal)
    return _run_model_stage(isolated, stage, journal, api_key=api_key)


def run_stages(
    state: Dict[str, Any],
    stages: Sequence[str] = STAGE_ORDER,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Run several stages in order, threading the returned state forward."""
    current = dict(state)
    for stage in stages:
        current = run_stage(current, stage, api_key=api_key)
        if current.get("status") == "BLOCKED":
            break
    return current
