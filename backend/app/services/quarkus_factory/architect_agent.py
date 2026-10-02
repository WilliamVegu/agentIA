"""
Agente Arquitecto Dinámico e Inteligente (Fábrica de Agentes Quarkus 3.x / Java 21)
Responsabilidades:
1. Evaluar el contrato OpenAPI 3.1 aprobado, el modelo relacional de BD y los requisitos técnicos.
2. Invocar a DeepSeek (o fallback adaptativo de dominio) para proponer 3 opciones arquitectónicas
   (Capas Estándar, Hexagonal DDD, Reactiva Mutiny) adaptadas al dominio exacto del proyecto.
3. Seleccionar y justificar dinámicamente las extensiones oficiales de Quarkus 3.15 LTS necesarias.
4. Generar la previsualización interactiva del arquetipo para Maven (pom.xml) y Gradle (build.gradle)
   con el árbol de directorios real y comandos de ejecución.
5. Proveer recomendaciones de extensiones bajo demanda con IA (Sugerir y Buscar extensiones).
"""

from typing import List, Dict, Any, Tuple, Optional
import json
import re
import os
import yaml

from app.models.quarkus_factory import (
    FactoryOrder,
    ArchitectureProposal,
    ArchitectureOption,
    ArchitecturePatternEnum,
    ArchetypePreview,
    BuildToolEnum,
    DatabaseEnum,
    SecurityEnum,
    QuarkusExtensionItem
)
from app.services.llm_factory import LLMFactory


class ArchitectAgent:

    @staticmethod
    def _extract_main_entity_name(order: FactoryOrder) -> str:
        """Extrae el nombre de la entidad principal a partir de las tablas de BD o del servicio."""
        tables = order.database_model.tables if (order.database_model and order.database_model.tables) else []
        if tables:
            stem = tables[0].name.strip()
            if stem.lower().endswith("es") and len(stem) > 4:
                stem = stem[:-2]
            elif stem.lower().endswith("s") and not stem.lower().endswith("ss") and len(stem) > 3:
                stem = stem[:-1]
            parts = re.split(r'[-_\s]+', stem)
            clean = ''.join(p.capitalize() for p in parts if p)
            if clean:
                return clean

        name_clean = order.basic_data.service_name.replace("-service", "").replace("_service", "")
        parts = re.split(r'[-_\s]+', name_clean)
        clean = ''.join(p.capitalize() for p in parts if p)
        return clean or "Entity"

    @classmethod
    def propose_architecture(
        cls,
        order: FactoryOrder,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Tuple[ArchitectureProposal, int]:
        """
        Genera dinámicamente las 3 opciones de arquitectura, la selección justificada
        de extensiones Quarkus 3.15 LTS y el arquetipo comparativo Maven/Gradle.
        """
        consumed_tokens = 3200
        service_name = order.basic_data.service_name
        group_id = order.basic_data.group_id
        pkg_path = group_id.replace(".", "/")
        main_entity = cls._extract_main_entity_name(order)

        # 1. Intentar generar propuesta arquitectónica con DeepSeek / LLM
        llm_options: Optional[List[ArchitectureOption]] = None
        llm_extensions: Optional[List[QuarkusExtensionItem]] = None

        if not LLMFactory.is_mock(api_key, provider):
            try:
                chat_model = LLMFactory.get_chat_model(
                    api_key=api_key,
                    provider=provider or "deepseek",
                    model_name=model_name or "deepseek-chat",
                    temperature=0.2
                )
                if chat_model:
                    from langchain_core.messages import SystemMessage, HumanMessage

                    # Resumen de tablas y endpoints para contexto del LLM
                    table_names = [t.name for t in (order.database_model.tables if order.database_model else [])]
                    table_summary = ", ".join(table_names) if table_names else "definidas en el contrato"

                    sys_msg = SystemMessage(content=(
                        "Eres el Agente Arquitecto Principal experto en Quarkus 3.x y Java 21 LTS de nivel Enterprise. "
                        "Tu tarea es diseñar la propuesta arquitectónica y seleccionar el conjunto EXACTO de extensiones Quarkus 3.15.1 "
                        "para el microservicio solicitado por el usuario.\n\n"
                        "Debes responder ÚNICAMENTE en JSON válido sin texto adicional ni bloques markdown ```json, con la siguiente estructura:\n"
                        "{\n"
                        '  "options": [\n'
                        "    {\n"
                        '      "id": "layered",\n'
                        '      "title": "Arquitectura en Capas Estándar (Pragmática)",\n'
                        '      "description": "Explicación adaptada al dominio del servicio...",\n'
                        '      "structure_layers": ["capa 1 con clases reales", "capa 2", "capa 3", "capa 4"],\n'
                        '      "pros": ["ventaja 1", "ventaja 2", "ventaja 3"],\n'
                        '      "cons": ["desventaja 1", "desventaja 2"],\n'
                        '      "recommended_for": "Para qué casos en este microservicio...",\n'
                        '      "is_recommended": true\n'
                        "    },\n"
                        "    {\n"
                        '      "id": "hexagonal",\n'
                        '      "title": "Arquitectura Hexagonal / Puertos y Adaptadores (DDD)",\n'
                        '      "description": "...",\n'
                        '      "structure_layers": ["domain/model", "domain/ports/in", "domain/ports/out", "adapters/in/rest", "adapters/out/persistence"],\n'
                        '      "pros": ["..."], "cons": ["..."], "recommended_for": "...", "is_recommended": false\n'
                        "    },\n"
                        "    {\n"
                        '      "id": "reactive",\n'
                        '      "title": "Arquitectura Reactiva / Event-Driven (Mutiny + Kafka)",\n'
                        '      "description": "...",\n'
                        '      "structure_layers": ["resource reactivo", "service reactivo", "messaging", "repository"],\n'
                        '      "pros": ["..."], "cons": ["..."], "recommended_for": "...", "is_recommended": false\n'
                        "    }\n"
                        "  ],\n"
                        '  "extensions": [\n'
                        "    {\n"
                        '      "id": "io.quarkus:quarkus-nombre-extension",\n'
                        '      "name": "Nombre legible",\n'
                        '      "version": "3.15.1",\n'
                        '      "category": "Web & REST | Persistencia | Observabilidad | Seguridad | Mensajería | Validación",\n'
                        '      "description": "Justificación precisa de por qué este microservicio específico necesita esta extensión.",\n'
                        '      "is_selected": true,\n'
                        '      "is_mandatory": false\n'
                        "    }\n"
                        "  ]\n"
                        "}"
                    ))

                    human_msg = HumanMessage(content=(
                        f"Microservicio: {service_name}\n"
                        f"Equipo: {order.basic_data.team}\n"
                        f"Package Group ID: {group_id}\n"
                        f"Descripción del Negocio: {order.business.description}\n"
                        f"Motor de Base de Datos: {getattr(order.technical.database, 'value', str(order.technical.database))}\n"
                        f"Seguridad: {getattr(order.technical.security, 'value', str(order.technical.security))}\n"
                        f"Kafka Habilitado: {order.technical.enable_kafka}\n"
                        f"Tablas diseñadas en BD: {table_summary}\n"
                        f"Entidad principal: {main_entity}\n\n"
                        "Genera las 3 opciones de arquitectura con capas usando los paquetes reales del proyecto y la lista de "
                        "extensiones Quarkus 3.15 LTS rigurosamente justificadas para este problema de negocio."
                    ))

                    resp = chat_model.invoke([sys_msg, human_msg])
                    raw_content = resp.content if hasattr(resp, "content") else str(resp)
                    cleaned_json = re.sub(r'```json\s*', '', raw_content)
                    cleaned_json = re.sub(r'```\s*$', '', cleaned_json).strip()

                    parsed = json.loads(cleaned_json)
                    if "options" in parsed and isinstance(parsed["options"], list) and len(parsed["options"]) == 3:
                        opts = []
                        for opt_data in parsed["options"]:
                            pat_id = ArchitecturePatternEnum(opt_data.get("id", "layered"))
                            opts.append(ArchitectureOption(
                                id=pat_id,
                                title=opt_data.get("title", f"Arquitectura {pat_id.value}"),
                                description=opt_data.get("description", ""),
                                structure_layers=opt_data.get("structure_layers", []),
                                pros=opt_data.get("pros", ["Desarrollo ágil"]),
                                cons=opt_data.get("cons", ["Requiere convención"]),
                                recommended_for=opt_data.get("recommended_for", "Uso general"),
                                is_recommended=opt_data.get("is_recommended", pat_id == ArchitecturePatternEnum.LAYERED)
                            ))
                        llm_options = opts

                    if "extensions" in parsed and isinstance(parsed["extensions"], list) and len(parsed["extensions"]) >= 5:
                        exts = []
                        for ext_data in parsed["extensions"]:
                            ext_id = ext_data.get("id", "").strip()
                            if not ext_id:
                                continue
                            if ":" not in ext_id:
                                ext_id = f"io.quarkus:{ext_id}"
                            exts.append(QuarkusExtensionItem(
                                id=ext_id,
                                name=ext_data.get("name", ext_id.split(":")[-1]),
                                version=ext_data.get("version", "3.15.1"),
                                category=ext_data.get("category", "General"),
                                description=ext_data.get("description", "Extensión seleccionada por IA."),
                                is_selected=ext_data.get("is_selected", True),
                                is_mandatory=ext_data.get("is_mandatory", "resteasy" in ext_id or "health" in ext_id)
                            ))
                        llm_extensions = exts
                        consumed_tokens += 1500
            except Exception as e:
                # Loggear y continuar al fallback adaptativo
                print(f"[ArchitectAgent] Fallback a arquitectura adaptativa: {e}")

        # 2. Si no hubo respuesta del LLM, usar fallback dinámico 100% adaptado al dominio
        if not llm_options:
            llm_options = [
                ArchitectureOption(
                    id=ArchitecturePatternEnum.LAYERED,
                    title="Arquitectura en Capas Estándar (Pragmática)",
                    description=f"Estructura clásica en 3 capas con Panache Active Record/Repository para {service_name}. Mínimo boilerplate y alta velocidad.",
                    structure_layers=[
                        f"src/main/java/{pkg_path}/resource/ ({main_entity}Resource.java)",
                        f"src/main/java/{pkg_path}/service/ ({main_entity}Service.java)",
                        f"src/main/java/{pkg_path}/model/ ({main_entity}.java PanacheEntity)",
                        f"src/main/java/{pkg_path}/dto/ ({main_entity}Request.java, {main_entity}Response.java)"
                    ],
                    pros=[
                        "Desarrollo ágil, familiar y con mínimo código superfluo.",
                        "Integración nativa directa con Quarkus Hibernate ORM con Panache.",
                        "Curva de aprendizaje muy baja para el equipo."
                    ],
                    cons=[
                        "Menor aislamiento estricto si el dominio crece exponencialmente.",
                        "Acoplamiento leve a las anotaciones de persistencia en la entidad."
                    ],
                    recommended_for=f"APIs REST transaccionales de tamaño mediano como {service_name}.",
                    is_recommended=not order.technical.enable_kafka
                ),
                ArchitectureOption(
                    id=ArchitecturePatternEnum.HEXAGONAL,
                    title="Arquitectura Hexagonal / Puertos y Adaptadores (DDD)",
                    description=f"Aislamiento absoluto del núcleo de dominio de {main_entity} mediante puertos (interfaces) y adaptadores (REST, BD, Eventos).",
                    structure_layers=[
                        f"src/main/java/{pkg_path}/domain/model/ ({main_entity} puro sin anotaciones de framework)",
                        f"src/main/java/{pkg_path}/domain/ports/in/ (Create{main_entity}UseCase.java)",
                        f"src/main/java/{pkg_path}/domain/ports/out/ ({main_entity}RepositoryPort.java)",
                        f"src/main/java/{pkg_path}/adapters/in/rest/ ({main_entity}ResourceAdapter.java)",
                        f"src/main/java/{pkg_path}/adapters/out/persistence/ ({main_entity}PanacheAdapter.java)"
                    ],
                    pros=[
                        "Total independencia del framework y tecnologías de base de datos.",
                        "Facilidad suprema para pruebas unitarias de lógica pura sin mocks de BD.",
                        "Excelente mantenibilidad a largo plazo en sistemas empresariales críticos."
                    ],
                    cons=[
                        "Mayor cantidad de clases, DTOs y mappers entre capas.",
                        "Tiempo inicial de síntesis y estructuración ligeramente mayor."
                    ],
                    recommended_for="Servicios con reglas de negocio muy densas o que cambian de infraestructura con frecuencia.",
                    is_recommended=False
                ),
                ArchitectureOption(
                    id=ArchitecturePatternEnum.REACTIVE,
                    title="Arquitectura Reactiva / Event-Driven (Mutiny + Kafka)",
                    description=f"Diseño no bloqueante de extremo a extremo para {service_name} utilizando Quarkus Mutiny (Uni/Multi) y mensajería reactiva.",
                    structure_layers=[
                        f"src/main/java/{pkg_path}/resource/ ({main_entity}ReactiveResource.java retorna Uni<Response>)",
                        f"src/main/java/{pkg_path}/service/ ({main_entity}ReactiveService.java)",
                        f"src/main/java/{pkg_path}/messaging/ ({main_entity}EventConsumer.java @Incoming)",
                        f"src/main/java/{pkg_path}/repository/ (Hibernate Reactive Panache)"
                    ],
                    pros=[
                        "Throughput extremo y consumo mínimo de memoria RAM y threads de SO.",
                        "Integración ideal con brokers de eventos como Apache Kafka.",
                        "Resiliencia nativa ante picos de concurrencia."
                    ],
                    cons=[
                        "Mayor complejidad conceptual al programar con streams reactivos (Mutiny).",
                        "Depuración y stacktraces más complejos en caso de errores en runtime."
                    ],
                    recommended_for="Microservicios con alto volumen de transacciones concurrentes o mensajería asíncrona.",
                    is_recommended=order.technical.enable_kafka
                )
            ]

        if not llm_extensions:
            # Fallback adaptativo de extensiones según características técnicas
            exts = [
                QuarkusExtensionItem(
                    id="io.quarkus:quarkus-resteasy-reactive",
                    name="RESTEasy Reactive",
                    version="3.15.1",
                    category="Web & REST",
                    description=f"Framework REST no bloqueante de alto rendimiento para exponer endpoints de {service_name}.",
                    is_selected=True,
                    is_mandatory=True
                ),
                QuarkusExtensionItem(
                    id="io.quarkus:quarkus-resteasy-reactive-jackson",
                    name="RESTEasy Reactive Jackson",
                    version="3.15.1",
                    category="Web & REST",
                    description="Serialización/deserialización JSON de alta velocidad para DTOs Java Records.",
                    is_selected=True,
                    is_mandatory=False
                ),
                QuarkusExtensionItem(
                    id="io.quarkus:quarkus-hibernate-orm-panache",
                    name="Hibernate ORM con Panache",
                    version="3.15.1",
                    category="Persistencia",
                    description=f"Simplifica el mapeo JPA y persistencia de las entidades de {service_name}.",
                    is_selected=True,
                    is_mandatory=False
                ),
                QuarkusExtensionItem(
                    id="io.quarkus:quarkus-hibernate-validator",
                    name="Hibernate Validator",
                    version="3.15.1",
                    category="Validación",
                    description="Validación declarativa de contratos Jakarta (@NotNull, @NotBlank, @Size, @Email).",
                    is_selected=True,
                    is_mandatory=False
                ),
                QuarkusExtensionItem(
                    id="io.quarkus:quarkus-flyway",
                    name="Flyway Database Migraciones",
                    version="3.15.1",
                    category="Persistencia",
                    description="Control de versiones y migraciones automáticas del esquema relacional DDL.",
                    is_selected=True,
                    is_mandatory=False
                ),
                QuarkusExtensionItem(
                    id="io.quarkus:quarkus-smallrye-openapi",
                    name="SmallRye OpenAPI & Swagger UI",
                    version="3.15.1",
                    category="Documentación & Contrato",
                    description="Expone la especificación OpenAPI 3.1 y la interfaz Swagger UI en /q/swagger-ui.",
                    is_selected=True,
                    is_mandatory=True
                ),
                QuarkusExtensionItem(
                    id="io.quarkus:quarkus-smallrye-health",
                    name="SmallRye Health",
                    version="3.15.1",
                    category="Observabilidad",
                    description="Provee sondas de liveness y readiness para Kubernetes en /q/health.",
                    is_selected=True,
                    is_mandatory=True
                ),
                QuarkusExtensionItem(
                    id="io.quarkus:quarkus-micrometer-registry-prometheus",
                    name="Micrometer Prometheus",
                    version="3.15.1",
                    category="Observabilidad",
                    description="Métricas operativas en formato Prometheus en /q/metrics.",
                    is_selected=True,
                    is_mandatory=False
                ),
                QuarkusExtensionItem(
                    id="io.quarkus:quarkus-opentelemetry",
                    name="OpenTelemetry Tracing",
                    version="3.15.1",
                    category="Observabilidad",
                    description="Trazabilidad distribuida para monitoreo APM transversal.",
                    is_selected=True,
                    is_mandatory=False
                )
            ]

            # Inyectar driver según la base de datos seleccionada
            db_type = order.technical.database
            if db_type == DatabaseEnum.SQLITE:
                exts.append(QuarkusExtensionItem(
                    id="io.quarkus:quarkus-jdbc-sqlite",
                    name="Driver JDBC SQLite",
                    version="3.15.1",
                    category="Persistencia",
                    description="Driver para base de datos SQLite ligera y portable para entornos de desarrollo.",
                    is_selected=True
                ))
            elif db_type in (DatabaseEnum.SQL_SERVER, DatabaseEnum.AZURE_SQL):
                exts.append(QuarkusExtensionItem(
                    id="io.quarkus:quarkus-jdbc-mssql",
                    name="Driver JDBC Microsoft SQL Server",
                    version="3.15.1",
                    category="Persistencia",
                    description="Driver oficial de Microsoft SQL Server para entornos corporativos.",
                    is_selected=True
                ))
            elif db_type == DatabaseEnum.POSTGRESQL:
                exts.append(QuarkusExtensionItem(
                    id="io.quarkus:quarkus-jdbc-postgresql",
                    name="Driver JDBC PostgreSQL",
                    version="3.15.1",
                    category="Persistencia",
                    description="Driver oficial de PostgreSQL de alto rendimiento para producción.",
                    is_selected=True
                ))
            elif db_type == DatabaseEnum.MYSQL:
                exts.append(QuarkusExtensionItem(
                    id="io.quarkus:quarkus-jdbc-mysql",
                    name="Driver JDBC MySQL",
                    version="3.15.1",
                    category="Persistencia",
                    description="Driver de conexión oficial para MySQL.",
                    is_selected=True
                ))

            # Seguridad
            sec_type = order.technical.security
            if sec_type == SecurityEnum.JWT:
                exts.append(QuarkusExtensionItem(
                    id="io.quarkus:quarkus-smallrye-jwt",
                    name="SmallRye JWT RBAC",
                    version="3.15.1",
                    category="Seguridad",
                    description="Validación de tokens JSON Web Tokens (JWT) y autorización por roles (@RolesAllowed).",
                    is_selected=True
                ))
            elif sec_type == SecurityEnum.OIDC:
                exts.append(QuarkusExtensionItem(
                    id="io.quarkus:quarkus-oidc",
                    name="OpenID Connect (OIDC / Keycloak)",
                    version="3.15.1",
                    category="Seguridad",
                    description="Autenticación federada corporativa con Keycloak / Azure AD / Okta.",
                    is_selected=True
                ))

            # Kafka
            if order.technical.enable_kafka:
                exts.append(QuarkusExtensionItem(
                    id="io.quarkus:quarkus-smallrye-reactive-messaging-kafka",
                    name="SmallRye Reactive Messaging Kafka",
                    version="3.15.1",
                    category="Mensajería & Eventos",
                    description="Conector no bloqueante de eventos con Apache Kafka mediante @Incoming/@Outgoing.",
                    is_selected=True
                ))

            llm_extensions = exts

        # 3. Generar previsualizaciones de Maven y Gradle con las extensiones seleccionadas
        maven_preview = cls.generate_archetype_preview(
            order=order,
            pattern=ArchitecturePatternEnum.LAYERED.value,
            build_tool=BuildToolEnum.MAVEN.value,
            extensions=llm_extensions
        )

        gradle_preview = cls.generate_archetype_preview(
            order=order,
            pattern=ArchitecturePatternEnum.LAYERED.value,
            build_tool=BuildToolEnum.GRADLE.value,
            extensions=llm_extensions
        )

        recommended_ext_names = [e.id.split(":")[-1] for e in llm_extensions if e.is_selected]

        proposal = ArchitectureProposal(
            options=llm_options,
            selected_option=ArchitecturePatternEnum.LAYERED,
            recommended_extensions=recommended_ext_names,
            quarkus_extensions=llm_extensions,
            maven_preview=maven_preview,
            gradle_preview=gradle_preview
        )

        return proposal, consumed_tokens

    @classmethod
    def generate_archetype_preview(
        cls,
        order: FactoryOrder,
        pattern: str,
        build_tool: str,
        extensions: List[QuarkusExtensionItem]
    ) -> ArchetypePreview:
        """
        Genera el contenido del archivo de configuración (pom.xml o build.gradle) y
        el árbol de carpetas proyectado según el patrón arquitectónico y las extensiones activas.
        """
        service_name = order.basic_data.service_name
        group_id = order.basic_data.group_id
        pkg_path = group_id.replace(".", "/")
        java_ver = order.basic_data.java_version
        main_entity = cls._extract_main_entity_name(order)

        active_exts = [e for e in extensions if e.is_selected]

        # 1. Árbol de carpetas según el patrón arquitectónico
        if pattern == ArchitecturePatternEnum.HEXAGONAL.value:
            folder_tree = [
                f"{service_name}/",
                f"├── src/main/java/{pkg_path}/",
                f"│   ├── domain/",
                f"│   │   ├── model/                  # {main_entity}.java (Entidad pura sin framework)",
                f"│   │   └── ports/",
                f"│   │       ├── in/                 # Create{main_entity}UseCase.java",
                f"│   │       └── out/                # {main_entity}RepositoryPort.java",
                f"│   ├── application/",
                f"│   │   └── service/                # {main_entity}ApplicationService.java",
                f"│   └── adapters/",
                f"│       ├── in/rest/                # {main_entity}ResourceAdapter.java (JAX-RS)",
                f"│       └── out/persistence/        # {main_entity}PanacheAdapter.java (JPA)",
                f"│   └── dto/                        # Records inmutables para Request/Response",
                f"├── src/main/resources/",
                f"│   ├── application.properties      # Configuración multi-perfil (dev, prod)",
                f"│   ├── openapi/openapi.yaml        # Contrato OpenAPI 3.1 congelado",
                f"│   └── db/migration/V1.0.0__init.sql",
                f"└── src/test/java/{pkg_path}/",
                f"    └── {main_entity}ResourceTest.java  # Pruebas @QuarkusTest"
            ]
        elif pattern == ArchitecturePatternEnum.REACTIVE.value:
            folder_tree = [
                f"{service_name}/",
                f"├── src/main/java/{pkg_path}/",
                f"│   ├── resource/                   # {main_entity}ReactiveResource.java (Uni<Response>)",
                f"│   ├── service/                    # {main_entity}ReactiveService.java (Mutiny Pipelines)",
                f"│   ├── messaging/                  # {main_entity}Consumer.java (@Incoming/@Outgoing)",
                f"│   ├── repository/                 # {main_entity}ReactiveRepository.java",
                f"│   └── dto/                        # Records inmutables para Request/Response",
                f"├── src/main/resources/",
                f"│   ├── application.properties      # Canales Kafka y observabilidad",
                f"│   ├── openapi/openapi.yaml        # Contrato OpenAPI 3.1 congelado",
                f"│   └── db/migration/V1.0.0__init.sql",
                f"└── src/test/java/{pkg_path}/",
                f"    └── {main_entity}ReactiveTest.java"
            ]
        else:
            # Layered estándar
            folder_tree = [
                f"{service_name}/",
                f"├── src/main/java/{pkg_path}/",
                f"│   ├── resource/                   # {main_entity}Resource.java (JAX-RS Endpoints)",
                f"│   ├── service/                    # {main_entity}Service.java (@ApplicationScoped)",
                f"│   ├── model/                      # {main_entity}.java (@Entity Panache)",
                f"│   ├── repository/                 # {main_entity}Repository.java (PanacheRepository)",
                f"│   └── dto/                        # {main_entity}CreateRequest.java, Response",
                f"├── src/main/resources/",
                f"│   ├── application.properties      # Observabilidad SmallRye y perfiles",
                f"│   ├── openapi/openapi.yaml        # Contrato OpenAPI 3.1 congelado",
                f"│   └── db/migration/V1.0.0__init.sql",
                f"└── src/test/java/{pkg_path}/",
                f"    └── {main_entity}ResourceTest.java  # @QuarkusTest RestAssured"
            ]

        # 2. Configuración de Construcción (Maven vs Gradle)
        if build_tool == BuildToolEnum.MAVEN.value or build_tool == "maven":
            config_file_name = "pom.xml"
            deps_xml = []
            for ext in active_exts:
                parts = ext.id.split(":")
                gid = parts[0]
                aid = parts[1] if len(parts) > 1 else parts[0]
                deps_xml.append(f"""    <!-- {ext.name} ({ext.category}) -->
    <dependency>
      <groupId>{gid}</groupId>
      <artifactId>{aid}</artifactId>
    </dependency>""")

            deps_str = "\n".join(deps_xml)

            config_file_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>{group_id}</groupId>
  <artifactId>{service_name}</artifactId>
  <version>1.0.0-SNAPSHOT</version>

  <properties>
    <compiler-plugin.version>3.13.0</compiler-plugin.version>
    <maven.compiler.release>{java_ver}</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <project.reporting.outputEncoding>UTF-8</project.reporting.outputEncoding>
    <quarkus.platform.artifact-id>quarkus-bom</quarkus.platform.artifact-id>
    <quarkus.platform.group-id>io.quarkus.platform</quarkus.platform.group-id>
    <quarkus.platform.version>3.15.1</quarkus.platform.version>
    <surefire-plugin.version>3.3.1</surefire-plugin.version>
  </properties>

  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>${{quarkus.platform.group-id}}</groupId>
        <artifactId>${{quarkus.platform.artifact-id}}</artifactId>
        <version>${{quarkus.platform.version}}</version>
        <type>pom</type>
        <scope>import</scope>
      </dependency>
    </dependencies>
  </dependencyManagement>

  <dependencies>
{deps_str}

    <!-- Pruebas Automatizadas con Quarkus Test -->
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-junit5</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>io.rest-assured</groupId>
      <artifactId>rest-assured</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>

  <build>
    <plugins>
      <plugin>
        <groupId>${{quarkus.platform.group-id}}</groupId>
        <artifactId>quarkus-maven-plugin</artifactId>
        <version>${{quarkus.platform.version}}</version>
        <extensions>true</extensions>
        <executions>
          <execution>
            <goals>
              <goal>build</goal>
              <goal>generate-code</goal>
              <goal>generate-code-tests</goal>
            </goals>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>
</project>
"""
            command_dev = "./mvnw quarkus:dev"
            command_test = "./mvnw test"
        else:
            config_file_name = "build.gradle"
            deps_gradle = []
            for ext in active_exts:
                parts = ext.id.split(":")
                gid = parts[0]
                aid = parts[1] if len(parts) > 1 else parts[0]
                deps_gradle.append(f"    implementation '{gid}:{aid}' // {ext.name}")

            deps_str = "\n".join(deps_gradle)

            config_file_content = f"""plugins {{
    id 'java'
    id 'io.quarkus' version '3.15.1'
}}

repositories {{
    mavenCentral()
    mavenLocal()
}}

dependencies {{
    implementation enforcedPlatform("io.quarkus.platform:quarkus-bom:3.15.1")
{deps_str}

    testImplementation 'io.quarkus:quarkus-junit5'
    testImplementation 'io.rest-assured:rest-assured'
}}

group '{group_id}'
version '1.0.0-SNAPSHOT'

java {{
    sourceCompatibility = JavaVersion.VERSION_{java_ver}
    targetCompatibility = JavaVersion.VERSION_{java_ver}
}}

test {{
    systemProperty "java.util.logging.manager", "org.jboss.logmanager.LogManager"
}}
compileJava {{
    options.encoding = 'UTF-8'
    options.compilerArgs << '-parameters'
}}
"""
            command_dev = "./gradlew --console=plain quarkusDev"
            command_test = "./gradlew test"

        summary_features = [
            f"Herramienta de compilación: {build_tool.upper()}",
            f"Patrón arquitectónico: {pattern.upper()}",
            f"Total extensiones Quarkus 3.15 LTS activas: {len(active_exts)}",
            f"Java Runtime: OpenJDK {java_ver} LTS",
            "Soporte nativo GraalVM listo"
        ]

        return ArchetypePreview(
            build_tool=BuildToolEnum(build_tool),
            config_file_name=config_file_name,
            config_file_content=config_file_content,
            folder_tree=folder_tree,
            command_dev=command_dev,
            command_test=command_test,
            summary_features=summary_features
        )

    @classmethod
    def suggest_quarkus_extension(
        cls,
        order: FactoryOrder,
        query: str,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Consulta con IA a DeepSeek para sugerir o buscar la extensión oficial de Quarkus
        que mejor resuelve la necesidad solicitada por el usuario.
        """
        service_name = order.basic_data.service_name

        if not LLMFactory.is_mock(api_key, provider):
            try:
                chat_model = LLMFactory.get_chat_model(
                    api_key=api_key,
                    provider=provider or "deepseek",
                    model_name=model_name or "deepseek-chat",
                    temperature=0.1
                )
                if chat_model:
                    from langchain_core.messages import SystemMessage, HumanMessage
                    sys_msg = SystemMessage(content=(
                        "Eres un Asesor Técnico de Quarkus 3.x. El usuario te pide una recomendación de extensión oficial de Quarkus. "
                        "Identifica la mejor extensión compatible con Quarkus 3.15 LTS y responde ÚNICAMENTE en JSON con:\n"
                        "{\n"
                        '  "id": "io.quarkus:quarkus-nombre",\n'
                        '  "name": "Nombre amigable",\n'
                        '  "version": "3.15.1",\n'
                        '  "category": "Web & REST | Persistencia | Seguridad | Mensajería | Integración | Observabilidad",\n'
                        '  "description": "Qué hace la extensión",\n'
                        '  "justification": "Por qué es ideal para el pedido del usuario",\n'
                        '  "usage_example": "Fragmento breve de código Java o application.properties"\n'
                        "}"
                    ))
                    human_msg = HumanMessage(content=(
                        f"Microservicio: {service_name}\n"
                        f"Necesidad / Consulta del usuario: {query}"
                    ))
                    resp = chat_model.invoke([sys_msg, human_msg])
                    raw = resp.content if hasattr(resp, "content") else str(resp)
                    cleaned = re.sub(r'```json\s*', '', raw)
                    cleaned = re.sub(r'```\s*$', '', cleaned).strip()
                    data = json.loads(cleaned)
                    return data
            except Exception as e:
                print(f"[ArchitectAgent] Error en sugerencia LLM: {e}")

        # Fallback heurístico inteligente si no hay conexión
        q_lower = query.lower()
        if any(w in q_lower for w in ["mail", "correo", "email", "notific"]):
            return {
                "id": "io.quarkus:quarkus-mailer",
                "name": "Quarkus Mailer",
                "version": "3.15.1",
                "category": "Integración",
                "description": "Envío reactivo y bloqueante de correos electrónicos vía SMTP.",
                "justification": f"Permite a {service_name} enviar alertas y comprobantes por email a los usuarios.",
                "usage_example": "@Inject Mailer mailer;\nmailer.send(Mail.withText(\"destinatario@empresa.com\", \"Asunto\", \"Contenido\"));"
            }
        elif any(w in q_lower for w in ["cache", "redis", "memoria", "rendimiento"]):
            return {
                "id": "io.quarkus:quarkus-cache",
                "name": "Quarkus Cache",
                "version": "3.15.1",
                "category": "Rendimiento",
                "description": "Caché declarativa en memoria mediante anotaciones @CacheResult.",
                "justification": f"Acelera consultas repetitivas de {service_name} sin sobrecargar la base de datos.",
                "usage_example": "@CacheResult(cacheName = \"datos-cache\")\npublic List<Item> listItems() { ... }"
            }
        elif any(w in q_lower for w in ["reloj", "timer", "schedule", "cron", "tarea", "batch"]):
            return {
                "id": "io.quarkus:quarkus-scheduler",
                "name": "Quarkus Scheduler",
                "version": "3.15.1",
                "category": "Automatización",
                "description": "Ejecución programada de tareas con expresiones Cron o intervalos fijos.",
                "justification": f"Automatiza cierres diarios, reportes y verificaciones periódicas en {service_name}.",
                "usage_example": "@Scheduled(cron = \"0 0 1 * * ?\")\nvoid tareaNocturna() { ... }"
            }
        elif any(w in q_lower for w in ["pdf", "reporte", "documento"]):
            return {
                "id": "io.quarkiverse.qute.web:quarkus-qute-web",
                "name": "Quarkus Qute Web",
                "version": "3.15.1",
                "category": "Plantillas",
                "description": "Motor de plantillas tipadas seguro para generación de reportes y HTML/PDF.",
                "justification": f"Generación de reportes dinámicos y comprobantes en {service_name}.",
                "usage_example": "@Inject Template reporteTemplate;\nreturn reporteTemplate.data(\"item\", item).render();"
            }
        else:
            return {
                "id": "io.quarkus:quarkus-smallrye-fault-tolerance",
                "name": "SmallRye Fault Tolerance",
                "version": "3.15.1",
                "category": "Resiliencia",
                "description": "Patrones de Circuit Breaker, Retry, Timeout y Fallback para microservicios.",
                "justification": f"Aumenta la resiliencia de {service_name} ante caídas de dependencias externas.",
                "usage_example": "@Retry(maxRetries = 3, delay = 200)\n@Fallback(fallbackMethod = \"metodoRecuperacion\")\npublic void ejecutarOperacion() { ... }"
            }
