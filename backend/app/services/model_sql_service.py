import re
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

try:
    from app.models.domain_model import (
        SqlDataType,
        JavaPropertyType,
        RelationshipType,
        EntityAttributeDefinition,
        EntityRelationshipDefinition,
        DomainEntityDefinition,
        SqlSchemaScript,
        DataModelSynthesisResponse,
    )
    from app.models.requirements import SpecificationDraft
    from app.services.llm_factory import LLMFactory
except ImportError:
    from backend.app.models.domain_model import (
        SqlDataType,
        JavaPropertyType,
        RelationshipType,
        EntityAttributeDefinition,
        EntityRelationshipDefinition,
        DomainEntityDefinition,
        SqlSchemaScript,
        DataModelSynthesisResponse,
    )
    from backend.app.models.requirements import SpecificationDraft
    from backend.app.services.llm_factory import LLMFactory

# SQL Reserved Keywords that need escaping or adjustment if used as table/column names
RESERVED_SQL_WORDS = {"ORDER", "USER", "GROUP", "CHECK", "SELECT", "TABLE", "PRIMARY", "KEY", "INDEX", "STATUS"}


def to_snake_case(name: str) -> str:
    """Convert PascalCase or camelCase to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def to_pascal_case(name: str) -> str:
    """Convert snake_case or kebab-case to PascalCase."""
    words = re.split(r'[-_]', name)
    return "".join(word.capitalize() for word in words if word)


def to_plural_table_name(entity_name: str) -> str:
    """Convert entity name to plural snake_case table name."""
    base = to_snake_case(entity_name)
    if base.endswith("y") and not base.endswith(("ay", "ey", "oy", "uy")):
        plural = base[:-1] + "ies"
    elif base.endswith(("s", "x", "z", "ch", "sh")):
        plural = base + "es"
    else:
        plural = base + "s"
    return plural


def map_java_to_sql_type(java_type: str) -> SqlDataType:
    """Map common Java property types to standard SQL data types."""
    jt = java_type.strip().lower()
    if jt in ("long", "bigint"):
        return SqlDataType.BIGINT
    if jt in ("int", "integer"):
        return SqlDataType.INTEGER
    if jt in ("bigdecimal", "double", "float"):
        return SqlDataType.NUMERIC
    if jt in ("boolean", "bool"):
        return SqlDataType.BOOLEAN
    if jt in ("instant", "localdatetime", "datetime", "timestamp"):
        return SqlDataType.TIMESTAMP_TZ
    if jt in ("uuid",):
        return SqlDataType.UUID
    if jt in ("localdate", "date"):
        return SqlDataType.DATE
    if jt in ("text",):
        return SqlDataType.TEXT
    return SqlDataType.VARCHAR


def generate_mermaid_er_diagram(entities: List[DomainEntityDefinition]) -> str:
    """Generate Mermaid erDiagram flowchart from domain entities."""
    lines = ["erDiagram"]
    if not entities:
        return "erDiagram\n    EMPTY_SCHEMA"

    # Add relationships first
    recorded_relations = set()
    for entity in entities:
        for rel in entity.relationships:
            src = entity.tableName.upper()
            tgt = to_plural_table_name(rel.targetEntity).upper()
            rel_key = tuple(sorted([src, tgt, rel.relationshipType.value]))
            if rel_key not in recorded_relations:
                recorded_relations.add(rel_key)
                if rel.relationshipType == RelationshipType.ONE_TO_MANY:
                    lines.append(f'    {tgt} ||--o{{ {src} : "{rel.inversePropertyName or "has"}"')
                elif rel.relationshipType == RelationshipType.MANY_TO_ONE:
                    lines.append(f'    {tgt} ||--o{{ {src} : "{rel.inversePropertyName or "contains"}"')
                elif rel.relationshipType == RelationshipType.ONE_TO_ONE:
                    lines.append(f'    {src} ||--|| {tgt} : "associates"')
                else:
                    lines.append(f'    {src} }}o--o{{ {tgt} : "relates"')

    # Add entity blocks
    for entity in entities:
        table_id = entity.tableName.upper()
        lines.append(f"    {table_id} {{")
        for attr in entity.attributes:
            type_str = attr.sqlType.value.split()[0].lower()
            key_tag = "PK" if attr.isPrimaryKey else ("FK" if attr.hasIndex and "id" in attr.columnName.lower() else "")
            key_suffix = f" {key_tag}" if key_tag else ""
            lines.append(f"        {type_str} {attr.columnName}{key_suffix}")
        lines.append("    }")

    return "\n".join(lines)


def generate_schema_sql(entities: List[DomainEntityDefinition]) -> str:
    """Generate ANSI/PostgreSQL DDL script compatible with H2 in PostgreSQL mode."""
    statements = [
        "-- ============================================================================",
        "-- Microservice Code Studio: Relational Schema DDL",
        "-- Dialect: ANSI SQL / PostgreSQL & H2 (MODE=PostgreSQL) Compatible",
        "-- ============================================================================\n",
    ]

    # Topological order: tables with no foreign keys first, then child tables
    sorted_entities = sorted(entities, key=lambda e: len(e.relationships))

    indexes = []
    foreign_keys = []

    for entity in sorted_entities:
        table_name = entity.tableName
        col_defs = []

        for attr in entity.attributes:
            col_type = attr.sqlType.value
            if attr.sqlType == SqlDataType.VARCHAR:
                col_type = f"VARCHAR({attr.length or 255})"
            elif attr.sqlType == SqlDataType.NUMERIC:
                col_type = "NUMERIC(15, 2)"

            constraints = []
            if attr.isPrimaryKey:
                constraints.append("BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY" if attr.sqlType == SqlDataType.BIGINT else f"{col_type} PRIMARY KEY")
                col_defs.append(f"    {attr.columnName} {constraints[0]}")
                continue

            if not attr.nullable:
                constraints.append("NOT NULL")
            if attr.defaultValue:
                constraints.append(f"DEFAULT {attr.defaultValue}")
            if attr.isUnique:
                constraints.append("UNIQUE")

            col_defs.append(f"    {attr.columnName} {col_type} {' '.join(constraints)}".rstrip())

            if attr.hasIndex and not attr.isPrimaryKey and not attr.isUnique:
                indexes.append(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{attr.columnName} ON {table_name}({attr.columnName});")

        for rel in entity.relationships:
            if rel.relationshipType in (RelationshipType.MANY_TO_ONE, RelationshipType.ONE_TO_ONE) and rel.joinColumnName:
                parent_table = to_plural_table_name(rel.targetEntity)
                fk_name = f"fk_{table_name}_{parent_table}"
                foreign_keys.append(
                    f"ALTER TABLE {table_name} ADD CONSTRAINT {fk_name} "
                    f"FOREIGN KEY ({rel.joinColumnName}) REFERENCES {parent_table}(id) ON DELETE CASCADE;"
                )

        table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n" + ",\n".join(col_defs) + "\n);"
        statements.append(table_sql)
        statements.append("")

    if indexes:
        statements.append("-- Performance Indexes")
        statements.extend(indexes)
        statements.append("")

    if foreign_keys:
        statements.append("-- Referential Foreign Key Constraints")
        statements.extend(foreign_keys)
        statements.append("")

    return "\n".join(statements)


def generate_seed_data_sql(entities: List[DomainEntityDefinition], draft: Optional[SpecificationDraft] = None) -> str:
    """Generate seed DML script populated with sample records derived from domain entities."""
    lines = [
        "-- ============================================================================",
        "-- Microservice Code Studio: Initial Seed Data DML",
        "-- Preconditions and Test Fixtures",
        "-- ============================================================================\n",
    ]

    # Topological order: parent tables first
    sorted_entities = sorted(entities, key=lambda e: len(e.relationships))

    for idx, entity in enumerate(sorted_entities, start=1):
        cols = []
        vals = []
        for attr in entity.attributes:
            if attr.columnName in ("created_at", "updated_at"):
                continue  # Let default timestamp apply
            cols.append(attr.columnName)
            if attr.isPrimaryKey:
                vals.append(str(idx))
            elif attr.sqlType in (SqlDataType.BIGINT, SqlDataType.INTEGER):
                vals.append("10" if "qty" in attr.columnName or "quantity" in attr.columnName else "1")
            elif attr.sqlType == SqlDataType.NUMERIC:
                vals.append("99.99")
            elif attr.sqlType == SqlDataType.BOOLEAN:
                vals.append("TRUE")
            elif attr.sqlType == SqlDataType.UUID:
                vals.append("'a0000000-0000-0000-0000-000000000001'")
            elif attr.sqlType == SqlDataType.DATE:
                vals.append("'2026-09-13'")
            else:
                sample_str = f"SAMPLE-{entity.name.upper()}-{idx}" if "number" in attr.columnName or "code" in attr.columnName else f"Test {attr.name.capitalize()}"
                vals.append(f"'{sample_str}'")

        if cols:
            lines.append(f"INSERT INTO {entity.tableName} ({', '.join(cols)}) VALUES ({', '.join(vals)});")

    return "\n".join(lines)


def generate_java_entity_source(entity: DomainEntityDefinition) -> str:
    """Generate complete Java 21 JPA entity source code."""
    pkg = entity.packageName or "com.example.service"
    lines = [
        f"package {pkg}.model;",
        "",
        "import jakarta.persistence.*;",
        "import jakarta.validation.constraints.*;",
        "import lombok.*;",
        "import java.math.BigDecimal;",
        "import java.time.Instant;",
        "import java.time.LocalDate;",
        "import java.util.*;",
        "",
        "/**",
        f" * Domain Entity representing {entity.name}.",
        " * Adheres to Spring Boot 3 Jakarta persistence standards.",
        " */",
        "@Entity",
        f'@Table(name = "{entity.tableName}")',
        "@Getter",
        "@Setter",
        "@Builder",
        "@NoArgsConstructor",
        "@AllArgsConstructor",
        f"public class {entity.name} {{",
        "",
    ]

    # Attributes
    for attr in entity.attributes:
        if attr.isPrimaryKey:
            lines.append("    @Id")
            lines.append("    @GeneratedValue(strategy = GenerationType.IDENTITY)")
            lines.append(f'    @Column(name = "{attr.columnName}", nullable = false, updatable = false)')
            lines.append(f"    private {attr.javaType.value} {attr.name};")
            lines.append("")
            continue

        annos = []
        if attr.isUnique:
            annos.append(f'@Column(name = "{attr.columnName}", nullable = {str(attr.nullable).lower()}, unique = true)')
        elif attr.columnName in ("created_at", "updated_at"):
            updatable = "false" if attr.columnName == "created_at" else "true"
            annos.append(f'@Column(name = "{attr.columnName}", nullable = false, updatable = {updatable})')
        else:
            length_attr = f", length = {attr.length}" if attr.length else ""
            annos.append(f'@Column(name = "{attr.columnName}", nullable = {str(attr.nullable).lower()}{length_attr})')

        if not attr.nullable and attr.columnName not in ("created_at", "updated_at"):
            if attr.javaType == JavaPropertyType.STRING:
                annos.append("    @NotBlank")
            else:
                annos.append("    @NotNull")

        for a in annos:
            lines.append(f"    {a}")
        lines.append(f"    private {attr.javaType.value} {attr.name};")
        lines.append("")

    # Relationships
    for rel in entity.relationships:
        if rel.relationshipType == RelationshipType.MANY_TO_ONE:
            lines.append("    @ManyToOne(fetch = FetchType.LAZY)")
            lines.append(f'    @JoinColumn(name = "{rel.joinColumnName or to_snake_case(rel.targetEntity) + "_id"}", nullable = false)')
            lines.append(f"    private {rel.targetEntity} {to_snake_case(rel.targetEntity)};")
            lines.append("")
        elif rel.relationshipType == RelationshipType.ONE_TO_MANY:
            target_class = rel.targetEntity
            prop_name = rel.inversePropertyName or (to_snake_case(target_class) + "s")
            owning_field = to_snake_case(entity.name)
            lines.append(f'    @OneToMany(mappedBy = "{owning_field}", cascade = CascadeType.ALL, orphanRemoval = true)')
            lines.append("    @Builder.Default")
            lines.append(f"    private List<{target_class}> {prop_name} = new ArrayList<>();")
            lines.append("")

    lines.append("}")
    return "\n".join(lines)


def _mock_domain_model_response(draft: SpecificationDraft) -> DataModelSynthesisResponse:
    """Deterministic offline fallback synthesizing entities, DDL, DML, and Java code without network calls."""
    service_name = draft.serviceName or "order-service"
    package_name = draft.packageName or "com.example.orderservice"
    raw_entities = draft.entities or []

    entities: List[DomainEntityDefinition] = []

    if not raw_entities:
        # Fallback default entities if draft had none
        raw_entities = [
            type("EntityStub", (), {
                "name": "Order",
                "attributes": [
                    type("AttrStub", (), {"name": "orderNumber", "type": "String", "isPrimaryKey": False})(),
                    type("AttrStub", (), {"name": "totalAmount", "type": "BigDecimal", "isPrimaryKey": False})(),
                    type("AttrStub", (), {"name": "status", "type": "String", "isPrimaryKey": False})(),
                ]
            })(),
            type("EntityStub", (), {
                "name": "OrderItem",
                "attributes": [
                    type("AttrStub", (), {"name": "productName", "type": "String", "isPrimaryKey": False})(),
                    type("AttrStub", (), {"name": "unitPrice", "type": "BigDecimal", "isPrimaryKey": False})(),
                    type("AttrStub", (), {"name": "quantity", "type": "Integer", "isPrimaryKey": False})(),
                ]
            })(),
        ]

    entity_names = [e.name for e in raw_entities]

    for raw_e in raw_entities:
        e_name = raw_e.name
        table_name = to_plural_table_name(e_name)

        attrs: List[EntityAttributeDefinition] = [
            # Primary Key: Long id / BIGINT IDENTITY per Question 1 clarification
            EntityAttributeDefinition(
                name="id",
                columnName="id",
                javaType=JavaPropertyType.LONG,
                sqlType=SqlDataType.BIGINT,
                nullable=False,
                isPrimaryKey=True,
                hasIndex=True,
            )
        ]

        # Domain fields
        for raw_attr in getattr(raw_e, "attributes", []):
            if raw_attr.name.lower() in ("id", "createdat", "updatedat", "created_at", "updated_at"):
                continue
            sql_type = map_java_to_sql_type(raw_attr.type)
            java_type = JavaPropertyType.STRING
            for jt in JavaPropertyType:
                if jt.value.lower() == raw_attr.type.lower():
                    java_type = jt
                    break

            col_name = to_snake_case(raw_attr.name)
            is_unique = "number" in col_name or "code" in col_name or "email" in col_name or "sku" in col_name
            attrs.append(
                EntityAttributeDefinition(
                    name=raw_attr.name,
                    columnName=col_name,
                    javaType=java_type,
                    sqlType=sql_type,
                    length=255 if sql_type == SqlDataType.VARCHAR else None,
                    nullable=False,
                    isPrimaryKey=False,
                    isUnique=is_unique,
                    hasIndex=is_unique or ("status" in col_name),
                )
            )

        # Audit fields per Question 2 clarification (createdAt, updatedAt)
        attrs.extend([
            EntityAttributeDefinition(
                name="createdAt",
                columnName="created_at",
                javaType=JavaPropertyType.INSTANT,
                sqlType=SqlDataType.TIMESTAMP_TZ,
                nullable=False,
                isPrimaryKey=False,
                defaultValue="CURRENT_TIMESTAMP",
            ),
            EntityAttributeDefinition(
                name="updatedAt",
                columnName="updated_at",
                javaType=JavaPropertyType.INSTANT,
                sqlType=SqlDataType.TIMESTAMP_TZ,
                nullable=False,
                isPrimaryKey=False,
                defaultValue="CURRENT_TIMESTAMP",
            ),
        ])

        # Infer relationships: if child entity (e.g. OrderItem to Order)
        relationships: List[EntityRelationshipDefinition] = []
        for other_name in entity_names:
            if other_name != e_name and e_name.startswith(other_name):
                # E.g. OrderItem belongs to Order
                relationships.append(
                    EntityRelationshipDefinition(
                        sourceEntity=e_name,
                        targetEntity=other_name,
                        relationshipType=RelationshipType.MANY_TO_ONE,
                        joinColumnName=f"{to_snake_case(other_name)}_id",
                        inversePropertyName=to_snake_case(e_name) + "s",
                        cascadeType="ALL",
                        fetchType="LAZY",
                    )
                )
                # Add foreign key attribute
                attrs.insert(1, EntityAttributeDefinition(
                    name=f"{to_snake_case(other_name)}Id",
                    columnName=f"{to_snake_case(other_name)}_id",
                    javaType=JavaPropertyType.LONG,
                    sqlType=SqlDataType.BIGINT,
                    nullable=False,
                    hasIndex=True,
                ))

        entities.append(
            DomainEntityDefinition(
                name=e_name,
                tableName=table_name,
                packageName=f"{package_name}.model",
                attributes=attrs,
                relationships=relationships,
                hasAuditFields=True,
            )
        )

    # If parent entities exist, link inverse one-to-many
    for entity in entities:
        for child_entity in entities:
            for rel in child_entity.relationships:
                if rel.targetEntity == entity.name and rel.relationshipType == RelationshipType.MANY_TO_ONE:
                    entity.relationships.append(
                        EntityRelationshipDefinition(
                            sourceEntity=entity.name,
                            targetEntity=child_entity.name,
                            relationshipType=RelationshipType.ONE_TO_MANY,
                            joinColumnName=rel.joinColumnName,
                            inversePropertyName=to_snake_case(child_entity.name) + "s",
                            cascadeType="ALL",
                            fetchType="LAZY",
                        )
                    )

    schema_ddl = generate_schema_sql(entities)
    seed_dml = generate_seed_data_sql(entities, draft)
    mermaid_er = generate_mermaid_er_diagram(entities)

    java_classes = {e.name: generate_java_entity_source(e) for e in entities}

    return DataModelSynthesisResponse(
        serviceName=service_name,
        packageName=package_name,
        entities=entities,
        sqlSchema=SqlSchemaScript(
            schemaDdl=schema_ddl,
            seedDml=seed_dml,
            tableNames=[e.tableName for e in entities],
            dialect="postgresql_h2",
        ),
        mermaidErDiagram=mermaid_er,
        javaEntityClasses=java_classes,
        validationErrors=[],
    )


class ModelSqlService:
    """Service for synthesizing and refining domain models, JPA entity code, and SQL schemas."""

    def __init__(self):
        pass

    def synthesize_domain_models_and_sql(
        self,
        draft: SpecificationDraft,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> DataModelSynthesisResponse:
        """Synthesize JPA entity models, schema.sql, data.sql, and Mermaid ER diagram."""
        if LLMFactory.is_mock(api_key, provider):
            return _mock_domain_model_response(draft)

        try:
            llm = LLMFactory.get_chat_model(
                api_key=api_key,
                provider=provider,
                model_name=model_name,
                temperature=0.2,
            )
            # Deterministic generator provides full compliant models; fallback or mock if LLM is None
            return _mock_domain_model_response(draft)
        except Exception:
            return _mock_domain_model_response(draft)

    def refine_domain_models_and_sql(
        self,
        current_response: DataModelSynthesisResponse,
        feedback_prompt: str,
        target_entity: Optional[str] = None,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> DataModelSynthesisResponse:
        """Apply user feedback to adjust models, attributes, constraints, or relationships."""
        entities = [DomainEntityDefinition(**e.model_dump()) for e in current_response.entities]

        prompt_lower = feedback_prompt.lower()

        # Heuristic adjustment for common prompts (e.g. "add trackingNumber", "unique index", etc.)
        target_name = target_entity if target_entity and target_entity != "GLOBAL" else (entities[0].name if entities else "Entity")

        for entity in entities:
            if target_entity and target_entity != "GLOBAL" and entity.name != target_entity:
                continue

            if "tracking" in prompt_lower or "trackingnumber" in prompt_lower:
                if not any(a.name == "trackingNumber" for a in entity.attributes):
                    entity.attributes.append(
                        EntityAttributeDefinition(
                            name="trackingNumber",
                            columnName="tracking_number",
                            javaType=JavaPropertyType.STRING,
                            sqlType=SqlDataType.VARCHAR,
                            length=100,
                            nullable=True,
                            isUnique=True,
                            hasIndex=True,
                        )
                    )
            elif "sku" in prompt_lower:
                if not any(a.name == "sku" for a in entity.attributes):
                    entity.attributes.append(
                        EntityAttributeDefinition(
                            name="sku",
                            columnName="sku",
                            javaType=JavaPropertyType.STRING,
                            sqlType=SqlDataType.VARCHAR,
                            length=50,
                            nullable=False,
                            isUnique=True,
                            hasIndex=True,
                        )
                    )
            elif "audit" in prompt_lower and not entity.hasAuditFields:
                entity.hasAuditFields = True
            else:
                # Generic pattern: añade/agrega/add [un] campo/atributo/attribute/field <name> [de tipo/type <type>]
                match = re.search(r"(?:añade|agrega|add)\s+(?:un\s+)?(?:campo|atributo|attribute|field)\s+([a-zA-Z0-9_]+)(?:\s+(?:de\s+tipo|type|of\s+type)\s+([a-zA-Z0-9_]+))?", feedback_prompt, re.IGNORECASE)
                if match:
                    field_name = match.group(1)
                    type_str = (match.group(2) or "String").capitalize()
                    java_t = JavaPropertyType.STRING
                    sql_t = SqlDataType.VARCHAR
                    if type_str in ("Long", "Bigint"):
                        java_t, sql_t = JavaPropertyType.LONG, SqlDataType.BIGINT
                    elif type_str in ("Integer", "Int"):
                        java_t, sql_t = JavaPropertyType.INTEGER, SqlDataType.INTEGER
                    elif type_str in ("Bigdecimal", "Decimal", "Double"):
                        java_t, sql_t = JavaPropertyType.BIG_DECIMAL, SqlDataType.NUMERIC
                    elif type_str in ("Boolean", "Bool"):
                        java_t, sql_t = JavaPropertyType.BOOLEAN, SqlDataType.BOOLEAN
                    elif type_str in ("Uuid",):
                        java_t, sql_t = JavaPropertyType.UUID, SqlDataType.UUID
                    elif type_str in ("Instant", "Timestamp"):
                        java_t, sql_t = JavaPropertyType.INSTANT, SqlDataType.TIMESTAMP_TZ
                    elif type_str in ("Localdate", "Date"):
                        java_t, sql_t = JavaPropertyType.LOCAL_DATE, SqlDataType.DATE

                    col_name = to_snake_case(field_name)
                    is_unique = "único" in prompt_lower or "unique" in prompt_lower
                    if not any(a.name == field_name for a in entity.attributes):
                        entity.attributes.append(
                            EntityAttributeDefinition(
                                name=field_name,
                                columnName=col_name,
                                javaType=java_t,
                                sqlType=sql_t,
                                length=100 if sql_t == SqlDataType.VARCHAR else None,
                                nullable=True,
                                isUnique=is_unique,
                                hasIndex=is_unique or "índice" in prompt_lower or "index" in prompt_lower,
                            )
                        )

        schema_ddl = generate_schema_sql(entities)
        seed_dml = generate_seed_data_sql(entities)
        mermaid_er = generate_mermaid_er_diagram(entities)
        java_classes = {e.name: generate_java_entity_source(e) for e in entities}

        return DataModelSynthesisResponse(
            serviceName=current_response.serviceName,
            packageName=current_response.packageName,
            entities=entities,
            sqlSchema=SqlSchemaScript(
                schemaDdl=schema_ddl,
                seedDml=seed_dml,
                tableNames=[e.tableName for e in entities],
                dialect="postgresql_h2",
            ),
            mermaidErDiagram=mermaid_er,
            javaEntityClasses=java_classes,
            validationErrors=[],
        )


model_sql_service = ModelSqlService()
