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


# ---------------------------------------------------------------------------
# The other entrance: blueprint ingestion
# ---------------------------------------------------------------------------
NONSENSE_MARKDOWN = "# Feature Specification: mock-test\n\nque dia es hoy?\n"


def test_the_upload_entrance_no_longer_invents_a_domain():
    """Measured before the fix: uploading nonsense returned 201.

        {'entityCount': 1, 'storyCount': 1, 'isValid': True, 'validationWarnings': []}

    `parse_spec_markdown` fabricated entity `Resource` (`id`, `name`) and story `US-1`
    "manage resources" with the scenario "service is running / endpoint is called /
    returns successful response". Nothing in the document said any of that, so EVERY
    document produced a "valid" specification and the caller could not learn that their
    file was unreadable. That is why the round trip appeared to work.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.auth_service import COOKIE, _sessions, _lock
    import hashlib, time

    token = "test-token-spec-upload"
    digest = hashlib.sha256(token.encode()).hexdigest()
    with _lock:
        _sessions[digest] = (time.time() + 3600, {"email": "test@example.com", "name": "Tester", "role": "Architect"})

    client = TestClient(app, raise_server_exceptions=False, cookies={COOKIE: token})
    response = client.post(
        "/api/v1/specifications/upload",
        files={"file": ("spec.md", NONSENSE_MARKDOWN.encode(), "text/markdown")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "UNLIKELY_SPECIFICATION"


def test_the_parser_refuses_a_document_with_no_entities():
    """No fabrication: it says what it could not find."""
    from app.services.spec_service import parse_spec_markdown

    document = (
        "# Feature Specification: thing\n\n"
        "## User Scenarios & Testing\n\n"
        "### User Story 1 - do something (Priority: P1)\n\n"
        "Given a state, when it happens, then it works.\n"
    )

    with pytest.raises(ValueError) as refused:
        parse_spec_markdown(document)

    assert "No domain entities" in str(refused.value)


def test_the_parser_round_trips_the_layout_the_application_writes():
    """The least a generator can do is read its own output.

    It could not. The parser understood only `### Key Entities` with `- **Name**: ...`,
    while `lifecycle_artifacts` writes `## Domain Entities` with `### Name (`table`)` and
    `- `attr`: Type — PK, required`. Every upload of the app's own spec.md found no
    entities and fell through to the fabricated `Resource`.
    """
    from app.services.spec_service import parse_spec_markdown

    document = (
        "# Feature Specification: Help Desk\n\n"
        "**Feature Branch**: `help-desk`\n\n"
        "## User Scenarios & Testing *(mandatory)*\n\n"
        "### User Story 1 - register a customer (Priority: P1)\n\n"
        "Given a new customer, when they register, then an account exists.\n\n"
        "## Domain Entities\n\n"
        "### Customer (`customers`)\n\n"
        "- `id`: Long — PK, required\n"
        "- `email`: String — required\n"
        "- `nickname`: String — optional\n"
    )

    blueprint = parse_spec_markdown(document)

    assert [e.name for e in blueprint.entities] == ["Customer"]
    entity = blueprint.entities[0]
    assert entity.tableName == "customers"
    fields = {a.name: a for a in entity.attributes}
    assert fields["id"].isPrimaryKey is True
    assert fields["email"].nullable is False
    assert fields["nickname"].nullable is True
    assert [s.id for s in blueprint.userStories] == ["US-1"]


def test_the_bulleted_story_layout_is_read_not_fabricated():
    """A third layout, previously unread.

    An e2e test asserted ingestion worked while the parser found no stories and the
    fabricated `US-1 / manage resources` placeholder satisfied it.
    """
    from app.services.spec_service import parse_spec_markdown

    document = (
        "# Feature Specification: Order Service\n"
        "**Feature Branch**: `001-order-service`\n\n"
        "### Key Entities\n"
        "- **Order**: Represents a purchase order. id (Long), totalAmount (BigDecimal)\n\n"
        "### User Scenarios & Acceptance Criteria\n"
        "- **US-1**: As a Buyer, I want to create an order, so that I can buy items.\n"
        "  - **AC-1.1**: Given valid items, when POST /orders is called, then it is created.\n"
    )

    blueprint = parse_spec_markdown(document)
    story = blueprint.userStories[0]

    assert story.id == "US-1"
    assert story.role == "Buyer"
    assert story.intent == "create an order"
    assert story.benefit == "I can buy items"
    assert story.scenarios[0].given == "valid items"
    assert story.scenarios[0].when == "POST /orders is called"
    assert story.scenarios[0].then == "it is created"


@pytest.mark.parametrize("culinary_prompt", [
    "que me haga un ceviche",
    "hazme un ceviche",
    "prepara un ceviche",
    "quiero que me hagas un ceviche con pescado y limon",
    "cocinar un ceviche de mariscos",
    "# Feature Specification: servicio\n\nque me haga un ceviche",
    "make me a ceviche",
    "cook a ceviche for dinner",
])
def test_culinary_and_absurd_food_requests_are_refused(culinary_prompt):
    assessment = assess_specification(culinary_prompt)
    assert assessment.plausible is False
    assert assessment.signals["outOfScopeMatches"] > 0 or assessment.signals["domainTerms"] == 0


@pytest.mark.parametrize("creative_prompt", [
    "cuéntame un chiste",
    "escribe un poema",
    "tell me a joke",
    "write a poem about spring",
])
def test_entertainment_and_creative_requests_are_refused(creative_prompt):
    assessment = assess_specification(creative_prompt)
    assert assessment.plausible is False


def test_legitimate_restaurant_microservice_referencing_ceviche_is_allowed():
    text = (
        "Microservicio de restaurante para gestionar pedidos, "
        "clientes y catálogo de platos típicos como ceviches y bebidas."
    )
    assessment = assess_specification(text)
    assert assessment.plausible is True
    assert assessment.signals["domainTerms"] > 0


def test_quick_start_endpoint_blocks_ceviche_before_creating_session():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models.session import GenerationSessionDB, SessionLocal
    from app.services.auth_service import COOKIE, _sessions, _lock
    import hashlib, time

    token = "test-token-quick-start"
    digest = hashlib.sha256(token.encode()).hexdigest()
    with _lock:
        _sessions[digest] = (time.time() + 3600, {"email": "test@example.com", "name": "Tester", "role": "Architect"})

    client = TestClient(app, raise_server_exceptions=False, cookies={COOKIE: token})
    response = client.post(
        "/api/v1/sessions/quick-start",
        json={
            "serviceName": "servicio-absurdo",
            "prompt": "que me haga un ceviche",
            "autoRun": False,
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"] == "UNLIKELY_SPECIFICATION"
    assert "ceviche" in data["detail"]["message"].lower() or "ceviche" in str(data["detail"]).lower()

    # Verify no session was created in database
    db = SessionLocal()
    try:
        found = db.query(GenerationSessionDB).filter(
            GenerationSessionDB.spec_name == "servicio-absurdo"
        ).first()
        assert found is None, "A session must not be created for an out-of-scope request"
    finally:
        db.close()

