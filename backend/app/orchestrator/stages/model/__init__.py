"""Model-driven generation stages (tasks T024-T028).

Each module owns one stage: its own direct ``LLMFactory.get_chat_model`` call, its
request construction, and its response extraction. The seam dispatches to these
implementations only for ``MODEL`` sessions; ``DETERMINISTIC`` sessions continue
to use ``app/orchestrator/stages/deterministic/``.

Registration is set-if-absent, so an implementation registered explicitly (by a
test, or a future override) is never clobbered by these built-ins.
"""

from app.orchestrator.stages.model import (  # noqa: F401
    controller,
    domain,
    scaffolder,
    service,
    test as test_synthesis,
)
from app.orchestrator.stages.runner import MODEL_STAGE_IMPLEMENTATIONS

#: Declaration order mirrors the execution order; T028 (scaffolder) is last in the
#: migration order but first in execution, which matters only for readability here.
_MODULES = (scaffolder, domain, service, controller, test_synthesis)


def register_all_model_stages() -> None:
    """Register the five built-in model stages, without overwriting overrides."""
    for module in _MODULES:
        MODEL_STAGE_IMPLEMENTATIONS.setdefault(module.STAGE, module.IMPLEMENTATION)
