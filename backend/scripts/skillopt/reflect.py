"""Reflect failures into a bounded edit set (FR-004 / T008).

One model call. The prompt is loaded from `prompts/analyst_error.md`, which records
that it is **adapted from Appendix C.2.1 (`analyst_error.md`) of
[arXiv:2605.23904](https://arxiv.org/abs/2605.23904)** and uses AgentIA's own
signals. It is not the paper's text and does not claim to be.

**The client comes from a direct call to the model factory**, in the same
request-construction path as the generation stages: no recording proxy, no shared
helper, no conditional. The recorder from feature 013 wraps a client only while a
recording context is active, and this module deliberately never establishes one —
a reflection call is not a generation call and must not appear in a session's cost
telemetry.

An unparseable response **raises**. A partially parsed edit set would be applied and
gated as though it were what the model proposed, which is worse than no proposal:
the run would report a decision about a candidate nobody asked for.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.services.llm_factory import LLMFactory
from app.skills.document import SkillDocument

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "analyst_error.md"

#: The edit budget, L_t. Shared with the applier so the two cannot drift.
from scripts.skillopt.apply import MAX_EDITS  # noqa: E402

_FENCED = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class ReflectError(RuntimeError):
    """The reflector could not produce a usable edit set."""


def _load_template() -> str:
    if not PROMPT_PATH.exists():
        raise ReflectError(f"reflector prompt not found: {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


def build_prompt(skill: SkillDocument, failures: Sequence[Dict[str, Any]],
                 max_edits: int = MAX_EDITS) -> str:
    """Fill the prompt template. Exposed so a test can assert what the model sees."""
    template = _load_template()
    return (
        template
        .replace("{{SKILL}}", skill.render().rstrip())
        .replace("{{FAILURES}}", json.dumps(list(failures), indent=2, sort_keys=True))
        .replace("{{MAX_EDITS}}", str(max_edits))
    )


def _extract_json_array(text: str) -> List[Any]:
    """Pull a JSON array out of the response, tolerating a fenced block."""
    candidates = []
    fenced = _FENCED.search(text)
    if fenced:
        candidates.append(fenced.group(1).strip())
    candidates.append(text.strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, list):
            return parsed
        # A dict wrapping the list is a common near-miss; accept only a single
        # obvious key rather than searching, so the shape stays predictable.
        if isinstance(parsed, dict):
            for key in ("edits", "edits_json", "proposals"):
                if isinstance(parsed.get(key), list):
                    return parsed[key]

    # Last resort: the outermost bracketed span.
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, list):
                return parsed
        except (TypeError, ValueError):
            pass

    raise ReflectError(
        "the reflector response contained no usable JSON array of edits. The "
        "iteration is failed rather than applying a partial parse."
    )


def _normalise(entries: Sequence[Any], max_edits: int) -> List[Dict[str, Any]]:
    """Keep the well-formed entries, drop the rest, and clip to the budget.

    Dropping a malformed entry rather than repairing it is deliberate: a repaired
    edit is no longer the edit the model proposed, so the logged set would not
    describe what was tested.
    """
    from scripts.skillopt.apply import OPERATIONS

    edits: List[Dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        op = entry.get("op")
        if op not in OPERATIONS:
            continue
        edit: Dict[str, Any] = {"op": op}
        if entry.get("target") is not None:
            edit["target"] = entry["target"]
        if entry.get("content") is not None:
            edit["content"] = entry["content"]
        edits.append(edit)
        if len(edits) >= max_edits:
            break
    return edits


def reflect(
    skill: SkillDocument,
    failures: Sequence[Dict[str, Any]],
    *,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    max_edits: int = MAX_EDITS,
) -> List[Dict[str, Any]]:
    """One model call: failures plus the current skill become at most `max_edits` edits.

    The client is obtained by a **direct** `LLMFactory.get_chat_model` call, in this
    function's request-construction path. No wrapper, no conditional.
    """
    if not failures:
        raise ReflectError("no failures to reflect on; the caller should not call a model")

    prompt = build_prompt(skill, failures, max_edits=max_edits)

    client = LLMFactory.get_chat_model(          # direct call -- no proxy, no helper
        api_key=api_key,
        provider=provider,
        model_name=model_name,
        temperature=0.2,
    )
    if client is None:
        raise ReflectError(
            "LLMFactory.get_chat_model returned no client; a reflection call needs a model"
        )

    response = client.invoke(prompt)
    text = getattr(response, "content", "")
    if isinstance(text, list):  # some clients return content blocks
        text = "".join(part.get("text", "") if isinstance(part, dict) else str(part)
                       for part in text)

    return _normalise(_extract_json_array(str(text)), max_edits)
