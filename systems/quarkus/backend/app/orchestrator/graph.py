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
from app.orchestrator.stages.runner import with_session_generation_mode

def _route_after_validator(state: GenerationAgentState) -> str:
    if state.get("status") == "FAILED":
        return END
    return "scaffolder"

def _route_after_sandbox(state: GenerationAgentState) -> str:
    if (state.get('test_metrics') or {}).get('verificationSkipped'): return END
    if state.get("build_success", False):
        return END
    if state.get("status") in {"BLOCKED", "PAUSED"}:
        return END
    return "repair"

def _route_after_repair(state: GenerationAgentState) -> str:
    if state.get("build_success"):
        return END
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


class _ModeInjectingGraph:
    """Caller boundary around the compiled graph (T020).

    Supplies ``generation_mode`` at the graph entry — once, before the first node
    runs — using the existing ``select_generation_mode()`` helper. This is the
    right place for it: computing the mode once and handing it downstream is
    exactly what a caller boundary does.

    The wrapper deliberately does **not** alter the graph. Node names, node
    count, topology and conditional edges are untouched, so phase-transition
    events, build-log streaming and repair-iteration events behave exactly as
    before (FR-021). It also does not add a default inside the seam: the stage
    execution boundary still fails loudly when ``generation_mode`` is absent, and
    that refusal is what stops a session from silently running against the wrong
    implementation.
    """

    __slots__ = ("_compiled",)

    def __init__(self, compiled):
        self._compiled = compiled

    def invoke(self, state, *args, **kwargs):
        return self._compiled.invoke(with_session_generation_mode(state), *args, **kwargs)

    async def ainvoke(self, state, *args, **kwargs):
        return await self._compiled.ainvoke(with_session_generation_mode(state), *args, **kwargs)

    def stream(self, state, *args, **kwargs):
        return self._compiled.stream(with_session_generation_mode(state), *args, **kwargs)

    async def astream(self, state, *args, **kwargs):
        async for item in self._compiled.astream(with_session_generation_mode(state), *args, **kwargs):
            yield item

    def __getattr__(self, name):
        # Anything not wrapped (get_graph, get_state, update_state, ...) is
        # delegated to the compiled graph unchanged.
        return getattr(self._compiled, name)


# Singleton graph, wrapped with the entry-boundary mode injection above.
generation_graph = _ModeInjectingGraph(create_generation_graph())

