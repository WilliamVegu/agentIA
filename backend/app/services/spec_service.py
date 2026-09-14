import re
import uuid
from typing import Dict, List, Tuple
from app.models.blueprint import (
    ArchitectureBlueprint,
    DomainEntity,
    EntityAttribute,
    UserStoryRecord,
    AcceptanceScenarioRecord,
    SpecificationSummary,
)

# In-memory store for parsed specifications
SPECIFICATIONS_STORE: Dict[str, ArchitectureBlueprint] = {}

def parse_spec_markdown(content: str) -> ArchitectureBlueprint:
    """
    Parses standard Spec Kit Markdown files extracting service name,
    entities, user stories, and Given/When/Then scenarios.
    """
    # 1. Extract Service Name
    branch_match = re.search(r"\*\*Feature Branch\*\*:\s*`([^`]+)`", content)
    if branch_match:
        raw_name = branch_match.group(1)
        # Strip sequential numbering like 001- if present
        clean_name = re.sub(r"^\d+-", "", raw_name)
    else:
        title_match = re.search(r"# Feature Specification:\s*(.+)", content)
        if title_match:
            clean_name = title_match.group(1).strip().lower().replace(" ", "-")
        else:
            clean_name = "app-service"

    package_name = f"com.corp.{clean_name.replace('-', '.')}"

    # 2. Extract Entities
    entities: List[DomainEntity] = []
    entity_section = re.search(r"### Key Entities.*?(?=##|\Z)", content, re.DOTALL)
    if entity_section:
        entity_matches = re.findall(r"-\s*\*\*([A-Za-z0-9]+)\*\*:\s*(.+)", entity_section.group(0))
        for name, desc in entity_matches:
            attrs = [EntityAttribute(name="id", type="UUID", isPrimaryKey=True)]
            # Look for extra attributes in description
            attr_matches = re.findall(r"(\w+)\s*\(([^)]+)\)", desc)
            for attr_name, attr_type_str in attr_matches:
                if attr_name.lower() != "id":
                    attrs.append(EntityAttribute(
                        name=attr_name,
                        type="String" if "String" in attr_type_str else "BigDecimal" if "BigDecimal" in attr_type_str else "Long",
                        nullable=False,
                        validationRules=["@NotNull"] if "@NotNull" in attr_type_str else ["@NotBlank"] if "@NotBlank" in attr_type_str else []
                    ))
            entities.append(DomainEntity(
                name=name,
                tableName=name.lower() + "s",
                attributes=attrs
            ))

    if not entities:
        # Fallback default entity
        entities.append(DomainEntity(
            name="Resource",
            tableName="resources",
            attributes=[
                EntityAttribute(name="id", type="UUID", isPrimaryKey=True),
                EntityAttribute(name="name", type="String", validationRules=["@NotBlank"])
            ]
        ))

    # 3. Extract User Stories and Given/When/Then scenarios
    user_stories: List[UserStoryRecord] = []
    story_blocks = re.findall(r"### User Story (\d+)\s*-\s*([^\n(]+)(?:\(Priority:\s*(P\d+)\))?(.*?)(?=### User Story|\Z)", content, re.DOTALL)
    
    for story_idx, story_title, priority, story_body in story_blocks:
        story_id = f"US-{story_idx}"
        prio = priority.strip() if priority else "P1"
        
        # Extract scenarios: Given X, When Y, Then Z
        scenarios: List[AcceptanceScenarioRecord] = []
        scenario_matches = re.findall(
            r"(?:(\d+)\.\s*)?\*\*Given\*\*\s*(.*?),\s*\*\*When\*\*\s*(.*?),\s*\*\*Then\*\*\s*([^\n.]+)",
            story_body,
            re.IGNORECASE
        )
        
        for sc_idx, given, when, then in scenario_matches:
            sc_id = f"AC-{story_idx}.{sc_idx or len(scenarios) + 1}"
            scenarios.append(AcceptanceScenarioRecord(
                scenarioId=sc_id,
                given=given.strip(),
                when=when.strip(),
                then=then.strip()
            ))

        if not scenarios:
            # Look for bullet points with Given When Then
            alt_matches = re.findall(r"Given\s+(.*?)\s+When\s+(.*?)\s+Then\s+([^\n.]+)", story_body, re.IGNORECASE)
            for given, when, then in alt_matches:
                scenarios.append(AcceptanceScenarioRecord(
                    scenarioId=f"AC-{story_idx}.{len(scenarios) + 1}",
                    given=given.strip(),
                    when=when.strip(),
                    then=then.strip()
                ))

        if not scenarios:
            # Provide baseline scenario if text had intent
            scenarios.append(AcceptanceScenarioRecord(
                scenarioId=f"AC-{story_idx}.1",
                given="valid request payload",
                when="operation is triggered",
                then="operation succeeds with 200 OK"
            ))

        user_stories.append(UserStoryRecord(
            id=story_id,
            priority=prio,
            role="User",
            intent=story_title.strip(),
            benefit="achieve expected business outcome",
            scenarios=scenarios
        ))

    if not user_stories:
        user_stories.append(UserStoryRecord(
            id="US-1",
            priority="P1",
            role="User",
            intent="manage resources",
            benefit="operate service",
            scenarios=[
                AcceptanceScenarioRecord(
                    scenarioId="AC-1.1",
                    given="service is running",
                    when="endpoint is called",
                    then="returns successful response"
                )
            ]
        ))

    blueprint = ArchitectureBlueprint(
        serviceName=clean_name,
        packageName=package_name,
        entities=entities,
        userStories=user_stories
    )

    validate_blueprint(blueprint)
    return blueprint

def validate_blueprint(blueprint: ArchitectureBlueprint) -> List[str]:
    """Validates structural and constitutional integrity of blueprint."""
    warnings = []
    
    if not blueprint.entities:
        raise ValueError("Specification must define at least one domain entity")

    for entity in blueprint.entities:
        has_pk = any(attr.isPrimaryKey for attr in entity.attributes)
        if not has_pk:
            raise ValueError(f"Entity '{entity.name}' must have at least one primary key attribute")

    if not blueprint.userStories:
        raise ValueError("Specification must include at least one user story")

    for story in blueprint.userStories:
        if not story.scenarios:
            raise ValueError(f"User Story '{story.id}' must include at least one acceptance scenario (Given/When/Then)")

    return warnings

def save_specification(blueprint: ArchitectureBlueprint) -> SpecificationSummary:
    spec_id = str(uuid.uuid4())
    warnings = validate_blueprint(blueprint)
    SPECIFICATIONS_STORE[spec_id] = blueprint

    return SpecificationSummary(
        specId=spec_id,
        serviceName=blueprint.serviceName,
        packageName=blueprint.packageName,
        entityCount=len(blueprint.entities),
        storyCount=len(blueprint.userStories),
        isValid=True,
        validationWarnings=warnings
    )

def get_specification(spec_id: str) -> ArchitectureBlueprint:
    if spec_id not in SPECIFICATIONS_STORE:
        raise KeyError(f"Specification {spec_id} not found")
    return SPECIFICATIONS_STORE[spec_id]

