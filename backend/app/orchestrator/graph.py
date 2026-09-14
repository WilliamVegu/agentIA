from langgraph.graph import StateGraph, START, END
from app.orchestrator.state import GenerationAgentState
from app.orchestrator.nodes.validator_node import validator_node
from app.orchestrator.nodes.scaffolder_node import scaffolder_node
from app.orchestrator.nodes.domain_node import domain_node
from app.orchestrator.nodes.service_node import service_node
from app.orchestrator.nodes.controller_node import controller_node
from app.orchestrator.nodes.test_node import test_node
from app.orchestrator.nodes.sandbox_node import sandbox_node
from app.orchestrator.nodes.repair_node import repair_node

def _route_after_validator(state: GenerationAgentState) -> str:
    if state.get("status") == "FAILED":
        return END
    return "scaffolder"

def _route_after_sandbox(state: GenerationAgentState) -> str:
    if state.get("build_success", False):
        return END
    if state.get("status") == "BLOCKED":
        return END
    return "repair"

def _route_after_repair(state: GenerationAgentState) -> str:
    if state.get("status") == "BLOCKED":
        return END
    return "sandbox"

def create_generation_graph():
    """
    Constructs the LangGraph state graph governing microservice synthesis,
    sandbox verification, and bounded auto-repair.
    """
    workflow = StateGraph(GenerationAgentState)

    # Register nodes
    workflow.add_node("validator", validator_node)
    workflow.add_node("scaffolder", scaffolder_node)
    workflow.add_node("domain", domain_node)
    workflow.add_node("service", service_node)
    workflow.add_node("controller", controller_node)
    workflow.add_node("test", test_node)
    workflow.add_node("sandbox", sandbox_node)
    workflow.add_node("repair", repair_node)

    # Add edges
    workflow.add_edge(START, "validator")
    workflow.add_conditional_edges("validator", _route_after_validator, {
        "scaffolder": "scaffolder",
        END: END
    })
    workflow.add_edge("scaffolder", "domain")
    workflow.add_edge("domain", "service")
    workflow.add_edge("service", "controller")
    workflow.add_edge("controller", "test")
    workflow.add_edge("test", "sandbox")

    workflow.add_conditional_edges("sandbox", _route_after_sandbox, {
        END: END,
        "repair": "repair"
    })
    workflow.add_conditional_edges("repair", _route_after_repair, {
        END: END,
        "sandbox": "sandbox"
    })

    return workflow.compile()

# Singleton compiled graph
generation_graph = create_generation_graph()

