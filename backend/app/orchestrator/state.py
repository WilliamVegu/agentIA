from typing import TypedDict, Optional, Dict, List, Any

class GenerationAgentState(TypedDict, total=False):
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

