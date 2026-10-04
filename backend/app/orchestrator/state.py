from typing import TypedDict, Optional, Dict, List, Any

class GenerationAgentState(TypedDict, total=False):
    execution_mode: str
    # --- Pre-existing structural fields. Names and semantics are unchanged;
    # --- FR-021 depends on the generated-artifact map and log list keeping them.
    session_id: str
    blueprint: Dict[str, Any]
    workspace_path: str
    current_phase: str
    generated_files: Dict[str, str]  # relative path -> content
    repair_attempts: int
    max_repair_attempts: int
    last_diagnostic: Optional[Dict[str, Any]]
    build_success: bool
    test_metrics: Optional[Dict[str, Any]]
    logs: List[str]
    status: str
    error: Optional[str]

    # --- Feature 011 additive fields (T012). All optional so that states built
    # --- by pre-existing callers continue to type-check unchanged.
    #
    # generation_mode is decided once per session at session start and is never
    # changed afterwards. The stage execution boundary (stages/runner.py) fails
    # loudly when it is absent rather than defaulting, because guessing the mode
    # would run an entire session against the wrong implementation.
    generation_mode: Optional[str]              # GenerationMode value: "MODEL" | "DETERMINISTIC"
    instruction_set_revision: Optional[str]     # content digest of the instruction set in force
    generation_journal: Optional[Dict[str, Any]]        # GenerationJournal — per-stage outcomes
    artifact_provenance: Optional[List[Dict[str, Any]]]  # GenerationProvenanceRecord list

    # --- Feature 012 additive field. Lets downstream nodes and the API see
    # --- whether verification actually ran, without re-reading test_metrics.
    # --- True means the sandbox could not build and substituted a result.
    verification_fallback_used: Optional[bool]

    # --- Feature 015 additive fields. These were MISSING, and their absence was
    # --- not cosmetic: LangGraph filters a node's state to the keys declared
    # --- here, so anything undeclared is silently dropped between the entry
    # --- point and the first node.
    # ---
    # --- The consequence was that MODEL mode could not run through the graph at
    # --- all. ``_ModeInjectingGraph`` selects the mode from the RAW state, so a
    # --- caller supplying a key got MODEL; LangGraph then stripped the key; the
    # --- stage found no client and raised GenerationModeError. The unit tests
    # --- never caught it because they call run_stage with a hand-built state and
    # --- bypass the graph entirely, so the model stages were only ever exercised
    # --- in isolation.
    # ---
    # --- Declared here rather than passed around the graph, and additive so that
    # --- states built by existing callers keep working unchanged. A caller that
    # --- supplies no key still resolves to DETERMINISTIC exactly as before.
    llm_api_key: Optional[str]                  # provider credential for MODEL mode
    llm_provider: Optional[str]                 # resolved provider for MODEL mode
    llm_model: Optional[str]                    # resolved model name for MODEL mode

    # --- Feature levantando_observaciones additive field. The deterministic
    # --- scaffolder records the ArchitecturePlan inferred from the blueprint's
    # --- inputInterface here, so downstream stages and the API can see the chosen
    # --- architecture without recomputing it. Optional: absent for blueprints with
    # --- no inputInterface, and for all pre-reframing sessions.
    architecture_plan: Optional[Dict[str, Any]]
