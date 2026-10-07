"""Test node — delegates to the stage execution boundary.

The original f-string implementation moved **verbatim** to
``app/orchestrator/stages/deterministic/test_synthesis.py`` in T020. That module
holds the emit logic unchanged; this module preserves the node's external
contract:

* the function name and signature,
* the return value,
* the files written to disk,
* the state keys it sets.

The constraint satisfied here is **behavioural equivalence, not byte identity**:
for identical input this node produces identical output, identical disk writes
and identical state. That equivalence is what keeps the frozen pre-migration
baseline a valid comparison target (T021 asserts it end to end).
"""

from typing import Any, Dict

from app.orchestrator.state import GenerationAgentState
from app.orchestrator.stages.runner import run_stage, with_session_generation_mode

__test__ = False  # keep pytest from collecting this module as a test

def test_node(state: GenerationAgentState) -> Dict[str, Any]:
    """Run the TEST stage through the seam.

    This function is a **caller boundary**: when a caller invokes it directly the
    state carries no generation mode yet, so the mode is computed here exactly as
    the graph entry computes it. The seam itself still refuses to default an
    absent mode — that refusal is deliberate and must not be moved into the seam.
    """
    return run_stage(with_session_generation_mode(state), "TEST")
