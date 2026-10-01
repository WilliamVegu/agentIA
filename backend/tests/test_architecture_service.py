import pytest
import yaml
from app.models.requirements import SpecificationDraft
from app.models.blueprint import DomainEntity, EntityAttribute, UserStoryRecord, AcceptanceScenarioRecord
from app.models.architecture import (
    ArchitectureDesignRequest,
    ArchitectureRefinementRequest,
    ArchitectureDesignResponse,
    LayerType,
    HttpMethod,
)
from app.services.architecture_service import (
    design_architecture,
    refine_architecture,
    generate_mermaid_flowchart,
    serialize_to_openapi_yaml,
    serialize_architecture_markdown,
)

def create_mock_draft():
    return SpecificationDraft(
        serviceName="payment-service",
        packageName="com.corp.payment",
        basePort=8080,
        entities=[
            DomainEntity(
                name="Payment",
                tableName="payments",
                attributes=[
                    EntityAttribute(name="id", type="UUID", isPrimaryKey=True),
                    EntityAttribute(name="amount", type="BigDecimal", validationRules=["@Positive"]),
                ],
            )
        ],
        userStories=[
            UserStoryRecord(
                id="US-1",
                priority="P1",
                role="Customer",
                intent="process a payment",
                benefit="complete checkout",
                scenarios=[
                    AcceptanceScenarioRecord(
                        scenarioId="AC-1.1",
                        given="a customer with valid balance",
                        when="POST /payments is executed",
                        then="payment is approved and 201 is returned",
                    ),
                    AcceptanceScenarioRecord(
                        scenarioId="AC-1.2",
                        given="a card with insufficient funds",
                        when="POST /payments is executed",
                        then="error 400 is returned with details",
                    ),
                ],
            )
        ],
        assumptions=["Payments are idempotent"],
    )


def test_mock_key_refuses_to_fabricate_architecture():
    """The mock generator is removed: an offline/mock request must fail honestly,
    not fabricate an architecture."""
    draft = create_mock_draft()
    req = ArchitectureDesignRequest(draft=draft)
    with pytest.raises(RuntimeError):
        design_architecture(req, api_key="mock-key")


def test_no_client_refuses_to_fabricate_architecture(monkeypatch):
    """A missing model client must raise, not fall back to a fabricated design."""
    draft = create_mock_draft()
    req = ArchitectureDesignRequest(draft=draft)
    # a non-mock key forces the real path; monkeypatch get_chat_model to return None
    monkeypatch.setattr(
        "app.services.architecture_service.LLMFactory.get_chat_model", lambda **k: None
    )
    with pytest.raises(RuntimeError):
        design_architecture(req, api_key="sk-real-key")
