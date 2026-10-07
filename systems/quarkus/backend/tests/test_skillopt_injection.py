"""Skill injection tests (feature 014, T009 / US1).

The load-bearing assertion here is **SC-005**: with no active skill, the rendered
request must be byte-identical to the pre-feature rendering.

That is not a formality. The skills directory is currently empty apart from
placeholders, and injection is the first code to read it on the generation path. A
regression that appended a stray newline, or that raised when the pointer was
absent, would break every existing session — and it would do so silently, because
generation would still "work" while producing different requests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.orchestrator.stages import journal as journal_mod  # noqa: E402
from app.orchestrator.stages.runner import render_stage_request, run_stage  # noqa: E402
from app.skills import active as active_mod  # noqa: E402
from tests.fixtures import fake_model as fm  # noqa: E402

CORPUS_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "baseline_blueprints"

VALID_SKILL = """# Test Skill

## Granularity
task-level

## When to apply
Always, during tests.

## Rules
1. A distinctive rule that can be searched for: ZEBRA_MARKER.

<!-- SLOW_UPDATE_START -->
<!-- SLOW_UPDATE_END -->
"""


def _blueprint(name: str = "minimal") -> dict:
    return json.loads((CORPUS_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _state() -> dict:
    return {
        "session_id": "t009",
        "blueprint": _blueprint(),
        "workspace_path": "/tmp/does-not-matter",
        "generated_files": {},
        "logs": [],
        "generation_mode": journal_mod.GENERATION_MODE_MODEL,
        "llm_provider": "deepseek",
        "llm_model": "deepseek-flash",
        "llm_api_key": "sk-fake",
    }


@pytest.fixture
def skills_dir(tmp_path, monkeypatch):
    """Point the active pointer at a throwaway directory."""
    monkeypatch.setattr(active_mod, "ACTIVE_POINTER", tmp_path / "active.md")
    return tmp_path


def _render() -> str:
    return render_stage_request(_state(), "DOMAIN", "STAGE INSTRUCTION BODY")


# ---------------------------------------------------------------------------
# SC-005 — the regression guard
# ---------------------------------------------------------------------------
def test_no_active_pointer_is_byte_identical_to_the_pre_feature_rendering(skills_dir):
    """The request must be unchanged when nothing is active."""
    before = _render()

    # Activate a skill, then remove the pointer again.
    (skills_dir / "active.md").write_text("layer_architecture", encoding="utf-8")
    with_skill = _render()
    (skills_dir / "active.md").unlink()
    after = _render()

    assert with_skill != before, "the active skill had no effect on the request"
    assert after == before, (
        "removing the active pointer did not restore the original request "
        "byte-for-byte — injection is not a clean no-op"
    )


def test_an_empty_pointer_is_a_no_op(skills_dir):
    baseline = _render()
    (skills_dir / "active.md").write_text("", encoding="utf-8")
    assert _render() == baseline


def test_a_pointer_of_only_comments_is_a_no_op(skills_dir):
    baseline = _render()
    (skills_dir / "active.md").write_text("# no skill today\n\n", encoding="utf-8")
    assert _render() == baseline


def test_a_dangling_pointer_is_a_no_op_and_does_not_raise(skills_dir):
    baseline = _render()
    (skills_dir / "active.md").write_text("a-skill-that-does-not-exist", encoding="utf-8")
    assert _render() == baseline


def test_an_invalid_skill_document_is_a_no_op_rather_than_a_failure(skills_dir):
    """A malformed skill stops the skill being injected, not generation running."""
    baseline = _render()
    (skills_dir / "broken.md").write_text("# Broken\n\nno markers here\n", encoding="utf-8")
    (skills_dir / "active.md").write_text("broken", encoding="utf-8")
    assert _render() == baseline


# ---------------------------------------------------------------------------
# Injection actually happens
# ---------------------------------------------------------------------------
def test_the_active_skill_text_reaches_the_request(skills_dir):
    (skills_dir / "active.md").write_text("layer_architecture", encoding="utf-8")

    request = _render()

    assert "ZEBRA" not in request  # sanity: the marker is not in the seed
    assert "Layer Architecture" in request, "the active skill was not injected"
    assert "controller" in request.lower()


def test_injection_augments_the_instruction_rather_than_replacing_it(skills_dir):
    (skills_dir / "active.md").write_text("layer_architecture", encoding="utf-8")

    request = _render()

    assert "STAGE INSTRUCTION BODY" in request, "the stage instruction was replaced"
    assert "## Task payload" in request, "injection disturbed the payload section"
    assert "## Output paths you own" in request, "injection disturbed the scope section"


def test_injection_does_not_change_the_payload_or_the_scope(skills_dir):
    payload_before = _render().split("## Task payload", 1)[1]
    (skills_dir / "active.md").write_text("layer_architecture", encoding="utf-8")
    payload_after = _render().split("## Task payload", 1)[1]

    assert payload_before == payload_after, (
        "injection changed the payload or the owned-path scope"
    )


# ---------------------------------------------------------------------------
# Through the seam, end to end
# ---------------------------------------------------------------------------
def test_the_injected_skill_reaches_the_real_model_request(monkeypatch, tmp_path, skills_dir):
    """Injection is only real if the model actually receives it."""
    (skills_dir / "active.md").write_text("layer_architecture", encoding="utf-8")

    model = fm.make_scripted_model(
        fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", _blueprint()))
    )
    monkeypatch.setattr(
        "langchain_openai.ChatOpenAI", lambda **kwargs: model, raising=False
    )

    workspace = tmp_path / "ws"
    workspace.mkdir()
    state = _state()
    state["workspace_path"] = str(workspace)
    run_stage(state, "DOMAIN")

    assert model.calls, "no request reached the model"
    assert "Layer Architecture" in model.calls[0], (
        "the active skill did not reach the model request"
    )


def test_generation_still_runs_with_no_active_skill(monkeypatch, tmp_path, skills_dir):
    """The no-op path must still complete a stage, not merely avoid raising."""
    model = fm.make_scripted_model(
        fm.canonical_json_response(fm.compliant_artifacts("DOMAIN", _blueprint()))
    )
    monkeypatch.setattr(
        "langchain_openai.ChatOpenAI", lambda **kwargs: model, raising=False
    )

    workspace = tmp_path / "ws"
    workspace.mkdir()
    state = _state()
    state["workspace_path"] = str(workspace)
    result = run_stage(state, "DOMAIN")

    assert result.get("status") != "BLOCKED"
    assert "Layer Architecture" not in model.calls[0]
