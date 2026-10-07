import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    from app.models.architecture import (
        ComponentDefinition,
        ApiEndpointDefinition,
        ComponentInteraction,
        ArchitectureDesignRequest,
        ArchitectureRefinementRequest,
        ArchitectureDesignResponse,
        LayerType,
        HttpMethod,
        InteractionType,
    )
    from app.models.blueprint import DomainEntity, UserStoryRecord, EntityAttribute
    from app.models.requirements import SpecificationDraft
    from app.services.llm_factory import LLMFactory
except ImportError:
    from backend.app.models.architecture import (
        ComponentDefinition,
        ApiEndpointDefinition,
        ComponentInteraction,
        ArchitectureDesignRequest,
        ArchitectureRefinementRequest,
        ArchitectureDesignResponse,
        LayerType,
        HttpMethod,
        InteractionType,
    )
    from backend.app.models.blueprint import DomainEntity, UserStoryRecord, EntityAttribute
    from backend.app.models.requirements import SpecificationDraft
    from backend.app.services.llm_factory import LLMFactory

class LLMComponentDecomposition(BaseModel):
    name: str = Field(description="PascalCase component name, e.g. OrderResource, OrderService, OrderRepository")
    layer: str = Field(description="controller, service, repository, model, or infrastructure")
    stereotype: str = Field(
        description=(
            "Quarkus 3.x stereotype ONLY: @Path for controller/resource, @ApplicationScoped for service, "
            "PanacheRepository for repository, @Entity for model, @ServerExceptionMapper for infrastructure. "
            "PROHIBIDO TERMINANTEMENTE EL USO DE ANOTACIONES O ESTEREOTIPOS DE SPRING (@RestController, @Service, @Repository, @RestControllerAdvice, @Autowired)."
        )
    )
    responsibilities: List[str] = Field(description="Primary responsibilities in Spanish")
    dependencies: List[str] = Field(description="Components this component depends on (must be strictly downward, ZERO circular dependencies)")
    mappedStories: List[str] = Field(default_factory=list, description="Story IDs e.g. US-1")

class LLMEndpointDecomposition(BaseModel):
    method: str = Field(description="GET, POST, PUT, DELETE, PATCH")
    path: str = Field(description="URI path e.g. /api/v1/orders")
    summary: str = Field(description="Endpoint description")
    requestDto: Optional[str] = Field(default=None, description="Request Record name")
    responseDto: Optional[str] = Field(default=None, description="Response Record name")
    successStatus: int = Field(default=200, description="200, 201, 204")
    errorStatuses: List[int] = Field(default_factory=lambda: [400, 500])
    mappedScenarioId: Optional[str] = Field(default=None)

class LLMArchitecturePayload(BaseModel):
    components: List[LLMComponentDecomposition] = Field(min_length=3)
    endpoints: List[LLMEndpointDecomposition] = Field(min_length=1)

def serialize_to_openapi_yaml(
    service_name: str,
    package_name: str,
    endpoints: List[ApiEndpointDefinition],
    entities: List[DomainEntity],
) -> str:
    """Serializes derived REST API endpoints and DTO schemas into a compliant OpenAPI 3.0 YAML document."""
    title = f"{service_name.replace('-', ' ').title()} API"
    paths_dict: Dict = {}

    for ep in endpoints:
        path = ep.path
        if path not in paths_dict:
            paths_dict[path] = {}

        method_key = ep.method.value.lower()
        operation = {
            "summary": ep.summary,
            "operationId": f"{method_key}_{re.sub(r'[^a-zA-Z0-9]', '_', path).strip('_')}",
            "responses": {
                str(ep.successStatus): {
                    "description": "Successful operation",
                }
            }
        }
        if ep.responseDto:
            operation["responses"][str(ep.successStatus)]["content"] = {
                "application/json": {
                    "schema": {"$ref": f"#/components/schemas/{ep.responseDto}"}
                }
            }

        for err_code in ep.errorStatuses:
            operation["responses"][str(err_code)] = {
                "description": f"Error response {err_code}",
                "content": {
                    "application/problem+json": {
                        "schema": {"$ref": "#/components/schemas/ProblemDetails"}
                    }
                }
            }

        if ep.requestDto and ep.method in (HttpMethod.POST, HttpMethod.PUT, HttpMethod.PATCH):
            operation["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{ep.requestDto}"}
                    }
                }
            }

        paths_dict[path][method_key] = operation

    # Build schema components
    schemas: Dict = {
        "ProblemDetails": {
            "type": "object",
            "required": ["timestamp", "status", "message"],
            "properties": {
                "timestamp": {"type": "string", "format": "date-time"},
                "status": {"type": "integer"},
                "message": {"type": "string"},
                "details": {"type": "array", "items": {"type": "string"}},
            }
        }
    }

    for ent in entities:
        properties = {}
        for attr in ent.attributes:
            prop_type = "string"
            prop_fmt = None
            if attr.type in ("Long", "Integer"):
                prop_type = "integer"
            elif attr.type == "BigDecimal":
                prop_type = "number"
            elif attr.type == "Boolean":
                prop_type = "boolean"
            elif attr.type == "UUID":
                prop_type = "string"
                prop_fmt = "uuid"
            elif attr.type == "DateTime":
                prop_type = "string"
                prop_fmt = "date-time"

            prop_def: Dict = {"type": prop_type}
            if prop_fmt:
                prop_def["format"] = prop_fmt
            properties[attr.name] = prop_def

        # Response Record DTO
        schemas[f"{ent.name}Response"] = {
            "type": "object",
            "description": f"Immutable Java Record response for {ent.name}",
            "properties": properties,
        }

        # Request Record DTO (excluding generated ID)
        req_props = {k: v for k, v in properties.items() if k != "id"}
        schemas[f"Create{ent.name}Request"] = {
            "type": "object",
            "description": f"Immutable Java Record request with Jakarta validation for {ent.name}",
            "required": [k for k in req_props.keys()],
            "properties": req_props,
        }

    openapi_doc = {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "description": f"Auto-generated API contracts for {service_name} conforming to Quarkus 3.x / Java 21 Records.",
            "version": "1.0.0",
        },
        "servers": [{"url": f"http://localhost:8080", "description": "Local server"}],
        "paths": paths_dict,
        "components": {"schemas": schemas},
    }

    return yaml.dump(openapi_doc, sort_keys=False)

def generate_mermaid_flowchart(
    components: List[ComponentDefinition],
    interactions: List[ComponentInteraction],
) -> str:
    """Generates a clean, layer-partitioned Mermaid flowchart."""
    lines = ["flowchart TD"]

    layers = {
        LayerType.CONTROLLER: ("Presentation", "Capa Controller / Resource (REST / HTTP)"),
        LayerType.SERVICE: ("Business", "Capa Service (Lógica de Negocio)"),
        LayerType.REPOSITORY: ("Persistence", "Capa Repository (Persistencia Panache / Hibernate ORM)"),
        LayerType.MODEL: ("Domain", "Capa Model (Dominio & Entidades)"),
        LayerType.INFRASTRUCTURE: ("Infrastructure", "Capa Infrastructure (Componentes Transversales & Excepciones)"),
    }

    comp_by_layer: Dict[LayerType, List[ComponentDefinition]] = {l: [] for l in LayerType}
    for c in components:
        comp_by_layer[c.layer].append(c)

    for layer_enum, (sub_id, sub_title) in layers.items():
        layer_comps = comp_by_layer[layer_enum]
        if layer_comps:
            lines.append(f'    subgraph {sub_id}["{sub_title}"]')
            for c in layer_comps:
                clean_name = re.sub(r"[^a-zA-Z0-9_]", "", c.name)
                lines.append(f'        {clean_name}["{c.name}<br/><i>{c.stereotype}</i>"]')
            lines.append("    end")

    # Add interaction links
    for inter in interactions:
        src = re.sub(r"[^a-zA-Z0-9_]", "", inter.sourceComponent)
        tgt = re.sub(r"[^a-zA-Z0-9_]", "", inter.targetComponent)
        if inter.interactionType == InteractionType.CALLS:
            lines.append(f"    {src} --> {tgt}")
        elif inter.interactionType == InteractionType.PERSISTS:
            lines.append(f"    {src} -->|persists| {tgt}")
        elif inter.interactionType == InteractionType.INTERCEPTS:
            lines.append(f"    {src} -.->|intercepts| {tgt}")
        else:
            lines.append(f"    {src} -.-> {tgt}")

    return "\n".join(lines)

def serialize_architecture_markdown(response: ArchitectureDesignResponse) -> str:
    """Generates the architecture.md document with full component catalog and Mermaid diagram."""
    lines = [
        f"# Architectural Blueprint / Blueprint Arquitectónico: {response.serviceName.replace('-', ' ').title()}",
        "",
        f"**Paquete Base**: `{response.packageName}` | **Puerto HTTP**: `{response.basePort}`",
        f"**Generado**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## 1. Topología Arquitectónica en 4 Capas",
        "",
        "```mermaid",
        response.mermaidDiagram,
        "```",
        "",
        "---",
        "",
        "## 2. Catálogo de Componentes",
        "",
        "| Componente | Capa | Estereotipo | Paquete | Responsabilidades | Dependencias |",
        "|:---|:---|:---|:---|:---|:---|",
    ]

    for c in response.components:
        resp_str = "<br/>".join([f"• {r}" for r in c.responsibilities]) or "—"
        dep_str = ", ".join(c.dependencies) or "—"
        lines.append(f"| **{c.name}** | `{c.layer.value}` | `{c.stereotype}` | `{c.packageName}` | {resp_str} | {dep_str} |")

    lines.extend([
        "",
        "---",
        "",
        "## 3. Catálogo de Endpoints REST Derivados",
        "",
        "| Método | Ruta | Resumen | Request DTO | Response DTO | Éxito | Errores | Criterio BDD |",
        "|:---|:---|:---|:---|:---|:---:|:---:|:---:|",
    ])

    for ep in response.endpoints:
        req_str = f"`{ep.requestDto}`" if ep.requestDto else "—"
        res_str = f"`{ep.responseDto}`" if ep.responseDto else "—"
        err_str = ", ".join(map(str, ep.errorStatuses))
        scenario_str = ep.mappedScenarioId or "—"
        lines.append(f"| `{ep.method.value}` | `{ep.path}` | {ep.summary} | {req_str} | {res_str} | `{ep.successStatus}` | `{err_str}` | `{scenario_str}` |")

    lines.extend([
        "",
        "---",
        "",
        "## 4. Gobernanza y Cumplimiento Constitucional (Quarkus 3.x)",
        "",
        "- **Principio I (Capas Estrictas y Cero Dependencias Cíclicas)**: Dependencias unidireccionales Controller/Resource (@Path) ➔ Service (@ApplicationScoped) ➔ Repository (PanacheRepository) ➔ Model (@Entity). Cero dependencias cíclicas.",
        "- **Principio II (Records DTOs Inmutables)**: DTOs inmutables desacoplados de la persistencia con validación declarativa Jakarta Validation.",
        "- **Principio III (Excepciones Centralizadas)**: Manejador `@ServerExceptionMapper` uniforme con respuestas estándar RFC 7807 ProblemDetails.",
        "- **Reglas Obligatorias de Arquitectura y Framework**:",
        "  * No utilizar dependencias de Spring.",
        "  * No utilizar Spring MVC (100% Quarkus REST con anotaciones Jakarta REST `@Path`).",
        "  * No utilizar Spring Data JPA (100% Hibernate ORM con `PanacheRepository`).",
        "  * No permitir dependencias cíclicas entre capas (flujo estrictamente unidireccional).",
        "  * Framework 100% nativo Quarkus 3.x y Java 21 LTS.",
        "",
    ])

    return "\n".join(lines)

def sanitize_quarkus_components(
    raw_components: List[ComponentDefinition],
) -> List[ComponentDefinition]:
    """
    Enforces pure Quarkus 3.x stereotypes, eliminates any Spring Boot/MVC/Data JPA references,
    and breaks any circular or upward dependencies between architectural layers.
    """
    STEREOTYPE_MAP = {
        LayerType.CONTROLLER: "@Path",
        LayerType.SERVICE: "@ApplicationScoped",
        LayerType.REPOSITORY: "PanacheRepository",
        LayerType.MODEL: "@Entity",
        LayerType.INFRASTRUCTURE: "@ServerExceptionMapper",
    }

    # First pass: clean names, stereotypes, and responsibilities
    cleaned: List[ComponentDefinition] = []
    comp_by_name: Dict[str, ComponentDefinition] = {}

    for comp in raw_components:
        layer = comp.layer if isinstance(comp.layer, LayerType) else LayerType(str(comp.layer).lower())

        stereo = comp.stereotype or ""
        if any(s in stereo for s in ("@RestControllerAdvice", "@ControllerAdvice")):
            stereo = "@ServerExceptionMapper"
        elif any(s in stereo for s in ("@RestController", "@Controller", "@RequestMapping")):
            stereo = "@Path"
        elif any(s in stereo for s in ("@Service", "@Component", "@Autowired")):
            stereo = "@ApplicationScoped"
        elif any(s in stereo for s in ("@Repository", "JpaRepository", "CrudRepository")):
            stereo = "PanacheRepository"
        elif not stereo or (not stereo.startswith("@") and layer != LayerType.REPOSITORY):
            stereo = STEREOTYPE_MAP.get(layer, "@ApplicationScoped")

        cleaned_resps = []
        for r in comp.responsibilities:
            r_clean = (
                r.replace("Spring Data JPA", "Panache Hibernate ORM")
                .replace("Spring Data", "Panache")
                .replace("Spring MVC", "Quarkus REST")
                .replace("Spring Boot", "Quarkus 3.x")
                .replace("Spring", "Quarkus")
                .replace("@RestControllerAdvice", "@ServerExceptionMapper")
                .replace("@RestController", "@Path (Quarkus REST)")
                .replace("@Service", "@ApplicationScoped")
                .replace("@Repository", "PanacheRepository")
            )
            cleaned_resps.append(r_clean)

        new_c = comp.model_copy(update={
            "layer": layer,
            "stereotype": stereo,
            "responsibilities": cleaned_resps,
        })
        cleaned.append(new_c)
        comp_by_name[new_c.name] = new_c

    # Second pass: Eliminate circular dependencies and enforce strict downward layering
    sanitized: List[ComponentDefinition] = []
    for comp in cleaned:
        valid_deps: List[str] = []

        for dep_name in comp.dependencies:
            if dep_name not in comp_by_name or dep_name == comp.name:
                continue

            dep_comp = comp_by_name[dep_name]

            # Strict downward rules:
            # Controller -> Service, Infrastructure
            # Service -> Repository, Service (non-cycle)
            # Repository -> Model
            # Model -> None
            # Infrastructure -> None
            if comp.layer == LayerType.CONTROLLER:
                if dep_comp.layer in (LayerType.SERVICE, LayerType.INFRASTRUCTURE):
                    valid_deps.append(dep_name)
            elif comp.layer == LayerType.SERVICE:
                if dep_comp.layer == LayerType.REPOSITORY:
                    valid_deps.append(dep_name)
                elif dep_comp.layer == LayerType.SERVICE:
                    # Prevent mutual circular dependency
                    if comp.name not in dep_comp.dependencies:
                        valid_deps.append(dep_name)
            elif comp.layer == LayerType.REPOSITORY:
                if dep_comp.layer == LayerType.MODEL:
                    valid_deps.append(dep_name)

        sanitized.append(comp.model_copy(update={"dependencies": valid_deps}))

    return sanitized

def _generate_mock_architecture(draft: SpecificationDraft) -> ArchitectureDesignResponse:
    """Deterministic mock architecture generator for unit tests and offline execution."""
    service_name = draft.serviceName or "order-service"
    package_name = draft.packageName or f"com.corp.{service_name.replace('-', '.')}"
    components: List[ComponentDefinition] = []
    endpoints: List[ApiEndpointDefinition] = []
    interactions: List[ComponentInteraction] = []

    # Cross-Cutting Infrastructure
    infra_comp = ComponentDefinition(
        name="GlobalExceptionHandler",
        layer=LayerType.INFRASTRUCTURE,
        stereotype="@ServerExceptionMapper",
        packageName=f"{package_name}.controller.advice",
        responsibilities=[
            "Interceptar excepciones HTTP y errores de validación de entrada",
            "Formatear respuestas como estándar RFC 7807 ProblemDetails",
        ],
        dependencies=[],
        mappedStories=["ALL"],
    )
    components.append(infra_comp)

    # Generate components per domain entity
    default_ent = DomainEntity(name="Order", tableName="orders", attributes=[EntityAttribute(name="id", type="Long", isPrimaryKey=True)])
    for ent in (draft.entities or [default_ent]):
        ent_name = ent.name
        table_name = ent.tableName or f"{ent_name.lower()}s"

        repo_comp = ComponentDefinition(
            name=f"{ent_name}Repository",
            layer=LayerType.REPOSITORY,
            stereotype="PanacheRepository",
            packageName=f"{package_name}.repository",
            responsibilities=[f"Operaciones de persistencia con Panache y Hibernate ORM para la entidad {ent_name}"],
            dependencies=[ent_name],
            mappedStories=["US-1"],
        )

        service_comp = ComponentDefinition(
            name=f"{ent_name}Service",
            layer=LayerType.SERVICE,
            stereotype="@ApplicationScoped",
            packageName=f"{package_name}.service",
            responsibilities=[
                f"Lógica de negocio y delimitación transaccional para {ent_name}",
                "Validación de reglas de negocio y mapeo entre entidades y Java Records",
            ],
            dependencies=[repo_comp.name],
            mappedStories=["US-1"],
        )

        controller_comp = ComponentDefinition(
            name=f"{ent_name}Controller",
            layer=LayerType.CONTROLLER,
            stereotype="@Path",
            packageName=f"{package_name}.controller",
            responsibilities=[
                f"Enrutamiento de endpoints HTTP con Quarkus REST para {table_name}",
                "Activación de validación declarativa con @Valid en payloads de entrada",
            ],
            dependencies=[service_comp.name],
            mappedStories=["US-1"],
        )

        model_comp = ComponentDefinition(
            name=ent_name,
            layer=LayerType.MODEL,
            stereotype="@Entity",
            packageName=f"{package_name}.model",
            responsibilities=[f"Entidad de dominio JPA/Panache mapeada a la tabla relacional {table_name}"],
            dependencies=[],
            mappedStories=["US-1"],
        )

        components.extend([controller_comp, service_comp, repo_comp, model_comp])

        # Interactions
        interactions.append(ComponentInteraction(sourceComponent=controller_comp.name, targetComponent=service_comp.name, interactionType=InteractionType.CALLS))
        interactions.append(ComponentInteraction(sourceComponent=service_comp.name, targetComponent=repo_comp.name, interactionType=InteractionType.CALLS))
        interactions.append(ComponentInteraction(sourceComponent=repo_comp.name, targetComponent=model_comp.name, interactionType=InteractionType.PERSISTS))
        interactions.append(ComponentInteraction(sourceComponent=infra_comp.name, targetComponent=controller_comp.name, interactionType=InteractionType.INTERCEPTS))

        # Endpoints derived from stories / entity
        endpoints.append(ApiEndpointDefinition(
            method=HttpMethod.POST,
            path=f"/api/v1/{table_name}",
            summary=f"Crear un nuevo registro de {ent_name}",
            requestDto=f"Create{ent_name}Request",
            responseDto=f"{ent_name}Response",
            successStatus=201,
            errorStatuses=[400, 500],
            mappedScenarioId="AC-1.1",
        ))
        endpoints.append(ApiEndpointDefinition(
            method=HttpMethod.GET,
            path=f"/api/v1/{table_name}/{{id}}",
            summary=f"Obtener {ent_name} por su identificador ID",
            responseDto=f"{ent_name}Response",
            successStatus=200,
            errorStatuses=[404, 500],
            mappedScenarioId="AC-1.2",
        ))

    components = sanitize_quarkus_components(components)
    mermaid_code = generate_mermaid_flowchart(components, interactions)
    openapi_str = serialize_to_openapi_yaml(service_name, package_name, endpoints, draft.entities or [])

    resp = ArchitectureDesignResponse(
        serviceName=service_name,
        packageName=package_name,
        basePort=draft.basePort or 8080,
        components=components,
        endpoints=endpoints,
        interactions=interactions,
        mermaidDiagram=mermaid_code,
        openapiYaml=openapi_str,
        entities=draft.entities,
        userStories=draft.userStories,
    )
    resp.architectureMarkdown = serialize_architecture_markdown(resp)
    return resp

def design_architecture(
    request: ArchitectureDesignRequest,
    api_key: str,
    provider: Optional[str] = None,
) -> ArchitectureDesignResponse:
    """
    Decomposes a specification draft into formal 4-layer architecture, endpoints, and diagrams.
    Supports free providers (Gemini, Groq), OpenAI, and offline mock mode.
    """
    chosen_provider = provider or getattr(request, "provider", None)
    chosen_model = getattr(request, "modelName", None)

    if LLMFactory.is_mock(api_key, chosen_provider):
        return _generate_mock_architecture(request.draft)

    from langchain_core.messages import SystemMessage, HumanMessage

    llm = LLMFactory.get_chat_model(
        api_key=api_key,
        provider=chosen_provider,
        model_name=chosen_model,
        temperature=0.2,
    )
    if llm is None:
        return _generate_mock_architecture(request.draft)

    structured_llm = llm.with_structured_output(LLMArchitecturePayload)

    system_prompt = (
        "Eres un Arquitecto de Software Empresarial experto especializado en Quarkus 3.x y Java 21 LTS.\n"
        "Tu tarea es analizar historias de usuario BDD, criterios Given/When/Then y entidades de dominio "
        "para diseñar una arquitectura de microservicio modular en 4 capas estrictas conforme a la Constitución del proyecto:\n\n"
        "REGLAS ARQUITECTÓNICAS OBLIGATORIAS Y PROHIBICIONES ESTRICTAS (CERO TOLERANCIA):\n"
        "1. EL FRAMEWORK DEBE SER 100% QUARKUS 3.x Y JAVA 21 LTS.\n"
        "2. NO UTILIZAR DEPENDENCIAS DE SPRING.\n"
        "3. NO UTILIZAR SPRING MVC (usar Quarkus REST con la anotación Jakarta REST @Path).\n"
        "4. NO UTILIZAR SPRING DATA JPA (usar PanacheRepository de Quarkus Hibernate ORM).\n"
        "5. NO PERMITIR DEPENDENCIAS CÍCLICAS ENTRE CAPAS: Flujo estrictamente unidireccional y jerárquico:\n"
        "   - Controllers/Resources (@Path) dependen ÚNICAMENTE de Services.\n"
        "   - Services (@ApplicationScoped) dependen de Repositories y otros Services.\n"
        "   - Repositories (PanacheRepository) dependen ÚNICAMENTE de Domain Entities (@Entity).\n"
        "   - NINGÚN Repository puede depender de Service o Controller.\n"
        "   - NINGÚN Service puede depender de Controller.\n"
        "   - Cero dependencias circulares directas o indirectas.\n"
        "6. ESTEREOTIPOS Y ANOTACIONES PERMITIDOS ÚNICAMENTE:\n"
        "   * Controller: '@Path'\n"
        "   * Service: '@ApplicationScoped'\n"
        "   * Repository: 'PanacheRepository'\n"
        "   * Model: '@Entity'\n"
        "   * Infrastructure: '@ServerExceptionMapper'\n"
        "7. PROHIBIDO TERMINANTEMENTE generar o sugerir cualquier anotación o componente de Spring Boot como @RestController, @Service (Spring), @Repository (Spring), @RestControllerAdvice, @Autowired, JpaRepository o CrudRepository.\n\n"
        "DIRECTRICES DE IDIOMA Y TÉRMINOS TÉCNICOS:\n"
        "- Toda la redacción explicativa, responsabilidades ('responsibilities') y resúmenes de endpoints ('summary') DEBEN ESTAR EN ESPAÑOL.\n"
        "- NO TRADUZCAS los términos técnicos de programación, framework o código; consérvalos intactos en inglés:\n"
        "  * Nombres de clases y componentes (ej: OrderController, OrderService, OrderRepository, GlobalExceptionHandler).\n"
        "  * Identificadores de capa: 'controller', 'service', 'repository', 'model', 'infrastructure'.\n"
        "  * Estereotipos y anotaciones: '@Path', '@ApplicationScoped', 'PanacheRepository', '@Entity', '@ServerExceptionMapper', '@Valid'.\n"
        "  * Métodos HTTP: 'GET', 'POST', 'PUT', 'DELETE', 'PATCH'.\n"
        "  * Tipos de Records y DTOs (ej: CreateOrderRequest, OrderResponse).\n"
        "  * Nombres de tecnologías y especificaciones: 'Quarkus 3.x', 'Java 21', 'Hibernate ORM with Panache', 'RFC 7807 ProblemDetails'.\n\n"
        "GRANULARIDAD DE COMPONENTES:\n"
        "- Un conjunto de componentes por cada Entidad de dominio.\n"
        "- Infrastructure: GlobalExceptionHandler con @ServerExceptionMapper.\n"
        "- REST Endpoints: Deducir endpoints a partir de los escenarios BDD con Java Records DTOs inmutables y códigos de estado HTTP."
    )

    content_summary = (
        f"Service Name: {request.draft.serviceName}\n"
        f"Package Name: {request.draft.packageName}\n"
        f"Entities: {[e.model_dump() for e in request.draft.entities]}\n"
        f"User Stories: {[s.model_dump() for s in request.draft.userStories]}\n"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=content_summary),
    ]

    llm_payload: Optional[LLMArchitecturePayload] = None
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            llm_payload = structured_llm.invoke(messages)
            break
        except Exception as exc:
            err_str = str(exc)
            is_transient = any(
                code in err_str
                for code in ("503", "UNAVAILABLE", "high demand", "429", "RESOURCE_EXHAUSTED", "timeout", "timed out")
            )
            if is_transient and attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            logger.warning(
                f"LLM architecture synthesis failed: {exc}. "
                "Falling back to resilient deterministic Quarkus 3.x architecture synthesis."
            )
            return _generate_mock_architecture(request.draft)

    if llm_payload is None:
        return _generate_mock_architecture(request.draft)

    components: List[ComponentDefinition] = []
    for c in llm_payload.components:
        layer_enum = LayerType(c.layer.lower()) if c.layer.lower() in [l.value for l in LayerType] else LayerType.SERVICE
        pkg = f"{request.draft.packageName}.{layer_enum.value}"
        components.append(ComponentDefinition(
            name=c.name,
            layer=layer_enum,
            stereotype=c.stereotype,
            packageName=pkg,
            responsibilities=c.responsibilities,
            dependencies=c.dependencies,
            mappedStories=c.mappedStories,
        ))

    # Sanitize components to guarantee 100% Quarkus stereotypes and zero circular dependencies
    components = sanitize_quarkus_components(components)

    endpoints: List[ApiEndpointDefinition] = []
    for ep in llm_payload.endpoints:
        method_enum = HttpMethod(ep.method.upper()) if ep.method.upper() in [m.value for m in HttpMethod] else HttpMethod.GET
        endpoints.append(ApiEndpointDefinition(
            method=method_enum,
            path=ep.path,
            summary=ep.summary,
            requestDto=ep.requestDto,
            responseDto=ep.responseDto,
            successStatus=ep.successStatus,
            errorStatuses=ep.errorStatuses,
            mappedScenarioId=ep.mappedScenarioId,
        ))

    # Derive interactions from dependencies
    interactions: List[ComponentInteraction] = []
    comp_map = {c.name: c for c in components}
    for c in components:
        for dep in c.dependencies:
            if dep in comp_map:
                tgt = comp_map[dep]
                inter_type = InteractionType.CALLS
                if tgt.layer == LayerType.MODEL:
                    inter_type = InteractionType.PERSISTS
                interactions.append(ComponentInteraction(sourceComponent=c.name, targetComponent=dep, interactionType=inter_type))

    mermaid_code = generate_mermaid_flowchart(components, interactions)
    openapi_str = serialize_to_openapi_yaml(request.draft.serviceName, request.draft.packageName, endpoints, request.draft.entities)

    resp = ArchitectureDesignResponse(
        serviceName=request.draft.serviceName,
        packageName=request.draft.packageName,
        basePort=request.draft.basePort,
        components=components,
        endpoints=endpoints,
        interactions=interactions,
        mermaidDiagram=mermaid_code,
        openapiYaml=openapi_str,
        entities=request.draft.entities,
        userStories=request.draft.userStories,
    )
    resp.architectureMarkdown = serialize_architecture_markdown(resp)
    return resp

def _apply_mock_refinement(request: ArchitectureRefinementRequest) -> ArchitectureDesignResponse:
    updated_comps = list(request.currentDesign.components)
    updated_interactions = list(request.currentDesign.interactions)

    # Add refined component in service layer
    new_comp_name = "AuditNotificationService"
    if not any(c.name == new_comp_name for c in updated_comps):
        new_comp = ComponentDefinition(
            name=new_comp_name,
            layer=LayerType.SERVICE,
            stereotype="@ApplicationScoped",
            packageName=f"{request.currentDesign.packageName}.service",
            responsibilities=[f"Servicio refinado según solicitud de arquitectura: {request.feedbackPrompt[:40]}"],
            dependencies=[],
            mappedStories=["US-1"],
        )
        updated_comps.append(new_comp)
        # Find a service to connect
        services = [c for c in updated_comps if c.layer == LayerType.SERVICE and c.name != new_comp_name]
        if services:
            services[0].dependencies.append(new_comp_name)
            updated_interactions.append(ComponentInteraction(sourceComponent=services[0].name, targetComponent=new_comp_name, interactionType=InteractionType.CALLS))

    updated_comps = sanitize_quarkus_components(updated_comps)
    mermaid_code = generate_mermaid_flowchart(updated_comps, updated_interactions)
    resp = request.currentDesign.model_copy(update={
        "components": updated_comps,
        "interactions": updated_interactions,
        "mermaidDiagram": mermaid_code,
    })
    resp.architectureMarkdown = serialize_architecture_markdown(resp)
    return resp

def refine_architecture(
    request: ArchitectureRefinementRequest,
    api_key: str,
    provider: Optional[str] = None,
) -> ArchitectureDesignResponse:
    """Applies architectural suggestions or delta feedback to update the architecture design."""
    chosen_provider = provider or getattr(request, "provider", None)
    chosen_model = getattr(request, "modelName", None)

    if LLMFactory.is_mock(api_key, chosen_provider):
        return _apply_mock_refinement(request)

    from langchain_core.messages import SystemMessage, HumanMessage

    llm = LLMFactory.get_chat_model(
        api_key=api_key,
        provider=chosen_provider,
        model_name=chosen_model,
        temperature=0.2,
    )
    if llm is None:
        return _apply_mock_refinement(request)

    structured_llm = llm.with_structured_output(LLMArchitecturePayload)

    system_prompt = (
        "Eres un Arquitecto de Software Empresarial experto en Quarkus 3.x y Java 21 LTS.\n"
        "Se te proporciona un diseño de arquitectura existente y una solicitud de refinamiento.\n"
        "Actualiza el catálogo de componentes y endpoints incorporando las instrucciones solicitadas manteniendo:\n"
        "1. EL FRAMEWORK DEBE SER 100% QUARKUS 3.x Y JAVA 21 LTS.\n"
        "2. NO UTILIZAR DEPENDENCIAS DE SPRING.\n"
        "3. NO UTILIZAR SPRING MVC (usar Quarkus REST con anotación Jakarta REST @Path).\n"
        "4. NO UTILIZAR SPRING DATA JPA (usar PanacheRepository de Quarkus Hibernate ORM).\n"
        "5. NO PERMITIR DEPENDENCIAS CÍCLICAS ENTRE CAPAS: Flujo estrictamente unidireccional (Controller -> Service -> Repository -> Model).\n"
        "6. ESTEREOTIPOS PERMITIDOS: '@Path' (controller), '@ApplicationScoped' (service), 'PanacheRepository' (repository), '@Entity' (model), '@ServerExceptionMapper' (infrastructure).\n"
        "7. PROHIBIDO TERMINANTEMENTE generar anotaciones o estereotipos de Spring (@RestController, @Service, @Repository, @RestControllerAdvice, @Autowired, JpaRepository).\n"
        "8. Toda redacción explicativa y responsabilidades DEBEN ESTAR EN ESPAÑOL, manteniendo términos técnicos en inglés."
    )

    current_summary = (
        f"Components: {[c.model_dump() for c in request.currentDesign.components]}\n"
        f"Endpoints: {[e.model_dump() for e in request.currentDesign.endpoints]}\n"
        f"Feedback: {request.feedbackPrompt}\n"
        f"Target Component: {request.targetComponent or 'GLOBAL'}"
    )

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=current_summary)]
    llm_payload: Optional[LLMArchitecturePayload] = None
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            llm_payload = structured_llm.invoke(messages)
            break
        except Exception as exc:
            err_str = str(exc)
            is_transient = any(
                code in err_str
                for code in ("503", "UNAVAILABLE", "high demand", "429", "RESOURCE_EXHAUSTED", "timeout", "timed out")
            )
            if is_transient and attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            logger.warning(
                f"LLM architecture refinement failed: {exc}. "
                "Falling back to resilient deterministic refinement."
            )
            return _apply_mock_refinement(request)

    if llm_payload is None:
        return _apply_mock_refinement(request)

    components: List[ComponentDefinition] = []
    for c in llm_payload.components:
        layer_enum = LayerType(c.layer.lower()) if c.layer.lower() in [l.value for l in LayerType] else LayerType.SERVICE
        pkg = f"{request.currentDesign.packageName}.{layer_enum.value}"
        components.append(ComponentDefinition(
            name=c.name,
            layer=layer_enum,
            stereotype=c.stereotype,
            packageName=pkg,
            responsibilities=c.responsibilities,
            dependencies=c.dependencies,
            mappedStories=c.mappedStories,
        ))

    # Sanitize components to guarantee 100% Quarkus stereotypes and zero circular dependencies
    components = sanitize_quarkus_components(components)

    endpoints: List[ApiEndpointDefinition] = []
    for ep in llm_payload.endpoints:
        method_enum = HttpMethod(ep.method.upper()) if ep.method.upper() in [m.value for m in HttpMethod] else HttpMethod.GET
        endpoints.append(ApiEndpointDefinition(
            method=method_enum,
            path=ep.path,
            summary=ep.summary,
            requestDto=ep.requestDto,
            responseDto=ep.responseDto,
            successStatus=ep.successStatus,
            errorStatuses=ep.errorStatuses,
            mappedScenarioId=ep.mappedScenarioId,
        ))

    interactions: List[ComponentInteraction] = []
    comp_map = {c.name: c for c in components}
    for c in components:
        for dep in c.dependencies:
            if dep in comp_map:
                interactions.append(ComponentInteraction(sourceComponent=c.name, targetComponent=dep, interactionType=InteractionType.CALLS))

    mermaid_code = generate_mermaid_flowchart(components, interactions)
    openapi_str = serialize_to_openapi_yaml(request.currentDesign.serviceName, request.currentDesign.packageName, endpoints, request.currentDesign.entities)

    resp = ArchitectureDesignResponse(
        serviceName=request.currentDesign.serviceName,
        packageName=request.currentDesign.packageName,
        basePort=request.currentDesign.basePort,
        components=components,
        endpoints=endpoints,
        interactions=interactions,
        mermaidDiagram=mermaid_code,
        openapiYaml=openapi_str,
        entities=request.currentDesign.entities,
        userStories=request.currentDesign.userStories,
    )
    resp.architectureMarkdown = serialize_architecture_markdown(resp)
    return resp

