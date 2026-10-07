"""Tests for the LLM injection judge (second guard layer)."""
import pytest

from app.services.injection_judge import (
    InjectionVerdict,
    JudgeRefusal,
    is_blocking,
    judge_text,
    parse_verdict,
)


class _FakeClient:
    def __init__(self, content: str):
        self.content = content

    def invoke(self, _prompt):
        class _Resp:
            content = self.content
        return _Resp()


def test_parse_verdict_plain_json():
    v = parse_verdict('{"verdict": "injection", "confidence": 0.95, "reason": "override"}')
    assert v.verdict == "injection"
    assert v.confidence == 0.95


def test_parse_verdict_fenced_json():
    v = parse_verdict('```json\n{"verdict": "benign", "confidence": 0.1, "reason": "x"}\n```')
    assert v.verdict == "benign"


def test_parse_verdict_prose_refuses():
    with pytest.raises(JudgeRefusal):
        parse_verdict("I think this is fine, no JSON here.")


def test_parse_verdict_wrong_shape_refuses():
    with pytest.raises(JudgeRefusal):
        parse_verdict('{"verdict": "injection"}')  # missing confidence


def test_judge_text_constrains_output():
    client = _FakeClient('{"verdict": "suspicious", "confidence": 0.5, "reason": "ambiguous"}')
    v = judge_text("some untrusted text", client)
    assert isinstance(v, InjectionVerdict)
    assert v.verdict == "suspicious"


def test_judge_unparseable_refuses():
    client = _FakeClient("free prose, no verdict")
    with pytest.raises(JudgeRefusal):
        judge_text("x", client)


def test_is_blocking_threshold():
    assert is_blocking(InjectionVerdict(verdict="injection", confidence=0.9, reason="r")) is True
    assert is_blocking(InjectionVerdict(verdict="injection", confidence=0.5, reason="r")) is False
    assert is_blocking(InjectionVerdict(verdict="suspicious", confidence=0.99, reason="r")) is False
