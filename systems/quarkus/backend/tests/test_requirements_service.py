import pytest
from app.models.requirements import (
    RequirementsTransformRequest,
    RefinementRequest,
    SpecificationDraft,
)
from app.models.blueprint import (
    DomainEntity,
    EntityAttribute,
    UserStoryRecord,
    AcceptanceScenarioRecord,
)
from app.services.requirements_service import (
    transform_requirements,
    refine_specification,
    serialize_draft_to_markdown,
)
from app.services.spec_service import parse_spec_markdown

def test_transform_requirements_mock_mode():
    req = RequirementsTransformRequest(
        rawText="Quiero un servicio para gestionar facturas con cliente, total y estado de pago.",
        serviceName="billing-service",
        packageName="com.corp.billing",
    )
    draft = transform_requirements(req, api_key="mock-key")
    assert isinstance(draft, SpecificationDraft)
    assert draft.serviceName == "billing-service"
    assert draft.packageName == "com.corp.billing"
    assert len(draft.userStories) >= 3

    # Constitution Principle V: >= 2 scenarios per story
    for story in draft.userStories:
        assert len(story.scenarios) >= 2
        assert any("valid" in sc.given.lower() or "active" in sc.given.lower() for sc in story.scenarios)
        assert any("reject" in sc.then.lower() or "error" in sc.then.lower() or "400" in sc.then for sc in story.scenarios)

def test_entity_extraction_types_and_primary_key():
    req = RequirementsTransformRequest(
        rawText="Gestionar pagos con ID UUID, monto en BigDecimal y fecha de transacción.",
        serviceName="payment-service",
    )
    draft = transform_requirements(req, api_key="mock-key")
    assert len(draft.entities) >= 1
    entity = draft.entities[0]
    # Verify primary key is designated
    pk_attrs = [a for a in entity.attributes if a.isPrimaryKey]
    assert len(pk_attrs) >= 1
    # Verify attribute types
    types = [a.type for a in entity.attributes]
    assert any(t in ("UUID", "Long", "String", "BigDecimal") for t in types)

def test_markdown_serialization_spec_kit_compatibility():
    draft = SpecificationDraft(
        serviceName="customer-service",
        packageName="com.corp.customer",
        basePort=8085,
        entities=[
            DomainEntity(
                name="Customer",
                tableName="customers",
                attributes=[
                    EntityAttribute(name="id", type="UUID", isPrimaryKey=True),
                    EntityAttribute(name="email", type="String", validationRules=["@NotBlank", "@Email"]),
                ],
            )
        ],
        userStories=[
            UserStoryRecord(
                id="US-1",
                priority="P1",
                role="User",
                intent="register an account",
                benefit="access the platform",
                scenarios=[
                    AcceptanceScenarioRecord(
                        scenarioId="AC-1.1",
                        given="a new user with unique email",
                        when="registration form is submitted",
                        then="customer profile is created and 201 is returned",
                    ),
                    AcceptanceScenarioRecord(
                        scenarioId="AC-1.2",
                        given="an existing email address",
                        when="registration form is submitted",
                        then="system rejects with 409 Conflict",
                    ),
                ],
            )
        ],
        assumptions=["Email verification required within 24 hours."],
    )
    md = serialize_draft_to_markdown(draft)
    assert "# Feature Specification: Customer Service" in md
    assert "**Feature Branch**: `customer-service`" in md
    assert "### Key Entities" in md
    assert "**Customer**" in md
    assert "### User Story 1 - register an account (Priority: P1)" in md

    # Verify that spec_service.py can successfully parse this generated markdown
    blueprint = parse_spec_markdown(md)
    assert blueprint.serviceName == "customer-service"
    assert len(blueprint.entities) >= 1
    assert len(blueprint.userStories) >= 1
    assert len(blueprint.userStories[0].scenarios) >= 2

def test_refine_specification_mock_mode():
    initial_draft = SpecificationDraft(
        serviceName="order-service",
        packageName="com.corp.order",
        basePort=8080,
        entities=[
            DomainEntity(
                name="Order",
                tableName="orders",
                attributes=[EntityAttribute(name="id", type="UUID", isPrimaryKey=True)],
            )
        ],
        userStories=[
            UserStoryRecord(
                id="US-1",
                priority="P1",
                role="Shopper",
                intent="place order",
                benefit="get goods",
                scenarios=[
                    AcceptanceScenarioRecord(
                        scenarioId="AC-1.1",
                        given="cart is full",
                        when="checkout clicked",
                        then="order created",
                    ),
                    AcceptanceScenarioRecord(
                        scenarioId="AC-1.2",
                        given="card declined",
                        when="checkout clicked",
                        then="error shown",
                    ),
                ],
            )
        ],
        assumptions=[],
    )
    refine_req = RefinementRequest(
        currentDraft=initial_draft,
        feedbackPrompt="Agregar validación cuando no hay stock",
        apiKey="mock-key",
    )
    refined = refine_specification(refine_req, api_key="mock-key")
    assert len(refined.userStories[0].scenarios) == 3
    assert refined.markdownSpec != ""

