from typing import Dict, Any
from app.orchestrator.state import GenerationAgentState
from app.models.session import SessionPhase

def validator_node(state: GenerationAgentState) -> Dict[str, Any]:
    """
    Validates blueprint data model and acceptance criteria prior to code generation.
    """
    blueprint = state.get("blueprint", {})
    logs = state.get("logs", [])
    service_name = blueprint.get("serviceName") or blueprint.get("service_name", "microservice")
    logs.append(f"[VALIDATOR] Validating blueprint for {service_name}")
    
    entities = blueprint.get("entities", [])
    user_stories = blueprint.get("userStories") or blueprint.get("user_stories", [])
    if not entities:
        return {
            "current_phase": SessionPhase.FAILED.value,
            "status": "FAILED",
            "error": "Blueprint must contain at least one domain entity",
            "logs": logs
        }
        
    logs.append(f"[VALIDATOR] Blueprint valid: {len(entities)} entities, {len(user_stories)} user stories.")
    return {
        "current_phase": SessionPhase.SCAFFOLDING.value,
        "logs": logs
    }
