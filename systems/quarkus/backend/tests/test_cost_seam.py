"""Test-seam guardrail tests (feature 013, T018 / SC-009).

The recording wrapper wraps a client the model factory returns. Two ways that
could go wrong, both checked here:

* It could break the **fake-client seam** — the fixture the whole model-path suite
  depends on — or the pre-existing assertions about what the factory returns.
* It could be applied when recording is not active, which is exactly the condition
  that keeps production covered while leaving direct factory calls untouched.

The condition under test is **"is a recording context active"**, never **"is this
a test"**. A test-shaped condition would satisfy these tests while leaving every
production call unrecorded, which is why the through-the-seam recording case lives
in ``test_cost_recording.py`` and asserts a record actually lands.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.cost import recording  # noqa: E402
from app.cost.recording import RecordingChatClient  # noqa: E402
from app.services.llm_factory import LLMFactory  # noqa: E402
from tests.fixtures import fake_model as fm  # noqa: E402


def test_no_recording_context_means_no_wrapping(monkeypatch):
    """The factory returns exactly what it returned before, outside the seam.

    This is what keeps the pre-existing factory tests valid: they call the factory
    directly and assert on the concrete client type.
    """
    assert recording.is_recording_active() is False
    inner = fm.make_scripted_model("x")
    assert LLMFactory._maybe_wrap(inner, "deepseek", "deepseek-flash") is inner


def test_the_wrapping_condition_is_recording_not_test_presence():
    """The condition is the context, not whether code is running under pytest."""
    inner = fm.make_scripted_model("x")

    # Under pytest, with no context: unwrapped.
    assert LLMFactory._maybe_wrap(inner, "deepseek", "deepseek-flash") is inner

    # Under pytest, WITH a context: wrapped. A test-shaped condition would fail
    # this assertion, and would leave production unrecorded.
    with recording.recording_context("seam", "DOMAIN"):
        wrapped = LLMFactory._maybe_wrap(inner, "deepseek", "deepseek-flash")
    assert isinstance(wrapped, RecordingChatClient)


def test_a_real_factory_call_still_returns_the_concrete_provider_client(monkeypatch):
    """The seven ``isinstance`` assertions in ``test_llm_factory.py`` still hold.

    Exercised directly here rather than by importing that module, so this test
    states the same claim in one place: a direct factory call is not wrapped.
    """
    import langchain_openai

    sentinel = fm.make_scripted_model("x")
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", lambda **kwargs: sentinel)

    result = LLMFactory.get_chat_model(api_key="sk-x", provider="deepseek",
                                       model_name="deepseek-flash")

    assert result is sentinel, "a direct factory call was wrapped; the seam is not inert"
    assert not isinstance(result, RecordingChatClient)


def test_the_wrapper_delegates_attribute_access():
    """A wrapped test double must remain usable: ``calls``/``call_count`` resolve."""
    inner = fm.make_scripted_model("a", "b")
    with recording.recording_context("seam-attr", "DOMAIN"):
        wrapped = LLMFactory._maybe_wrap(inner, "deepseek", "deepseek-flash")

    wrapped.invoke("one")
    assert inner.calls == ["one"], "the wrapped client did not receive the request"
    assert wrapped.calls == ["one"], "attribute access was not delegated"
    assert wrapped.call_count == 1


def test_the_monkeypatched_fake_path_never_reaches_the_wrapper(monkeypatch):
    """The suite's dominant injection style replaces the factory outright.

    That path cannot be wrapped at all, so the fake seam is inert by construction
    rather than by a bypass someone has to remember to maintain.
    """
    fake = fm.make_scripted_model("z")
    monkeypatch.setattr(LLMFactory, "get_chat_model", staticmethod(lambda **kw: fake))

    with recording.recording_context("seam-fake", "DOMAIN"):
        result = LLMFactory.get_chat_model(api_key="sk-x", provider="deepseek")

    assert result is fake
    assert not isinstance(result, RecordingChatClient)
