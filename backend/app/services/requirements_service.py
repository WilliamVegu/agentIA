import re
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

try:
    from app.models.blueprint import (
        DomainEntity,
        EntityAttribute,
        UserStoryRecord,
        AcceptanceScenarioRecord,
    )
    from app.models.requirements import (
        RequirementsTransformRequest,
        RefinementRequest,
        SpecificationDraft,
    )
    from app.services.llm_factory import LLMFactory
except ImportError:
    from backend.app.models.blueprint import (
        DomainEntity,
        EntityAttribute,
        UserStoryRecord,
        AcceptanceScenarioRecord,
    )
    from backend.app.models.requirements import (
        RequirementsTransformRequest,
        RefinementRequest,
        SpecificationDraft,
    )
    from backend.app.services.llm_factory import LLMFactory

class LLMStoryDecomposition(BaseModel):
    id: str = Field(description="Story ID e.g. US-1")
    priority: str = Field(default="P1", description="P1, P2, or P3")
    role: str = Field(description="Stakeholder role e.g. Customer, Admin")
    intent: str = Field(description="What they want to do")
    benefit: str = Field(description="Why they want it")
    scenarios: List[AcceptanceScenarioRecord] = Field(
        min_length=2,
        description="At least 2 Given/When/Then scenarios: 1 happy path and 1 validation/error path.",
    )

class LLMEntityDecomposition(BaseModel):
    name: str = Field(description="PascalCase entity name e.g. Order, Payment")
    tableName: str = Field(description="snake_case table name e.g. orders, payments")
    attributes: List[EntityAttribute] = Field(
        min_length=1,
        description="Attributes including primary key and typed fields (String, Long, BigDecimal, Boolean, DateTime, UUID).",
    )

class LLMRequirementsDecomposition(BaseModel):
    serviceName: str = Field(description="Hyphenated service name e.g. payment-service")
    packageName: str = Field(description="Java package name e.g. com.corp.payment")
    assumptions: List[str] = Field(default_factory=list, description="Architecture or business assumptions")
    entities: List[LLMEntityDecomposition] = Field(
        min_length=1,
        description="List of domain entities extracted from requirements",
    )
    userStories: List[LLMStoryDecomposition] = Field(
        min_length=3,
        description="Synthesized user stories with prioritized Given/When/Then acceptance criteria. You MUST provide at least 3 distinct user stories (min 3: P1 core MVP flow, P2 validation/secondary workflow, P3 auxiliary/inquiry flow).",
    )

def serialize_draft_to_markdown(draft: SpecificationDraft) -> str:
    """
    Serializes a SpecificationDraft into a compliant Spec Kit Markdown document
    that is directly parseable by spec_service.py.
    """
    title = draft.serviceName.replace("-", " ").title()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    md_lines = [
        f"# Feature Specification: {title}",
        "",
        f"**Feature Branch**: `{draft.serviceName}`",
        "",
        f"**Created**: {date_str}",
        "",
        "**Status**: Draft",
        "",
        "## User Scenarios & Testing *(mandatory)*",
        "",
    ]

    for idx, story in enumerate(draft.userStories, start=1):
        md_lines.append(f"### User Story {idx} - {story.intent} (Priority: {story.priority})")
        md_lines.append("")
        md_lines.append(f"As a {story.role}, I want {story.intent}, so that {story.benefit}.")
        md_lines.append("")
        md_lines.append("**Acceptance Scenarios**:")
        md_lines.append("")
        for sc_idx, sc in enumerate(story.scenarios, start=1):
            md_lines.append(f"{sc_idx}. **Given** {sc.given}, **When** {sc.when}, **Then** {sc.then}.")
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    if draft.assumptions:
        md_lines.append("### Assumptions & Edge Cases")
        md_lines.append("")
        for assumption in draft.assumptions:
            md_lines.append(f"- {assumption}")
        md_lines.append("")

    md_lines.append("## Requirements *(mandatory)*")
    md_lines.append("")
    md_lines.append("### Key Entities")
    md_lines.append("")

    for entity in draft.entities:
        attr_strs = []
        for attr in entity.attributes:
            rules_str = f", {', '.join(attr.validationRules)}" if attr.validationRules else ""
            pk_str = ", PK" if attr.isPrimaryKey else ""
            attr_strs.append(f"{attr.name} ({attr.type}{pk_str}{rules_str})")
        joined_attrs = ", ".join(attr_strs)
        md_lines.append(f"- **{entity.name}**: Attributes: {joined_attrs}")

    md_lines.append("")
    return "\n".join(md_lines)

def _generate_mock_decomposition(raw_text: str, service_name: Optional[str] = None) -> LLMRequirementsDecomposition:
    """Deterministic fallback/mock generator for tests and offline mode."""
    clean_service = service_name or "order-service"
    clean_service = re.sub(r"[^a-z0-9-]", "", clean_service.lower().replace(" ", "-")) or "app-service"
    package = f"com.corp.{clean_service.replace('-', '.')}"

    return LLMRequirementsDecomposition(
        serviceName=clean_service,
        packageName=package,
        assumptions=[
            "Data retention adheres to standard 90-day retention policies.",
            "All monetary transactions require validation against active accounts.",
        ],
        entities=[
            LLMEntityDecomposition(
                name="Order",
                tableName="orders",
                attributes=[
                    EntityAttribute(name="id", type="Long", isPrimaryKey=True),
                    EntityAttribute(name="customerEmail", type="String", validationRules=["@NotBlank", "@Email"]),
                    EntityAttribute(name="totalAmount", type="BigDecimal", validationRules=["@NotNull", "@Positive"]),
                ],
            )
        ],
        userStories=[
            LLMStoryDecomposition(
                id="US-1",
                priority="P1",
                role="Customer",
                intent="create an order with valid payment",
                benefit="receive the purchased items",
                scenarios=[
                    AcceptanceScenarioRecord(
                        scenarioId="AC-1.1",
                        given="a customer with an active account and valid payment method",
                        when="submitting an order with customer email and positive amount",
                        then="order is created in PENDING status and 201 Created is returned",
                    ),
                    AcceptanceScenarioRecord(
                        scenarioId="AC-1.2",
                        given="an order request with a negative or zero amount",
                        when="submitting the invalid order payload",
                        then="system rejects with 400 Bad Request and validation error details",
                    ),
                ],
            ),
            LLMStoryDecomposition(
                id="US-2",
                priority="P2",
                role="Inventory Operator",
                intent="validate and update order processing status",
                benefit="ensure sufficient stock before fulfillment",
                scenarios=[
                    AcceptanceScenarioRecord(
                        scenarioId="AC-2.1",
                        given="an active order with valid item reservations",
                        when="processing the order verification workflow",
                        then="order status is updated to CONFIRMED and 200 OK is returned",
                    ),
                    AcceptanceScenarioRecord(
                        scenarioId="AC-2.2",
                        given="an order with insufficient warehouse stock or invalid state",
                        when="attempting fulfillment transition",
                        then="system rejects with 400 Bad Request error and cancellation reason",
                    ),
                ],
            ),
            LLMStoryDecomposition(
                id="US-3",
                priority="P3",
                role="Auditor",
                intent="query and audit historical order records",
                benefit="track transaction lifecycle and reconcile accounts",
                scenarios=[
                    AcceptanceScenarioRecord(
                        scenarioId="AC-3.1",
                        given="an authenticated auditor with valid search criteria and active session",
                        when="querying order transactions by identifier or date filter",
                        then="matching order records are returned with 200 OK",
                    ),
                    AcceptanceScenarioRecord(
                        scenarioId="AC-3.2",
                        given="an invalid query parameter or unauthorized request",
                        when="fetching order audit logs",
                        then="system rejects with 400 Bad Request error or 401 Unauthorized",
                    ),
                ],
            ),
        ],
    )

def transform_requirements(
    request: RequirementsTransformRequest,
    api_key: str,
    provider: Optional[str] = None,
) -> SpecificationDraft:
    """
    Decomposes unstructured natural language requirements into canonical User Stories,
    BDD Acceptance Criteria (Given/When/Then), and Domain Entities.
    Supports free providers (Gemini, Groq), OpenAI, and offline mock mode.
    """
    chosen_provider = provider or getattr(request, "provider", None)
    chosen_model = getattr(request, "modelName", None)

    if LLMFactory.is_mock(api_key, chosen_provider):
        decomp = _generate_mock_decomposition(request.rawText, request.serviceName)
    else:
        from langchain_core.messages import SystemMessage, HumanMessage

        llm = LLMFactory.get_chat_model(
            api_key=api_key,
            provider=chosen_provider,
            model_name=chosen_model,
            temperature=0.2,
        )
        if llm is None:
            decomp = _generate_mock_decomposition(request.rawText, request.serviceName)
        else:
            structured_llm = llm.with_structured_output(LLMRequirementsDecomposition)

            system_prompt = (
                "You are an expert Enterprise Software Architect and Agile Product Owner. "
                "Your task is to analyze natural language software requirements and synthesize a complete, formal "
                "specification draft conforming to modern microservice standards (Spring Boot 3 / Java 21):\n"
                "1. SERVICE & PACKAGE: Propose a kebab-case serviceName (e.g. 'payment-service') and Java packageName (e.g. 'com.corp.payment').\n"
                "2. DOMAIN ENTITIES: Extract all business domain entities. Each entity MUST have an 'id' attribute (UUID or Long, isPrimaryKey=True) "
                "and typed attributes (String, Long, BigDecimal, Boolean, DateTime, UUID) with Jakarta Validation rules (@NotBlank, @NotNull, @Positive, @Email, etc.).\n"
                "3. USER STORIES: Synthesize AT LEAST 3 formal User Stories (minItems: 3). You MUST provide a minimum of 3 distinct user stories:\n"
                "   - Story 1 (Priority P1): Core MVP transaction/creation flow (As a [role], I want to create/register [entity], so that [benefit]).\n"
                "   - Story 2 (Priority P2): Secondary business workflow, state transition, or validation flow.\n"
                "   - Story 3 (Priority P3): Auxiliary inquiry, search, or audit flow.\n"
                "   Adhere strictly to 'As a [role], I want [action], so that [benefit]'.\n"
                "4. ACCEPTANCE SCENARIOS: For EVERY user story, generate AT LEAST 2 Given/When/Then acceptance scenarios (minItems: 2):\n"
                "   - At least 1 Happy Path scenario.\n"
                "   - At least 1 Validation / Business Error scenario (e.g. invalid input, insufficient balance, resource not found).\n"
                "5. ASSUMPTIONS: Document any technical or business assumptions made during analysis."
            )

            user_content = f"Requirements Input:\n{request.rawText}"
            if request.serviceName:
                user_content += f"\nRequested Service Name: {request.serviceName}"
            if request.packageName:
                user_content += f"\nRequested Package Name: {request.packageName}"

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content),
            ]

            decomp: LLMRequirementsDecomposition = structured_llm.invoke(messages)

    # Convert LLM decomposition into SpecificationDraft
    entities: List[DomainEntity] = []
    for ent in decomp.entities:
        has_pk = any(attr.isPrimaryKey for attr in ent.attributes)
        attrs = list(ent.attributes)
        if not has_pk:
            attrs.insert(0, EntityAttribute(name="id", type="UUID", isPrimaryKey=True))
        entities.append(DomainEntity(
            name=ent.name,
            tableName=ent.tableName,
            attributes=attrs,
        ))

    user_stories: List[UserStoryRecord] = []
    for st_idx, st in enumerate(decomp.userStories, start=1):
        story_id = f"US-{st_idx}"
        scenarios: List[AcceptanceScenarioRecord] = []
        for sc_idx, sc in enumerate(st.scenarios, start=1):
            scenarios.append(AcceptanceScenarioRecord(
                scenarioId=f"AC-{st_idx}.{sc_idx}",
                given=sc.given.strip(),
                when=sc.when.strip(),
                then=sc.then.strip(),
            ))
        # Ensure at least 2 scenarios per story (Constitution Principle V & Clarification #3)
        if len(scenarios) < 2:
            scenarios.append(AcceptanceScenarioRecord(
                scenarioId=f"AC-{st_idx}.{len(scenarios) + 1}",
                given=f"an invalid or unauthorized request for {st.intent}",
                when="the request is submitted",
                then="the system rejects the transaction with an appropriate HTTP client error",
            ))

        user_stories.append(UserStoryRecord(
            id=story_id,
            priority=st.priority if st.priority in ("P1", "P2", "P3") else "P1",
            role=st.role,
            intent=st.intent,
            benefit=st.benefit,
            scenarios=scenarios,
        ))

    # Ensure minimum 3 user stories (P1 core, P2 secondary/validation, P3 audit/inquiry)
    while len(user_stories) < 3:
        st_idx = len(user_stories) + 1
        prio = "P2" if st_idx == 2 else "P3"
        ent_name = entities[0].name if entities else "Resource"
        if st_idx == 2:
            intent_val = f"process and update {ent_name.lower()} state"
            benefit_val = f"ensure operational consistency of {ent_name.lower()}"
            sc1 = AcceptanceScenarioRecord(
                scenarioId=f"AC-{st_idx}.1",
                given=f"an existing {ent_name.lower()} in an active and valid state",
                when="executing status update or validation workflow",
                then=f"the {ent_name.lower()} status is updated and 200 OK is returned",
            )
            sc2 = AcceptanceScenarioRecord(
                scenarioId=f"AC-{st_idx}.2",
                given=f"an invalid update payload or non-existent {ent_name.lower()}",
                when="submitting the processing request",
                then="system rejects with 400 Bad Request error and details",
            )
        else:
            intent_val = f"query and audit {ent_name.lower()} records"
            benefit_val = f"verify transaction history for {ent_name.lower()}"
            sc1 = AcceptanceScenarioRecord(
                scenarioId=f"AC-{st_idx}.1",
                given=f"an authenticated client with valid query filters and active session",
                when=f"requesting {ent_name.lower()} records by ID or criteria",
                then=f"matching {ent_name.lower()} records are returned with 200 OK",
            )
            sc2 = AcceptanceScenarioRecord(
                scenarioId=f"AC-{st_idx}.2",
                given=f"an invalid filter or unauthorized query for {ent_name.lower()}",
                when="executing the query",
                then="system rejects with 400 Bad Request error or 401 Unauthorized",
            )
        user_stories.append(UserStoryRecord(
            id=f"US-{st_idx}",
            priority=prio,
            role="System Operator" if st_idx == 2 else "Auditor",
            intent=intent_val,
            benefit=benefit_val,
            scenarios=[sc1, sc2],
        ))

    service_name = request.serviceName or decomp.serviceName
    clean_service = re.sub(r"[^a-z0-9-]", "", service_name.lower().replace(" ", "-")) or "service-app"
    package_name = request.packageName or decomp.packageName or f"com.corp.{clean_service.replace('-', '.')}"

    draft = SpecificationDraft(
        serviceName=clean_service,
        packageName=package_name,
        basePort=8080,
        entities=entities,
        userStories=user_stories,
        assumptions=decomp.assumptions,
    )
    draft.markdownSpec = serialize_draft_to_markdown(draft)
    return draft

def refine_specification(
    request: RefinementRequest,
    api_key: str,
    provider: Optional[str] = None,
) -> SpecificationDraft:
    """
    Applies natural language refinement feedback to update stories, scenarios, or entities in a draft.
    Supports free providers (Gemini, Groq), OpenAI, and offline mock mode.
    """
    chosen_provider = provider or getattr(request, "provider", None)
    chosen_model = getattr(request, "modelName", None)

    if LLMFactory.is_mock(api_key, chosen_provider):
        # For mock/testing, apply deterministic modification based on prompt
        updated_stories = list(request.currentDraft.userStories)
        if request.targetStoryId:
            for s in updated_stories:
                if s.id == request.targetStoryId:
                    s.scenarios.append(AcceptanceScenarioRecord(
                        scenarioId=f"AC-{s.id.replace('US-', '')}.{len(s.scenarios) + 1}",
                        given="refined condition based on user feedback",
                        when="user triggers refined action",
                        then="expected refined behavior is verified",
                    ))
        else:
            # Add scenario to first story
            if updated_stories:
                updated_stories[0].scenarios.append(AcceptanceScenarioRecord(
                    scenarioId=f"AC-1.{len(updated_stories[0].scenarios) + 1}",
                    given="feedback prompt applied: " + request.feedbackPrompt[:30],
                    when="system executes updated logic",
                    then="specification reflects refined requirement",
                ))

        draft = request.currentDraft.model_copy(update={"userStories": updated_stories})
        draft.markdownSpec = serialize_draft_to_markdown(draft)
        return draft

    from langchain_core.messages import SystemMessage, HumanMessage

    llm = LLMFactory.get_chat_model(
        api_key=api_key,
        provider=chosen_provider,
        model_name=chosen_model,
        temperature=0.2,
    )
    if llm is None:
        draft = request.currentDraft.model_copy()
        draft.markdownSpec = serialize_draft_to_markdown(draft)
        return draft

    structured_llm = llm.with_structured_output(LLMRequirementsDecomposition)

    system_prompt = (
        "You are an expert Software Architect and Agile Product Owner. "
        "You are given an existing SpecificationDraft and user feedback/refinement instructions. "
        "Apply the requested changes to the specification draft, modifying existing stories/scenarios, "
        "adding new acceptance scenarios, or refining entities as instructed. "
        "Ensure every story maintains at least 2 Given/When/Then scenarios (at least 1 happy path and 1 error scenario)."
    )

    current_summary = (
        f"Current Service: {request.currentDraft.serviceName}\n"
        f"Current Stories: {[s.model_dump() for s in request.currentDraft.userStories]}\n"
        f"Current Entities: {[e.model_dump() for e in request.currentDraft.entities]}\n"
        f"Target Story: {request.targetStoryId or 'ALL'}\n"
        f"Feedback / Refinement Prompt: {request.feedbackPrompt}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=current_summary),
    ]

    decomp: LLMRequirementsDecomposition = structured_llm.invoke(messages)

    # Reconstruct updated draft
    entities: List[DomainEntity] = []
    for ent in decomp.entities:
        has_pk = any(attr.isPrimaryKey for attr in ent.attributes)
        attrs = list(ent.attributes)
        if not has_pk:
            attrs.insert(0, EntityAttribute(name="id", type="UUID", isPrimaryKey=True))
        entities.append(DomainEntity(
            name=ent.name,
            tableName=ent.tableName,
            attributes=attrs,
        ))

    user_stories: List[UserStoryRecord] = []
    for st_idx, st in enumerate(decomp.userStories, start=1):
        story_id = f"US-{st_idx}"
        scenarios: List[AcceptanceScenarioRecord] = []
        for sc_idx, sc in enumerate(st.scenarios, start=1):
            scenarios.append(AcceptanceScenarioRecord(
                scenarioId=f"AC-{st_idx}.{sc_idx}",
                given=sc.given.strip(),
                when=sc.when.strip(),
                then=sc.then.strip(),
            ))
        if len(scenarios) < 2:
            scenarios.append(AcceptanceScenarioRecord(
                scenarioId=f"AC-{st_idx}.{len(scenarios) + 1}",
                given="an invalid request condition",
                when="operation is invoked",
                then="system returns 400 Bad Request",
            ))

        user_stories.append(UserStoryRecord(
            id=story_id,
            priority=st.priority if st.priority in ("P1", "P2", "P3") else "P1",
            role=st.role,
            intent=st.intent,
            benefit=st.benefit,
            scenarios=scenarios,
        ))

    refined_draft = SpecificationDraft(
        serviceName=request.currentDraft.serviceName,
        packageName=request.currentDraft.packageName,
        basePort=request.currentDraft.basePort,
        entities=entities if entities else request.currentDraft.entities,
        userStories=user_stories if user_stories else request.currentDraft.userStories,
        assumptions=decomp.assumptions or request.currentDraft.assumptions,
    )
    refined_draft.markdownSpec = serialize_draft_to_markdown(refined_draft)
    return refined_draft

