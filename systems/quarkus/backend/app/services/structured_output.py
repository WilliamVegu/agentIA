"""Structured output that survives providers which do not support it.

Feature 011's services ask for structured output via
``llm.with_structured_output(Schema)``, which LangChain implements as a
``response_format`` JSON-schema request. **DeepSeek rejects that**:

    400 - {'error': {'message': 'This response_format type is unavailable now'}}

Reported from the UI as "nothing is created after modo asistido is triggered": the
requirements transform 500s, the story catalogue stays at 0, and the pipeline has no
draft to work from. The generation *stages* were never affected because they ask for
JSON in the prompt text and parse it themselves (``render_stage_request`` /
``extract_artifacts``) -- which is exactly the technique this module falls back to, so
the fallback is the mechanism already proven to work with this provider across 15
measured sessions.

A fallback is only correct if it is narrow. Falling back on every error would turn a
genuine API failure (bad key, rate limit, outage) into a confusing parse error, so the
trigger is specifically a rejection of the ``response_format`` parameter. Anything else
propagates unchanged.
"""

from __future__ import annotations

import json
import re
from typing import Any, List, Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_FENCED = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _looks_like_unsupported_response_format(exc: Exception) -> bool:
    """Whether the provider refused the ``response_format`` parameter itself.

    Narrow on purpose: the message must name the parameter. A generic 400 (bad model,
    malformed request) must not be silently retried as a prompt -- that would hide the
    real fault behind a JSON parse error.
    """
    text = str(exc).lower()
    return "response_format" in text or "response format" in text


def _extract_json_object(text: str) -> Any:
    """Pull a JSON object out of a model response, tolerating fences and prose."""
    candidate = (text or "").strip()
    if not candidate:
        raise ValueError("the model returned an empty response")

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    fenced = _FENCED.search(candidate)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        return json.loads(candidate[start:end + 1])

    raise ValueError(f"no JSON object found in the response: {candidate[:200]!r}")


def invoke_structured(
    llm: Any,
    schema: Type[T],
    messages: List[Any],
    *,
    provider: Optional[str] = None,
) -> T:
    """Invoke ``llm`` for a ``schema``-shaped result, falling back to prompt-JSON.

    ``provider`` is only used in the error message; the decision is made from the
    provider's own response, not from a hardcoded list of which providers support
    structured output. A capability list would go stale silently -- someone would add
    a provider, generation would 400 on every call, and nothing would say why.
    """
    try:
        return llm.with_structured_output(schema).invoke(messages)
    except Exception as exc:  # noqa: BLE001 -- re-raised unless the trigger matches
        if not _looks_like_unsupported_response_format(exc):
            raise

    # The provider refused response_format. Ask for the same shape in the prompt, the
    # way the generation stages already do.
    from langchain_core.messages import HumanMessage

    instruction = (
        "Return ONLY a single JSON object conforming to this JSON Schema. "
        "No prose and no markdown fences.\n\n"
        + json.dumps(schema.model_json_schema(), indent=2)
    )
    response = llm.invoke(list(messages) + [HumanMessage(content=instruction)])
    text = getattr(response, "content", None)
    if not isinstance(text, str):
        text = str(response)
    return schema.model_validate(_extract_json_object(text))
