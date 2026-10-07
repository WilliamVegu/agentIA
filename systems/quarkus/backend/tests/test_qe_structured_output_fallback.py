"""Structured output must survive a provider that rejects `response_format`.

Reported from the UI as "nothing is created after modo asistido is triggered", with
DeepSeek connected. The requirements transform returned 500 because DeepSeek answers
``with_structured_output`` with:

    400 - {'error': {'message': 'This response_format type is unavailable now'}}

so the story catalogue stayed at 0 and the pipeline had no draft to work from. Every
``with_structured_output`` call site was affected (transform, requirements refine,
architecture design, architecture refine) -- the whole guided flow -- while the
generation *stages* kept working, because they ask for JSON in the prompt text and
parse it themselves. That is the technique the fallback uses, so the fallback is the
mechanism already proven against this provider across 15 measured sessions.

The tests below care most about the **narrowness** of the trigger: a fallback that
fires on every error would convert a bad key or an outage into a confusing parse
error, which is worse than the original failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.structured_output import _extract_json_object, invoke_structured  # noqa: E402


class Payload(BaseModel):
    serviceName: str
    stories: int = 0


DEEPSEEK_400 = (
    "Error code: 400 - {'error': {'message': 'This response_format type is unavailable "
    "now (request_id: abc-123)', 'type': 'invalid_request_error', 'code': "
    "'invalid_request_error'}}"
)


class _Response:
    def __init__(self, content):
        self.content = content


class _FakeLLM:
    """Records how it was called and answers per configuration."""

    def __init__(self, *, structured_raises=None, text='{"serviceName": "x"}'):
        self.structured_raises = structured_raises
        self.text = text
        self.structured_called = False
        self.plain_called = False

    def with_structured_output(self, schema):
        self.structured_called = True
        outer = self

        class _Structured:
            def invoke(self, messages):
                if outer.structured_raises:
                    raise outer.structured_raises
                return schema(serviceName="x")

        return _Structured()

    def invoke(self, messages):
        self.plain_called = True
        self.last_messages = messages
        if isinstance(self.text, Exception):
            raise self.text
        return _Response(self.text)


def test_a_rejected_response_format_falls_back_to_prompt_json():
    llm = _FakeLLM(
        structured_raises=Exception(DEEPSEEK_400),
        text='{"serviceName": "helpdesk-service", "stories": 3}',
    )

    result = invoke_structured(llm, Payload, [{"role": "user", "content": "hi"}])

    assert isinstance(result, Payload)
    assert result.serviceName == "helpdesk-service"
    assert result.stories == 3
    assert llm.plain_called, "the fallback never made the prompt-based call"


def test_the_fallback_asks_for_the_schema_in_the_prompt():
    llm = _FakeLLM(structured_raises=Exception(DEEPSEEK_400))

    invoke_structured(llm, Payload, [{"role": "user", "content": "hi"}])

    instruction = llm.last_messages[-1].content
    assert "JSON" in instruction
    assert "serviceName" in instruction, "the schema was not sent to the model"
    assert "no markdown fences" in instruction.lower() or "No markdown fences" in instruction


@pytest.mark.parametrize(
    "text",
    [
        '{"serviceName": "a"}',
        '```json\n{"serviceName": "a"}\n```',
        "Here is the result:\n```\n{\"serviceName\": \"a\"}\n```\nHope that helps.",
        'Sure! {"serviceName": "a"} — done.',
    ],
)
def test_the_fallback_tolerates_the_encodings_a_model_actually_returns(text):
    llm = _FakeLLM(structured_raises=Exception(DEEPSEEK_400), text=text)

    assert invoke_structured(llm, Payload, []).serviceName == "a"


def test_an_unrelated_error_is_NOT_swallowed():
    """The trigger must name response_format, or a bad key becomes a parse error."""
    llm = _FakeLLM(structured_raises=Exception("Error code: 401 - invalid api key"))

    with pytest.raises(Exception) as excinfo:
        invoke_structured(llm, Payload, [])

    assert "401" in str(excinfo.value)
    assert not llm.plain_called, "an unrelated failure was retried as a prompt"


def test_an_outage_is_not_treated_as_an_unsupported_parameter():
    llm = _FakeLLM(structured_raises=Exception("Error code: 503 - service unavailable"))

    with pytest.raises(Exception):
        invoke_structured(llm, Payload, [])

    assert not llm.plain_called


def test_a_rate_limit_is_not_treated_as_an_unsupported_parameter():
    llm = _FakeLLM(structured_raises=Exception("Error code: 429 - rate limit exceeded"))

    with pytest.raises(Exception):
        invoke_structured(llm, Payload, [])

    assert not llm.plain_called


def test_a_native_success_never_reaches_the_fallback():
    llm = _FakeLLM()

    assert invoke_structured(llm, Payload, []).serviceName == "x"
    assert not llm.plain_called


def test_an_empty_response_is_an_error_not_an_empty_object():
    llm = _FakeLLM(structured_raises=Exception(DEEPSEEK_400), text="")

    with pytest.raises(ValueError, match="empty response"):
        invoke_structured(llm, Payload, [])


def test_a_response_with_no_json_is_an_error():
    llm = _FakeLLM(structured_raises=Exception(DEEPSEEK_400), text="I cannot help with that.")

    with pytest.raises(ValueError, match="no JSON object"):
        invoke_structured(llm, Payload, [])


def test_json_that_does_not_match_the_schema_is_rejected():
    """A well-formed object of the wrong shape must not be accepted."""
    llm = _FakeLLM(structured_raises=Exception(DEEPSEEK_400), text='{"wrong": "shape"}')

    with pytest.raises(Exception):
        invoke_structured(llm, Payload, [])


def test_extract_handles_a_nested_object_with_braces_in_strings():
    data = _extract_json_object('prefix {"a": {"b": "}"}, "c": 1} suffix')

    assert data == {"a": {"b": "}"}, "c": 1}


# ---------------------------------------------------------------------------
# The real services must use it
# ---------------------------------------------------------------------------
def test_no_service_calls_with_structured_output_directly():
    """Pins the fix at every call site, not just in the helper.

    The bug was not that the helper was missing; it was that four services asked for
    structured output directly, so a provider that refuses the parameter broke them
    all. A new call site added later must go through `invoke_structured`.
    """
    offenders = []
    for path in (REPO_ROOT / "backend/app").rglob("*.py"):
        if path.name == "structured_output.py":
            continue
        if "with_structured_output" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert not offenders, (
        f"these modules bypass the provider-compatibility fallback: {offenders}"
    )


def test_the_requirements_transform_works_against_a_provider_that_rejects_the_parameter(
    monkeypatch,
):
    """End to end through the service the UI calls, with the 400 simulated."""
    from app.models.requirements import RequirementsTransformRequest
    from app.services import requirements_service as rs

    real_get = rs.LLMFactory.get_chat_model

    def fake_get(api_key=None, provider=None, model_name=None, **kwargs):
        return _FakeLLM(
            structured_raises=Exception(DEEPSEEK_400),
            # Built rather than hand-written: the schema requires at least three
            # stories, each with at least two scenarios, and a tableName per entity.
            # Hand-written JSON drifted from those rules twice while writing this.
            text=json.dumps({
                "serviceName": "helpdesk-service",
                "packageName": "com.corp.helpdesk",
                "assumptions": ["the service is stateless"],
                "entities": [{
                    "name": "Ticket", "tableName": "tickets",
                    "attributes": [{"name": "id", "type": "Long", "isPrimaryKey": True}],
                }],
                "userStories": [
                    {
                        "id": f"US-{n}", "priority": "P1", "role": "support agent",
                        "intent": f"open a ticket {n}", "benefit": "track work",
                        "scenarios": [
                            {"scenarioId": f"AC-{n}.1", "given": "an existing customer",
                             "when": "a ticket is opened", "then": "it is stored"},
                            {"scenarioId": f"AC-{n}.2", "given": "an unknown customer",
                             "when": "a ticket is opened", "then": "it is rejected"},
                        ],
                    }
                    for n in (1, 2, 3)
                ],
            }),
        )

    monkeypatch.setattr(rs.LLMFactory, "get_chat_model", fake_get)
    monkeypatch.setattr(rs.LLMFactory, "is_mock", staticmethod(lambda *a, **k: False))

    draft = rs.transform_requirements(
        RequirementsTransformRequest(
            serviceName="helpdesk-service", rawText="A helpdesk service.", provider="deepseek",
        ),
        api_key="sk-not-a-real-key",
        provider="deepseek",
    )

    assert draft.userStories, "the transform produced no stories against a rejecting provider"
    assert draft.userStories[0].intent == "open a ticket 1"
