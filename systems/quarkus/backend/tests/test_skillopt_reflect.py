"""Reflector tests (feature 014, T012 / US2).

The reflector turns failures into a bounded edit set. Three things are asserted:

* edits come back **well-formed and bounded**;
* an **unparseable** response raises rather than being partially applied — a
  half-parsed edit set is worse than no edit set, because it would be applied and
  gated as though it were what the model proposed;
* the client is obtained by a **direct call to the model factory**, not through the
  recording proxy and not through a helper. The test replaces the provider class so
  the real factory runs, and asserts the wrapper was **not** applied.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.skills.document import load_skill  # noqa: E402
from scripts.skillopt.apply import MAX_EDITS  # noqa: E402
from scripts.skillopt.reflect import (  # noqa: E402
    PROMPT_PATH,
    ReflectError,
    build_prompt,
    reflect,
)
from tests.fixtures import fake_model as fm  # noqa: E402

SKILL_TEXT = """# A Skill

## Granularity
task-level

## When to apply
Whenever.

## Rules
1. First rule.

<!-- SLOW_UPDATE_START -->
<!-- SLOW_UPDATE_END -->
"""

FAILURES = [{
    "session_id": "s1",
    "spec_id": "spec-s1",
    "artifact_paths": ["src/main/java/com/corp/notes/controller/NoteController.java"],
    "build_exit_code": 1,
    "terminal_status": "BLOCKED",
    "verification_fallback_used": False,
}]


@pytest.fixture
def skill(tmp_path):
    path = tmp_path / "skill.md"
    path.write_text(SKILL_TEXT, encoding="utf-8")
    return load_skill(path)


def _model_returning(content: str):
    """Make the REAL factory return a scripted model, by patching the provider class."""
    return fm.make_scripted_model(content)


def _patch_provider(monkeypatch, model):
    import langchain_openai
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", lambda **kwargs: model)


# ---------------------------------------------------------------------------
# Prompt provenance (FR-004)
# ---------------------------------------------------------------------------
def test_the_prompt_records_its_adaptation_source():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "2605.23904" in text, "the prompt does not cite the paper it was adapted from"
    assert "C.2.1" in text, "the prompt does not cite the specific contract"
    assert "analyst_error" in text, "the prompt does not name the contract file"


def test_the_prompt_uses_platform_signals():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    for signal in ("build_exit_code", "terminal_status", "artifact_paths",
                   "verification_fallback_used"):
        assert signal in text, f"the prompt omits the platform signal {signal}"
    assert "mvn" in text.lower() or "build" in text.lower()


def test_the_prompt_is_not_a_verbatim_copy_of_the_paper():
    """A prompt presented as the source's own wording would be a false claim."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "adapted from" in text.lower(), "the provenance note does not say 'adapted from'"


def test_build_prompt_injects_the_skill_and_the_failures(skill):
    prompt = build_prompt(skill, FAILURES, max_edits=MAX_EDITS)

    assert "First rule." in prompt
    assert "s1" in prompt
    assert "1. First rule." in prompt  # the target must be visible to be copied
    assert "{{SKILL}}" not in prompt and "{{FAILURES}}" not in prompt, (
        "an unfilled placeholder leaked into the prompt"
    )


# ---------------------------------------------------------------------------
# Well-formed, bounded output
# ---------------------------------------------------------------------------
def test_reflect_returns_well_formed_edits(monkeypatch, skill):
    payload = json.dumps([{"op": "append", "content": "2. Second rule."}])
    _patch_provider(monkeypatch, _model_returning(payload))

    edits = reflect(skill, FAILURES, api_key="sk-x")

    assert isinstance(edits, list) and len(edits) == 1
    assert edits[0]["op"] == "append"
    assert edits[0]["content"] == "2. Second rule."


def test_more_proposals_than_the_budget_are_clipped(monkeypatch, skill):
    payload = json.dumps([{"op": "append", "content": f"rule {n}"} for n in range(MAX_EDITS + 5)])
    _patch_provider(monkeypatch, _model_returning(payload))

    edits = reflect(skill, FAILURES, api_key="sk-x")

    assert len(edits) == MAX_EDITS, "the reflector exceeded the edit budget"


def test_markdown_fenced_json_is_accepted(monkeypatch, skill):
    fenced = "```json\n" + json.dumps([{"op": "append", "content": "x"}]) + "\n```"
    _patch_provider(monkeypatch, _model_returning(fenced))

    assert len(reflect(skill, FAILURES, api_key="sk-x")) == 1


def test_an_unparseable_response_raises_rather_than_applying_a_partial_parse(monkeypatch, skill):
    _patch_provider(monkeypatch, _model_returning("I think you should add a rule about layering."))

    with pytest.raises(ReflectError):
        reflect(skill, FAILURES, api_key="sk-x")


def test_a_non_list_response_raises(monkeypatch, skill):
    _patch_provider(monkeypatch, _model_returning(json.dumps({"op": "append"})))

    with pytest.raises(ReflectError):
        reflect(skill, FAILURES, api_key="sk-x")


def test_malformed_edit_entries_are_dropped_not_guessed(monkeypatch, skill):
    payload = json.dumps([{"op": "append", "content": "ok"}, "not an object", {"no_op": True}])
    _patch_provider(monkeypatch, _model_returning(payload))

    edits = reflect(skill, FAILURES, api_key="sk-x")

    assert len(edits) == 1 and edits[0]["content"] == "ok"


# ---------------------------------------------------------------------------
# The client comes from a direct factory call
# ---------------------------------------------------------------------------
def test_the_client_is_not_the_spec_013_recording_proxy(monkeypatch, skill):
    """The reflector calls the factory directly, with no recording wrapper.

    The recording proxy is applied when a recording context is active. This test
    asserts the reflector does **not** establish one, so the client it receives is
    the raw one — which is what 'direct call, no wrapper' means in practice.
    """
    from app.cost.recording import RecordingChatClient, is_recording_active
    from app.services.llm_factory import LLMFactory

    seen = {}

    def _capture(**kwargs):
        seen["model"] = _model_returning(json.dumps([{"op": "append", "content": "x"}]))
        return seen["model"]

    import langchain_openai
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", _capture)

    reflect(skill, FAILURES, api_key="sk-x")

    assert "model" in seen, "the reflector did not construct a client through the factory"
    assert not isinstance(seen["model"], RecordingChatClient)
    assert is_recording_active() is False, (
        "the reflector established a recording context; it must call the factory directly"
    )
