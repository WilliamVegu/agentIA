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

def test_architecture_synthesis_strict_layering_and_aggregates():
    draft = create_mock_draft()
    req = ArchitectureDesignRequest(draft=draft)
    design = design_architecture(req, api_key="mock-key")

    assert isinstance(design, ArchitectureDesignResponse)
    assert design.serviceName == "payment-service"
    assert design.packageName == "com.corp.payment"

    # Verify component catalog contains aggregate components
    comp_names = [c.name for c in design.components]
    assert "PaymentController" in comp_names
    assert "PaymentService" in comp_names
    assert "PaymentRepository" in comp_names
    assert "Payment" in comp_names
    assert "GlobalExceptionHandler" in comp_names

    # Verify layers
    layers = {c.layer for c in design.components}
    assert LayerType.CONTROLLER in layers
    assert LayerType.SERVICE in layers
    assert LayerType.REPOSITORY in layers
    assert LayerType.MODEL in layers
    assert LayerType.INFRASTRUCTURE in layers

    # Verify unidirectional dependencies
    controller = next(c for c in design.components if c.name == "PaymentController")
    assert "PaymentService" in controller.dependencies
    assert "PaymentRepository" not in controller.dependencies  # Prohibited direct access

def test_endpoint_derivation_from_scenarios():
    draft = create_mock_draft()
    req = ArchitectureDesignRequest(draft=draft)
    design = design_architecture(req, api_key="mock-key")

    assert len(design.endpoints) >= 2
    post_ep = next(e for e in design.endpoints if e.method == HttpMethod.POST)
    assert post_ep.path == "/api/v1/payments"
    assert post_ep.requestDto == "CreatePaymentRequest"
    assert post_ep.responseDto == "PaymentResponse"
    assert post_ep.successStatus == 201
    assert 400 in post_ep.errorStatuses

    get_ep = next(e for e in design.endpoints if e.method == HttpMethod.GET)
    assert get_ep.path == "/api/v1/payments/{id}"
    assert get_ep.successStatus == 200

def test_openapi_yaml_serialization_validity():
    draft = create_mock_draft()
    req = ArchitectureDesignRequest(draft=draft)
    design = design_architecture(req, api_key="mock-key")

    yaml_str = design.openapiYaml
    assert yaml_str != ""
    doc = yaml.safe_load(yaml_str)
    assert doc["openapi"] == "3.0.3"
    assert "Payment Service API" in doc["info"]["title"]
    assert "/api/v1/payments" in doc["paths"]
    assert "ProblemDetails" in doc["components"]["schemas"]
    assert "CreatePaymentRequest" in doc["components"]["schemas"]
    assert "PaymentResponse" in doc["components"]["schemas"]

def test_mermaid_flowchart_generation():
    draft = create_mock_draft()
    req = ArchitectureDesignRequest(draft=draft)
    design = design_architecture(req, api_key="mock-key")

    mermaid = design.mermaidDiagram
    assert "flowchart TD" in mermaid
    assert "subgraph Presentation" in mermaid
    assert "subgraph Business" in mermaid
    assert "subgraph Persistence" in mermaid
    assert "subgraph Domain" in mermaid
    assert "subgraph Infrastructure" in mermaid
    assert "PaymentController --> PaymentService" in mermaid
    assert "PaymentService --> PaymentRepository" in mermaid

def test_refine_architecture_logic():
    draft = create_mock_draft()
    initial_design = design_architecture(ArchitectureDesignRequest(draft=draft), api_key="mock-key")
    initial_count = len(initial_design.components)

    refine_req = ArchitectureRefinementRequest(
        currentDesign=initial_design,
        feedbackPrompt="Añadir un componente de auditoría para registrar cada transacción",
        apiKey="mock-key",
    )
    refined = refine_architecture(refine_req, api_key="mock-key")
    assert len(refined.components) > initial_count
    assert any("Audit" in c.name for c in refined.components)
    assert "AuditNotificationService" in refined.mermaidDiagram

def test_design_architecture_fallback_on_503_unavailable(monkeypatch):
    from unittest.mock import MagicMock
    from app.services.llm_factory import LLMFactory

    # Mock LLM to throw 503 UNAVAILABLE
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.side_effect = Exception(
        "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
    )
    mock_llm.with_structured_output.return_value = mock_structured
    monkeypatch.setattr(LLMFactory, "get_chat_model", lambda **kwargs: mock_llm)
    monkeypatch.setattr(LLMFactory, "is_mock", lambda *args, **kwargs: False)

    draft = create_mock_draft()
    req = ArchitectureDesignRequest(draft=draft, provider="gemini")
    design = design_architecture(req, api_key="real-gemini-key")

    assert design is not None
    assert design.serviceName == "payment-service"
    assert len(design.components) >= 4
    assert any(c.name == "PaymentController" for c in design.components)
    assert any(c.stereotype == "PanacheRepository" for c in design.components)

def test_sanitize_quarkus_components_eradicates_spring_and_cycles():
    from app.models.architecture import ComponentDefinition, LayerType
    from app.services.architecture_service import sanitize_quarkus_components

    # Contaminated component list with Spring stereotypes, mentions, and circular dependencies
    dirty_comps = [
        ComponentDefinition(
            name="OrderController",
            layer=LayerType.CONTROLLER,
            stereotype="@RestController",
            packageName="com.corp.order.controller",
            responsibilities=["Endpoints Spring MVC y enrutamiento"],
            dependencies=["OrderService", "OrderRepository"],  # Direct repo dependency must be pruned
        ),
        ComponentDefinition(
            name="OrderService",
            layer=LayerType.SERVICE,
            stereotype="@Service",
            packageName="com.corp.order.service",
            responsibilities=["Lógica con Spring Data JPA"],
            dependencies=["OrderRepository", "OrderController"],  # Upward dependency to controller must be pruned
        ),
        ComponentDefinition(
            name="OrderRepository",
            layer=LayerType.REPOSITORY,
            stereotype="@Repository",
            packageName="com.corp.order.repository",
            responsibilities=["Persistencia Spring Data"],
            dependencies=["Order", "OrderService"],  # Circular dependency to Service must be pruned
        ),
        ComponentDefinition(
            name="Order",
            layer=LayerType.MODEL,
            stereotype="@Entity",
            packageName="com.corp.order.model",
            responsibilities=["Entidad JPA"],
            dependencies=["OrderRepository"],  # Model cannot depend on repository
        ),
        ComponentDefinition(
            name="GlobalExceptionHandler",
            layer=LayerType.INFRASTRUCTURE,
            stereotype="@RestControllerAdvice",
            packageName="com.corp.order.infra",
            responsibilities=["Manejo centralizado @RestControllerAdvice"],
            dependencies=[],
        ),
    ]

    cleaned = sanitize_quarkus_components(dirty_comps)
    cleaned_map = {c.name: c for c in cleaned}

    # Verify Quarkus stereotypes
    assert cleaned_map["OrderController"].stereotype == "@Path"
    assert cleaned_map["OrderService"].stereotype == "@ApplicationScoped"
    assert cleaned_map["OrderRepository"].stereotype == "PanacheRepository"
    assert cleaned_map["GlobalExceptionHandler"].stereotype == "@ServerExceptionMapper"
    assert cleaned_map["Order"].stereotype == "@Entity"

    # Verify responsibilities cleaned of Spring mentions
    for c in cleaned:
        for resp in c.responsibilities:
            assert "Spring" not in resp

    # Verify layering rules and cycle eradication:
    # Controller depends only on Service (Repository pruned)
    assert cleaned_map["OrderController"].dependencies == ["OrderService"]
    # Service depends only on Repository (Controller pruned)
    assert cleaned_map["OrderService"].dependencies == ["OrderRepository"]
    # Repository depends only on Model (Service pruned)
    assert cleaned_map["OrderRepository"].dependencies == ["Order"]
    # Model has NO dependencies (Repository pruned)
    assert cleaned_map["Order"].dependencies == []
