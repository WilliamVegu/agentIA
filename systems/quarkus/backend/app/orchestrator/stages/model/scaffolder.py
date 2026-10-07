"""Model-driven scaffolder stage (task T028).

The stage's request-construction path calls ``LLMFactory.get_chat_model``
**directly** (see ``build_client``). That call is deliberately not routed through
a shared helper: the stage owns construction of its own client, so the model path
cannot silently degenerate into the deterministic one.

The deterministic counterpart of this stage lives in
``app/orchestrator/stages/deterministic/scaffolder.py`` and is dispatched by the
seam only for DETERMINISTIC sessions.
"""

import json
from typing import Any, Dict, Mapping, Optional, Tuple

from app.orchestrator.stages.compliance import load_dependency_allowlist
from app.orchestrator.stages.runner import (
    ModelStageImplementation,
    extract_artifacts,
    render_stage_request,
)
from app.services.llm_factory import LLMFactory

STAGE = "SCAFFOLDER"

#: Stage-specific emphasis appended to the authored instruction.
STAGE_EMPHASIS = (
    "Build configuration only. Every declared dependency MUST come from the allowlist below."
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
    """Render the instruction, payload, and the dependency allowlist.

    The allowlist is inlined because this stage is the only one that emits build
    configuration: an unlisted dependency cannot be resolved by the hermetic
    offline build, and the resulting failure can be swallowed by the verification
    environment's offline-cache fallback. The seam enforces the allowlist
    independently (compliance.check_dependency_allowlist, T049), so this is a
    hint that helps the model comply, not the enforcement itself.
    """
    allowlist = load_dependency_allowlist()
    permitted = json.dumps(
        {
            "parent": allowlist.get("parent"),
            "dependencies": allowlist.get("dependencies"),
            "build_plugins": allowlist.get("build_plugins"),
            "prohibited": allowlist.get("prohibited"),
        },
        indent=2,
        sort_keys=True,
    )
    return render_stage_request(
        state,
        STAGE,
        f"{instruction}\n\n## Stage emphasis\n{STAGE_EMPHASIS}\n\n"
        f"## Permitted dependencies (declare nothing outside this list)\n{permitted}",
    )


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
