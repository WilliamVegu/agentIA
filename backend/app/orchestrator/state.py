from typing import TypedDict, Optional, Dict, List, Any

class GenerationAgentState(TypedDict, total=False):
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
