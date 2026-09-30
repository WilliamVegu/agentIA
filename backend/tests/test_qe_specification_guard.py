"""Is the input a specification at all?

Separate from `injection_guard`, which answers a different question and correctly found
nothing wrong with the case that prompted this:

    # Feature Specification: mock-test

    que dia es hoy?

Nothing there is an attack. It is simply not a specification, and the pipeline designed a
domain around it -- three entities (`DateInquiry`, `CalendarDay`, `AuditEvent`), a
persistence model, and two BDD stories about resolving "the current date" through an
inquiry table. Model calls were spent, artifacts were written, and the output looked like a
result. Asked a question, the system produced an API.
"""
import pytest

from app.services.requirements_service import transform_requirements
from app.services.specification_guard import (
    MIN_WORDS,
    UnlikelySpecificationError,
    assess_specification,
    assert_looks_like_specification,
)

#: The exact input from the report.
REPORTED = "# Feature Specification: mock-test\n\nque dia es hoy?"


def test_the_reported_input_is_refused():
    assessment = assess_specification(REPORTED)

    assert assessment.plausible is False
    assert assessment.signals["domainTerms"] == 0
    assert assessment.signals["readsAsQuestion"] == 1


def test_a_title_alone_does_not_make_something_a_specification():
    """The gate's first version counted `#` as structure and was defeated by this.

    A heading is a label. Enumerated content -- bullets, acceptance criteria -- is
    structure, and only that counts.
    """
    assert assess_specification("# Feature Specification: mock-test").plausible is False
    assert assess_specification(REPORTED).plausible is False


@pytest.mark.parametrize("text", [
    "que dia es hoy?",
    "¿Qué día es hoy?",
    "What is the weather today?",
    "hola",
    "hi there",
    "",
    "   ",
])
def test_conversation_is_refused(text):
    assert assess_specification(text).plausible is False


@pytest.mark.parametrize("text", [
    # Terse but unmistakably a request for a service.
    "Customer CRUD with email and tier",
    "Un servicio para gestionar tickets de soporte con CRUD completo",
    # Explicit.
    "A REST API to manage orders, with create, read, update and delete operations",
    # Spanish prose, no markdown.
    "Necesito que los usuarios puedan registrar pedidos y consultar su estado",
    # Structured.
    "# Feature Specification: help-desk\n\n- Customer\n- Ticket\n",
    "GIVEN a customer WHEN they register THEN an account is created",
])
def test_real_specifications_are_never_blocked(text):
    """A false block stops work; a false allow wastes a model call. Bias to the former."""
    assert assess_specification(text).plausible is True


def test_a_long_question_without_domain_words_is_allowed():
    """Documented limit: this is a plausibility heuristic, not comprehension.

    Past the length floor the gate stops guessing, because a verbose specification written
    as prose -- legitimate and common -- looks the same by every signal it can read.
    """
    text = "I would like to know what day it is today because I always forget and need to check quickly"
    assert len(text.split()) > MIN_WORDS
    assert assess_specification(text).plausible is True


def test_the_refusal_names_what_was_missing():
    """The caller asked a question; the message must not read as a refusal of their work."""
    assessment = assess_specification(REPORTED)

    joined = " ".join(assessment.reasons)
    assert "question" in joined
    assert "no entities" in joined or "names no entities" in joined


def test_the_error_carries_a_structured_envelope():
    with pytest.raises(UnlikelySpecificationError) as raised:
        assert_looks_like_specification(REPORTED)

    payload = raised.value.to_dict()
    assert payload["error"] == "UNLIKELY_SPECIFICATION"
    assert payload["field"] == "rawText"
    assert isinstance(payload["signals"], dict)


def test_the_guard_runs_before_anything_else_happens(monkeypatch):
    """The point is to not spend a call and not write artifacts.

    Both downstream entry points are made to explode, so this proves the gate precedes
    whichever one would have run. Patching only `invoke_structured` would not: the mock
    provider never reaches it, and the test would pass while proving nothing.
    """
    from app.models.requirements import RequirementsTransformRequest
    from app.services import requirements_service

    def _explode(*args, **kwargs):  # pragma: no cover - only runs if the gate is late
        raise AssertionError("work started for input that is not a specification")

    monkeypatch.setattr(requirements_service, "invoke_structured", _explode, raising=False)
    monkeypatch.setattr(
        requirements_service, "_generate_mock_decomposition", _explode, raising=False
    )

    request = RequirementsTransformRequest(rawText=REPORTED, serviceName="mock-test")
    with pytest.raises(UnlikelySpecificationError):
        transform_requirements(request, "unused-key", provider="mock")
