import pytest
from pydantic import ValidationError
from app.services.spec_service import parse_spec_markdown, validate_blueprint
from app.models.blueprint import ArchitectureBlueprint, DomainEntity, EntityAttribute, UserStoryRecord, AcceptanceScenarioRecord

SAMPLE_SPEC_MARKDOWN = """
# Feature Specification: Order Service

**Feature Branch**: `001-order-service`

## Requirements
### Key Entities
- **Order**: Represents a customer order. Attributes: id (UUID, PK), customerEmail (String, @NotBlank), totalAmount (BigDecimal, @Positive).

### User Scenarios & Testing
### User Story 1 - Create Order (Priority: P1)
As a Customer, I want to place an order, so that I receive my goods.
1. **Given** valid cart items, **When** order is placed, **Then** order is saved with status PENDING.
"""

def test_parse_spec_markdown_success():
    blueprint = parse_spec_markdown(SAMPLE_SPEC_MARKDOWN)
    assert blueprint.serviceName == "order-service"
    assert len(blueprint.entities) >= 1
    assert len(blueprint.userStories) >= 1
    assert blueprint.userStories[0].scenarios[0].given == "valid cart items"

def test_validate_blueprint_missing_scenarios_raises_error():
    with pytest.raises(ValidationError) as exc:
        UserStoryRecord(
            id="US-1",
            priority="P1",
            role="Customer",
            intent="buy",
            benefit="have item",
            scenarios=[]
        )
    assert "List should have at least 1 item" in str(exc.value)

def test_validate_blueprint_missing_primary_key_raises_error():
    entity_no_pk = DomainEntity(
        name="NoPkEntity",
        tableName="no_pks",
        attributes=[EntityAttribute(name="title", type="String")]
    )
    story = UserStoryRecord(
        id="US-1",
        priority="P1",
        role="Admin",
        intent="test",
        benefit="test",
        scenarios=[
            AcceptanceScenarioRecord(scenarioId="AC-1.1", given="state", when="action", then="result")
        ]
    )
    blueprint = ArchitectureBlueprint(
        serviceName="test-service",
        packageName="com.corp.test",
        entities=[entity_no_pk],
        userStories=[story]
    )
    with pytest.raises(ValueError) as exc:
        validate_blueprint(blueprint)
    assert "must have at least one primary key attribute" in str(exc.value)

