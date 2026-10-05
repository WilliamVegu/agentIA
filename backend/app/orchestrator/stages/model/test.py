"""Model-driven test stage (task T026).

The stage's request-construction path calls ``LLMFactory.get_chat_model``
**directly** (see ``build_client``). That call is deliberately not routed through
a shared helper: the stage owns construction of its own client, so the model path
cannot silently degenerate into the deterministic one.

The deterministic counterpart of this stage lives in
``app/orchestrator/stages/deterministic/test_synthesis.py`` and is dispatched by the
seam only for DETERMINISTIC sessions.
"""

from typing import Any, Dict, Mapping, Optional, Tuple

from app.orchestrator.stages.runner import (
    ModelStageImplementation,
    extract_artifacts,
    render_stage_request,
)
from app.services.llm_factory import LLMFactory

STAGE = "TEST"

#: Stage-specific emphasis appended to the authored instruction.
STAGE_EMPHASIS = (
    "Derive one test per declared acceptance scenario rather than emitting a fixed set of method names. "
    "Use Spring Boot 3 and Java 21 standards with Mockito and MockMvc; do not import deprecated classes such as org.springframework.data.web.config.SpringDataWebAutoConfiguration."
)


def build_client(state: Mapping[str, Any], api_key: Optional[str] = None):
    """Construct this stage's chat model.

    This is part of the stage's request-construction path and is a direct
    ``LLMFactory.get_chat_model`` call: no wrapper, no conditional. Provider,
    model and key are taken from the session state so the stage cannot disagree
    with the mode that selected it.
    """
    return LLMFactory.get_chat_model(
        api_key=api_key if api_key is not None else state.get("llm_api_key"),
        provider=state.get("llm_provider"),
        model_name=state.get("llm_model"),
        temperature=0.2,
    )


def build_request(state: Mapping[str, Any], instruction: str) -> str:
    """Render the instruction plus the blueprint-derived payload for this stage."""
    return render_stage_request(state, STAGE, f"{instruction}\n\n## Stage emphasis\n{STAGE_EMPHASIS}")


def extract(
    response_text: str, state: Mapping[str, Any], instruction: str
) -> Tuple[Dict[str, str], bool]:
    """Map a raw response onto this stage's artifacts."""
    return extract_artifacts(response_text)


IMPLEMENTATION = ModelStageImplementation(
    stage=STAGE,
    build_request=build_request,
    extract=extract,
    build_client=build_client,
)

__test__ = False  # never collected as a test module
