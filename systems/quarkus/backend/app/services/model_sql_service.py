import json
import re
from typing import Any, Dict, List, Optional
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
    from app.models.blueprint import DomainEntity, EntityAttribute
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
    from backend.app.models.blueprint import DomainEntity, EntityAttribute
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
    jt = java_type.strip().rsplit('.',1)[-1].lower()
    if jt in ("long", "bigint"):
        return SqlDataType.BIGINT
    if jt in ("int", "integer"):
        return SqlDataType.INTEGER
    if jt == "double":
        return SqlDataType.DOUBLE
    if jt == "float":
        return SqlDataType.REAL
    if jt in ("bigdecimal", "decimal"):
        return SqlDataType.NUMERIC
    if jt in ("boolean", "bool"):
        return SqlDataType.BOOLEAN
    if jt in ("instant",):
        return SqlDataType.TIMESTAMP_TZ
    if jt in ("localdatetime", "datetime", "timestamp"):
        return SqlDataType.TIMESTAMP
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


def _sql_type(attr, db_engine):
    value = attr.sqlType.value
    if attr.sqlType == SqlDataType.VARCHAR:
        value = f'VARCHAR({attr.length or 255})'
    elif attr.sqlType == SqlDataType.NUMERIC:
        value = 'NUMERIC(19, 2)'
    if db_engine.upper() == 'MYSQL':
        value = value.replace('TIMESTAMP WITH TIME ZONE', 'TIMESTAMP(6)').replace('UUID', 'BINARY(16)')
    return value


def _validate_entities(entities):
    by_name = {e.name: e for e in entities}
    if len(by_name) != len(entities) or len({e.tableName for e in entities}) != len(entities):
        raise ValueError('Entidades o tablas duplicadas')
    for entity in entities:
        identifiers = [entity.name, entity.tableName] + [a.name for a in entity.attributes] + [a.columnName for a in entity.attributes]
        if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value) for value in identifiers):
            raise ValueError('Identificador de modelo invalido')
        if len({a.columnName for a in entity.attributes}) != len(entity.attributes):
            raise ValueError('Columnas duplicadas')
        if len([a for a in entity.attributes if a.isPrimaryKey]) != 1:
            raise ValueError('El perfil local exige una clave primaria simple')
    for entity in entities:
        for rel in entity.relationships:
            if rel.targetEntity not in by_name or rel.sourceEntity != entity.name:
                raise ValueError('Relacion con entidad inexistente o propietario incorrecto')
            if rel.joinColumnName and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', rel.joinColumnName):
                raise ValueError('Columna de relacion invalida')
            if rel.relationshipType == RelationshipType.MANY_TO_MANY and rel.targetEntity == entity.name:
                raise ValueError('Relacion reflexiva MANY_TO_MANY requiere un modelo de enlace explicito')
            if rel.relationshipType == RelationshipType.MANY_TO_MANY and not any(
                    r.relationshipType == RelationshipType.MANY_TO_MANY and r.targetEntity == entity.name
                    for r in by_name[rel.targetEntity].relationships):
                raise ValueError('MANY_TO_MANY exige ambos lados del modelo para definir propietario e inverso')
            if rel.relationshipType in (RelationshipType.MANY_TO_ONE, RelationshipType.ONE_TO_ONE):
                column = rel.joinColumnName or to_snake_case(rel.targetEntity) + '_id'
                scalar = next((a for a in entity.attributes if a.columnName == column), None)
                primary = next(a for a in by_name[rel.targetEntity].attributes if a.isPrimaryKey)
                if scalar and (scalar.sqlType != primary.sqlType or scalar.javaType != primary.javaType
                        or scalar.sqlType == SqlDataType.VARCHAR and (scalar.length or 255) != (primary.length or 255)):
                    raise ValueError('Tipo FK incompatible con la clave primaria destino: ' + column)
    return by_name


def _many_links(entities):
    by_name = {e.name: e for e in entities}
    seen = set()
    for entity in entities:
        for rel in entity.relationships:
            if rel.relationshipType == RelationshipType.MANY_TO_MANY:
                pair = tuple(sorted((entity.name, rel.targetEntity)))
                if pair not in seen:
                    seen.add(pair)
                    yield by_name[pair[0]], by_name[pair[1]]


def generate_schema_sql(entities: List[DomainEntityDefinition], db_engine: str = 'POSTGRESQL') -> str:
    """Generate ANSI/PostgreSQL DDL script compatible with H2 in PostgreSQL mode."""
    if db_engine.upper() not in {'POSTGRESQL', 'MYSQL', 'H2'}:
        raise ValueError('Motor SQL no admitido')
    by_name = _validate_entities(entities)
    statements = [
        "-- ============================================================================",
        "-- Microservice Code Studio: Relational Schema DDL",
        f"-- Dialect: {db_engine.upper()}",
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
                col_type = "NUMERIC(19, 2)"
            if db_engine.upper() == 'MYSQL':
                col_type = col_type.replace('TIMESTAMP WITH TIME ZONE', 'TIMESTAMP(6)').replace('UUID', 'BINARY(16)')

            constraints = []
            if attr.isPrimaryKey:
                identity = f'{col_type} AUTO_INCREMENT PRIMARY KEY' if db_engine.upper() == 'MYSQL' else f'{col_type} GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY'
                constraints.append(identity if attr.sqlType in (SqlDataType.BIGINT, SqlDataType.INTEGER) else f"{col_type} PRIMARY KEY")
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
                guard = '' if db_engine.upper() == 'MYSQL' else 'IF NOT EXISTS '
                indexes.append(f"CREATE INDEX {guard}idx_{table_name}_{attr.columnName} ON {table_name}({attr.columnName});")

        for rel in entity.relationships:
            if rel.relationshipType in (RelationshipType.MANY_TO_ONE, RelationshipType.ONE_TO_ONE):
                column = rel.joinColumnName or to_snake_case(rel.targetEntity) + '_id'
                parent = by_name.get(rel.targetEntity)
                if parent is None:
                    raise ValueError('Relacion con entidad inexistente: ' + rel.targetEntity)
                primary = [a for a in parent.attributes if a.isPrimaryKey]
                if len(primary) != 1:
                    raise ValueError('La relacion exige una clave primaria simple')
                parent_table = parent.tableName
                parent_pk = primary[0]
                scalar = next((a for a in entity.attributes if a.columnName == column), None)
                if scalar is None:
                    fk_type = parent_pk.sqlType.value
                    if parent_pk.sqlType == SqlDataType.VARCHAR:
                        fk_type = f'VARCHAR({parent_pk.length or 255})'
                    if db_engine.upper() == 'MYSQL':
                        fk_type = fk_type.replace('UUID', 'BINARY(16)')
                    col_defs.append(f'    {column} {fk_type} NOT NULL' + (' UNIQUE' if rel.relationshipType == RelationshipType.ONE_TO_ONE else ''))
                elif rel.relationshipType == RelationshipType.ONE_TO_ONE and not scalar.isUnique:
                    col_defs.append(f'    UNIQUE ({column})')
                fk_name = f"fk_{table_name}_{column}"
                foreign_keys.append(
                    f"ALTER TABLE {table_name} ADD CONSTRAINT {fk_name} "
                    f"FOREIGN KEY ({column}) REFERENCES {parent_table}({parent_pk.columnName});"
                )

        table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n" + ",\n".join(col_defs) + "\n);"
        statements.append(table_sql)
        statements.append("")

    for left, right in _many_links(entities):
        table = left.tableName + '_' + right.tableName
        lp = next(a for a in left.attributes if a.isPrimaryKey)
        rp = next(a for a in right.attributes if a.isPrimaryKey)
        lc, rc = to_snake_case(left.name) + '_id', to_snake_case(right.name) + '_id'
        statements.append(f'CREATE TABLE IF NOT EXISTS {table} (\n'
            f'    {lc} {_sql_type(lp, db_engine)} NOT NULL,\n'
            f'    {rc} {_sql_type(rp, db_engine)} NOT NULL,\n'
            f'    PRIMARY KEY ({lc}, {rc}),\n'
            f'    FOREIGN KEY ({lc}) REFERENCES {left.tableName}({lp.columnName}) ON DELETE CASCADE,\n'
            f'    FOREIGN KEY ({rc}) REFERENCES {right.tableName}({rp.columnName}) ON DELETE CASCADE\n);')

    if indexes:
        statements.append("-- Performance Indexes")
        statements.extend(indexes)
        statements.append("")

    if foreign_keys:
        statements.append("-- Referential Foreign Key Constraints")
        statements.extend(foreign_keys)
        statements.append("")

    return "\n".join(statements)


def generate_seed_data_sql(entities: List[DomainEntityDefinition], draft: Optional[SpecificationDraft] = None, db_engine: str = 'POSTGRESQL') -> str:
    """Generate seed DML script populated with sample records derived from domain entities."""
    lines = [
        "-- ============================================================================",
        "-- Microservice Code Studio: Initial Seed Data DML",
        "-- Preconditions and Test Fixtures",
        "-- ============================================================================\n",
    ]

    # Topological order: parent tables first
    by_name = _validate_entities(entities)
    pending, sorted_entities = list(entities), []
    while pending:
        ready = [e for e in pending if all(rel.targetEntity in {v.name for v in sorted_entities}
            for rel in e.relationships if rel.relationshipType in (RelationshipType.MANY_TO_ONE, RelationshipType.ONE_TO_ONE))]
        if not ready:
            raise ValueError('Semillas con ciclo obligatorio o entidad inexistente; defina una migracion de semillas explicita')
        sorted_entities.extend(ready)
        pending = [e for e in pending if e not in ready]
    def foreign_value(target):
        primary = next(a for a in target.attributes if a.isPrimaryKey)
        if primary.sqlType == SqlDataType.UUID:
            return "UNHEX('a00000000000000000000000000000001')" if db_engine.upper() == 'MYSQL' else "'a0000000-0000-0000-0000-000000000001'"
        if primary.sqlType in (SqlDataType.VARCHAR, SqlDataType.TEXT):
            return "'KEY-%s'" % (sorted_entities.index(target) + 1)
        return '1'

    for idx, entity in enumerate(sorted_entities, start=1):
        cols = []
        vals = []
        for attr in entity.attributes:
            if attr.isPrimaryKey and attr.sqlType in (SqlDataType.BIGINT, SqlDataType.INTEGER):
                continue  # Let identity allocate keys; explicit IDs do not advance PostgreSQL sequences.
            if attr.columnName in ("created_at", "updated_at"):
                continue  # Let default timestamp apply
            cols.append(attr.columnName)
            relation = next((r for r in entity.relationships if (r.joinColumnName or to_snake_case(r.targetEntity) + '_id') == attr.columnName
                and r.relationshipType in (RelationshipType.MANY_TO_ONE, RelationshipType.ONE_TO_ONE)), None)
            if relation:
                vals.append(foreign_value(by_name[relation.targetEntity]))
                continue
            if attr.sqlType == SqlDataType.UUID:
                vals.append("UNHEX('a00000000000000000000000000000001')" if db_engine.upper() == 'MYSQL' else "'a0000000-0000-0000-0000-000000000001'")
            elif attr.isPrimaryKey and attr.sqlType in (SqlDataType.VARCHAR, SqlDataType.TEXT):
                vals.append(f"'KEY-{idx}'")
            elif attr.isPrimaryKey:
                vals.append(str(idx))
            elif attr.sqlType in (SqlDataType.BIGINT, SqlDataType.INTEGER):
                vals.append("10" if "qty" in attr.columnName or "quantity" in attr.columnName else "1")
            elif attr.sqlType == SqlDataType.NUMERIC:
                vals.append("99.99")
            elif attr.sqlType == SqlDataType.BOOLEAN:
                vals.append("TRUE")
            elif attr.sqlType == SqlDataType.TIMESTAMP_TZ:
                vals.append('CURRENT_TIMESTAMP')
            elif attr.sqlType == SqlDataType.DATE:
                vals.append("'2026-09-13'")
            else:
                sample_str = f"SAMPLE-{entity.name.upper()}-{idx}" if "number" in attr.columnName or "code" in attr.columnName else f"Test {attr.name.capitalize()}"
                vals.append(f"'{sample_str}'")

        for relation in entity.relationships:
            column = relation.joinColumnName or to_snake_case(relation.targetEntity) + '_id'
            if relation.relationshipType in (RelationshipType.MANY_TO_ONE, RelationshipType.ONE_TO_ONE) and column not in cols:
                cols.append(column)
                vals.append(foreign_value(by_name[relation.targetEntity]))
        if cols:
            lines.append(f"INSERT INTO {entity.tableName} ({', '.join(cols)}) VALUES ({', '.join(vals)});")
        else:
            suffix = '() VALUES ()' if db_engine.upper() == 'MYSQL' else 'DEFAULT VALUES'
            lines.append(f'INSERT INTO {entity.tableName} {suffix};')

    for left, right in _many_links(entities):
        lines.append(f'INSERT INTO {left.tableName}_{right.tableName} '
            f'({to_snake_case(left.name)}_id, {to_snake_case(right.name)}_id) '
            f'VALUES ({foreign_value(left)}, {foreign_value(right)});')
    return "\n".join(lines)


def generate_java_entity_source(entity: DomainEntityDefinition, entities=None) -> str:
    """Generate complete Java 21 JPA entity source code."""
    pkg = entity.packageName or "com.example.service"
    if not pkg.endswith('.model'):
        pkg += '.model'
    lines = [
        f"package {pkg};",
        "",
        "import jakarta.persistence.*;",
        "import jakarta.validation.constraints.*;",
        "import lombok.*;",
        "import java.math.BigDecimal;",
        "import java.time.Instant;",
        "import java.time.LocalDate;",
        "import java.time.LocalDateTime;",
        "import java.util.*;",
        "",
        "/**",
        f" * Domain Entity representing {entity.name}.",
        " * Adheres to Quarkus 3 Jakarta persistence standards.",
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
            if attr.javaType == JavaPropertyType.UUID:
                lines.append("    @GeneratedValue(strategy = GenerationType.UUID)")
            elif attr.javaType in (JavaPropertyType.LONG, JavaPropertyType.INTEGER):
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

        from app.services.domain_descriptor import constraints
        for constraint in constraints({'type':attr.javaType.value, 'nullable':attr.nullable, 'validationRules':attr.validationRules}):
            if '    '+constraint not in annos:
                annos.append('    '+constraint)
        for a in annos:
            lines.append(f"    {a}")
        lines.append(f"    private {attr.javaType.value} {attr.name};")
        lines.append("")

    # Relationships
    for rel in entity.relationships:
        if rel.relationshipType in (RelationshipType.MANY_TO_ONE, RelationshipType.ONE_TO_ONE):
            annotation = 'ManyToOne' if rel.relationshipType == RelationshipType.MANY_TO_ONE else 'OneToOne'
            lines.append(f"    @{annotation}(fetch = FetchType.LAZY)")
            column = rel.joinColumnName or to_snake_case(rel.targetEntity) + '_id'
            shared = ', insertable = false, updatable = false' if any(a.columnName == column for a in entity.attributes) else ''
            unique = ', unique = true' if rel.relationshipType == RelationshipType.ONE_TO_ONE else ''
            lines.append(f'    @JoinColumn(name = "{column}", nullable = false{shared}{unique})')
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

        elif rel.relationshipType == RelationshipType.MANY_TO_MANY:
            prop = to_snake_case(rel.targetEntity) + 's'
            if entity.name < rel.targetEntity:
                # Canonical owner agrees with the SQL join table generator.
                target = next((e for e in (entities or []) if e.name == rel.targetEntity), None)
                target_table = target.tableName if target else to_plural_table_name(rel.targetEntity)
                lines.append('    @ManyToMany(fetch = FetchType.LAZY)')
                lines.append(f'    @JoinTable(name = "{entity.tableName}_{target_table}", '
                    f'joinColumns = @JoinColumn(name = "{to_snake_case(entity.name)}_id"), '
                    f'inverseJoinColumns = @JoinColumn(name = "{to_snake_case(rel.targetEntity)}_id"))')
            else:
                lines.append(f'    @ManyToMany(mappedBy = "{to_snake_case(entity.name)}s", fetch = FetchType.LAZY)')
            lines.extend(['    @Builder.Default', f'    private Set<{rel.targetEntity}> {prop} = new HashSet<>();', ''])

    audit = [a for a in entity.attributes if a.columnName in ('created_at', 'updated_at') and a.javaType == JavaPropertyType.INSTANT]
    if audit:
        lines.extend(['    @PrePersist', '    void initializeTimestamps() {', '        Instant now = Instant.now();'])
        for attr in audit:
            lines.append(f'        if ({attr.name} == null) {attr.name} = now;')
        lines.extend(['    }', ''])
        updated = next((a for a in audit if a.columnName == 'updated_at'), None)
        if updated:
            lines.extend(['    @PreUpdate', f'    void updateTimestamp() {{ {updated.name} = Instant.now(); }}', ''])

    lines.append("}")
    return "\n".join(lines)


def _mock_domain_model_response(draft: SpecificationDraft, db_engine: str = 'POSTGRESQL') -> DataModelSynthesisResponse:
    """Deterministic offline fallback synthesizing entities, DDL, DML, and Java code without network calls."""
    from app.services.domain_descriptor import normalize_blueprint
    from app.models.blueprint import DomainEntity
    normalized=normalize_blueprint(draft.model_dump())
    service_name=draft.serviceName
    package_name=draft.packageName
    raw_entities=[DomainEntity.model_validate(entity) for entity in normalized['entities']]
    if not raw_entities: raise ValueError('El draft debe declarar sus entidades antes de generar Model/SQL')
    entities: List[DomainEntityDefinition]=[]

    for raw_e in raw_entities:
        e_name = raw_e.name
        table_name = getattr(raw_e, 'tableName', None) or to_plural_table_name(e_name)

        raw_attrs = list(getattr(raw_e, "attributes", []))
        pk_attr = next((a for a in raw_attrs if getattr(a, "isPrimaryKey", False) or a.name.lower() == "id"), None)

        attrs: List[EntityAttributeDefinition] = []
        if pk_attr:
            java_pk = JavaPropertyType.LONG
            for jt in JavaPropertyType:
                if jt.value.lower() == pk_attr.type.rsplit('.',1)[-1].lower():
                    java_pk = jt
                    break
            sql_pk = map_java_to_sql_type(pk_attr.type)
            attrs.append(
                EntityAttributeDefinition(
                    name=pk_attr.name,
                    columnName=pk_attr.columnName or to_snake_case(pk_attr.name),
                    javaType=java_pk,
                    sqlType=sql_pk,
                    nullable=False,
                    isPrimaryKey=True,
                    hasIndex=True,
                )
            )
        else:
            attrs.append(
                EntityAttributeDefinition(
                    name="id",
                    columnName="id",
                    javaType=JavaPropertyType.LONG,
                    sqlType=SqlDataType.BIGINT,
                    nullable=False,
                    isPrimaryKey=True,
                    hasIndex=True,
                )
            )

        # Domain fields
        for raw_attr in getattr(raw_e, "attributes", []):
            if getattr(raw_attr, "isPrimaryKey", False):
                continue
            sql_type = map_java_to_sql_type(raw_attr.type)
            java_type = JavaPropertyType.STRING
            for jt in JavaPropertyType:
                if jt.value.lower() == raw_attr.type.rsplit('.',1)[-1].lower():
                    java_type = jt
                    break

            col_name = raw_attr.columnName or to_snake_case(raw_attr.name)
            if any(a.columnName == col_name for a in attrs):
                continue
            is_unique=bool(raw_attr.isUnique)
            attrs.append(
                EntityAttributeDefinition(
                    name=raw_attr.name,
                    columnName=col_name,
                    javaType=java_type,
                    sqlType=sql_type,
                    length=255 if sql_type == SqlDataType.VARCHAR else None,
                    nullable=raw_attr.nullable and not raw_attr.required,
                    isPrimaryKey=False,
                    isUnique=is_unique,
                    validationRules=getattr(raw_attr, "validationRules", []),
                    hasIndex=is_unique or ("status" in col_name),
                )
            )

        # Relationships require an explicit contract; names alone never imply a FK.
        relationships: List[EntityRelationshipDefinition]=[
            EntityRelationshipDefinition(sourceEntity=e_name,targetEntity=attribute.referencesEntity,
                relationshipType=RelationshipType.MANY_TO_ONE,
                joinColumnName=attribute.columnName or to_snake_case(attribute.name),
                cascadeType="PERSIST",fetchType="LAZY")
            for attribute in raw_e.attributes if attribute.referencesEntity
        ]

        # Deduplicate attributes by column name to guarantee uniqueness under all circumstances
        deduped_attrs: List[EntityAttributeDefinition] = []
        seen_cols = set()
        for a in attrs:
            if a.columnName not in seen_cols:
                seen_cols.add(a.columnName)
                deduped_attrs.append(a)
        attrs = deduped_attrs

        entities.append(
            DomainEntityDefinition(
                name=e_name,
                tableName=table_name,
                packageName=f"{package_name}.model",
                attributes=attrs,
                relationships=relationships,
                hasAuditFields=any(attribute.name in {"createdAt","updatedAt"} for attribute in attrs),
            )
        )

    schema_ddl = generate_schema_sql(entities, db_engine)
    seed_dml = generate_seed_data_sql(entities, draft, db_engine)
    mermaid_er = generate_mermaid_er_diagram(entities)

    java_classes = {e.name: generate_java_entity_source(e, entities) for e in entities}

    return DataModelSynthesisResponse(
        serviceName=service_name,
        packageName=package_name,
        entities=entities,
        sqlSchema=SqlSchemaScript(
            schemaDdl=schema_ddl,
            seedDml=seed_dml,
            tableNames=[e.tableName for e in entities],
            dialect=db_engine.lower(),
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
        db_engine: str = "POSTGRESQL",
    ) -> DataModelSynthesisResponse:
        """Synthesize JPA entity models, schema.sql, data.sql, and Mermaid ER diagram."""
        from app.services.injection_guard import assert_no_injection
        assert_no_injection(draft.model_dump(), field="domain model draft")

        if LLMFactory.is_mock(api_key, provider):
            return _mock_domain_model_response(draft, db_engine)

        try:
            llm = LLMFactory.get_chat_model(
                api_key=api_key,
                provider=provider,
                model_name=model_name,
                temperature=0.2,
            )
            if llm is not None:
                from langchain_core.messages import SystemMessage, HumanMessage
                from app.services.structured_output import invoke_structured
                from pydantic import BaseModel, Field

                class LLMAttr(BaseModel):
                    name: str
                    type: str = "String"
                    nullable: bool = False
                    isPrimaryKey: bool = False
                    isUnique: bool = False

                class LLMEntity(BaseModel):
                    name: str
                    tableName: Optional[str] = None
                    attributes: List[LLMAttr] = Field(default_factory=list)

                class LLMModelPayload(BaseModel):
                    entities: List[LLMEntity] = Field(default_factory=list)

                system_prompt = (
                    "You are a Senior Data Architect specializing in Quarkus 3 JPA and PostgreSQL DDL.\n"
                    "Analyze the given specification draft and user stories.\n"
                    "Extract or enrich all domain entities, preserving requested primary key types (e.g. UUID vs Long),\n"
                    "unique business keys (e.g. ISBN, email, SKU, code), and audit fields."
                )
                human_prompt = (
                    f"Service: {draft.serviceName}\n"
                    f"Package: {draft.packageName}\n"
                    f"Draft Entities: {[e.model_dump() for e in draft.entities]}\n"
                    f"User Stories: {[s.model_dump() for s in draft.userStories]}"
                )

                llm_res: LLMModelPayload = invoke_structured(
                    llm,
                    LLMModelPayload,
                    [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)],
                )
                if llm_res and llm_res.entities:
                    enriched_entities = []
                    for le in llm_res.entities:
                        attrs = []
                        for la in le.attributes:
                            attrs.append(EntityAttribute(
                                name=la.name,
                                type=la.type,
                                nullable=la.nullable,
                                isPrimaryKey=la.isPrimaryKey,
                                isUnique=getattr(la, "isUnique", False),
                            ))
                        enriched_entities.append(DomainEntity(
                            name=le.name,
                            tableName=le.tableName or to_plural_table_name(le.name),
                            attributes=attrs,
                        ))
                    if enriched_entities:
                        draft_copy = draft.model_copy(update={"entities": enriched_entities})
                        return _mock_domain_model_response(draft_copy, db_engine)

            raise RuntimeError("The selected provider returned no domain entities")
        except Exception as exc:
            raise RuntimeError("Domain model synthesis failed with the selected provider") from exc

    def refine_domain_models_and_sql(
        self,
        current_response: DataModelSynthesisResponse,
        feedback_prompt: str,
        target_entity: Optional[str] = None,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        db_engine: Optional[str] = None,
    ) -> DataModelSynthesisResponse:
        """Apply user feedback to adjust models, attributes, constraints, or relationships."""
        db_engine = db_engine or (current_response.sqlSchema.dialect.upper() if current_response.sqlSchema.dialect.upper() in {"POSTGRESQL", "MYSQL", "H2"} else "POSTGRESQL")
        from app.services.injection_guard import assert_no_injection
        assert_no_injection(feedback_prompt, field="domain model refinement feedback")

        if not LLMFactory.is_mock(api_key, provider):
            from langchain_core.messages import SystemMessage, HumanMessage
            from app.services.structured_output import invoke_structured
            llm = LLMFactory.get_chat_model(api_key=api_key, provider=provider, model_name=model_name, temperature=0.2)
            if llm is None:
                raise RuntimeError("Selected provider is unavailable")
            refined = invoke_structured(llm, DataModelSynthesisResponse, [
                SystemMessage(content="Refine the supplied domain model using the feedback. Preserve unaffected entities, identifier types and unique constraints. Regenerate consistent JPA classes, SQL and ER diagram. Return the complete structured response."),
                HumanMessage(content=json.dumps({"currentModel": current_response.model_dump(mode="json"), "feedback": feedback_prompt, "targetEntity": target_entity}))])
            if not refined or not refined.entities:
                raise RuntimeError("The selected provider returned no refined entities")
            refined.sqlSchema.schemaDdl = generate_schema_sql(refined.entities, db_engine)
            refined.sqlSchema.seedDml = generate_seed_data_sql(refined.entities, db_engine=db_engine)
            refined.sqlSchema.dialect = db_engine.lower()
            return refined

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
                    validationRules=getattr(raw_attr, "validationRules", []),
                                hasIndex=is_unique or "índice" in prompt_lower or "index" in prompt_lower,
                            )
                        )

        schema_ddl = generate_schema_sql(entities, db_engine)
        seed_dml = generate_seed_data_sql(entities, db_engine=db_engine)
        mermaid_er = generate_mermaid_er_diagram(entities)
        java_classes = {e.name: generate_java_entity_source(e, entities) for e in entities}

        return DataModelSynthesisResponse(
            serviceName=current_response.serviceName,
            packageName=current_response.packageName,
            entities=entities,
            sqlSchema=SqlSchemaScript(
                schemaDdl=schema_ddl,
                seedDml=seed_dml,
                tableNames=[e.tableName for e in entities],
                dialect=db_engine.lower(),
            ),
            mermaidErDiagram=mermaid_er,
            javaEntityClasses=java_classes,
            validationErrors=[],
        )


model_sql_service = ModelSqlService()


# ---------------------------------------------------------------------------
# Fallback DDL from a requirements draft
# ---------------------------------------------------------------------------
#: Java type -> SQL column type. Deliberately small and explicit: an unmapped type
#: becomes TEXT rather than being guessed at, because a wrong numeric type is worse
#: than a permissive one.
_SQL_TYPE_FROM_JAVA = {
    "Long": "BIGINT",
    "long": "BIGINT",
    "Integer": "INTEGER",
    "int": "INTEGER",
    "String": "VARCHAR(255)",
    "BigDecimal": "NUMERIC(19, 2)",
    "Double": "DOUBLE PRECISION",
    "Float": "REAL",
    "Boolean": "BOOLEAN",
    "boolean": "BOOLEAN",
    "LocalDate": "DATE",
    "LocalDateTime": "TIMESTAMP",
    "Instant": "TIMESTAMP WITH TIME ZONE",
    "UUID": "UUID",
    "List<String>": "TEXT",
}


def _snake_case(name: str) -> str:
    """`customerEmail` -> `customer_email`; the convention the emitters use."""
    out = []
    for index, char in enumerate(str(name)):
        if char.isupper() and index and not str(name)[index - 1].isupper():
            out.append("_")
        out.append(char.lower())
    return "".join(out)


def schema_sql_from_draft(draft: Any, db_engine: str = 'POSTGRESQL') -> str:
    """DDL for the entities a requirements draft actually declares.

    This exists for the case where model-backed synthesis fails: a fallback must
    still describe *this* service. A fixed table would contradict the JPA entities
    generated beside it, and under ``ddl-auto: validate`` the application would then
    refuse to start against the database its own schema created.
    """
    from app.services.domain_descriptor import normalize_blueprint
    from app.models.blueprint import DomainEntity
    raw_entities=[]
    for entity in getattr(draft, 'entities', None) or []:
        raw=entity.model_dump() if hasattr(entity, 'model_dump') else vars(entity).copy()
        raw['attributes']=[a.model_dump() if hasattr(a,'model_dump') else vars(a).copy() for a in getattr(entity,'attributes',[]) ]
        raw_entities.append(raw)
    normalized=normalize_blueprint({'packageName':getattr(draft,'packageName','com.corp.service'),'entities':raw_entities})
    normalized_entities=[DomainEntity.model_validate(entity) for entity in normalized['entities']]
    statements = [
        "-- ============================================================================",
        "-- Microservice Code Studio: Relational Schema DDL (fallback from blueprint)",
        f"-- Dialect: {db_engine.upper()}",
        "-- ============================================================================\n",
    ]

    emitted = 0
    for entity in normalized_entities:
        emitted += 1
        table_name = getattr(entity, "tableName", None) or _snake_case(
            getattr(entity, "name", "entity")
        )
        columns = []
        for attribute in getattr(entity, "attributes", None) or []:
            column = getattr(attribute, 'columnName', None) or _snake_case(getattr(attribute, "name", "column"))
            java_type = str(getattr(attribute, "type", "String")).rsplit('.', 1)[-1]
            if getattr(attribute, "isPrimaryKey", False):
                key_type = _SQL_TYPE_FROM_JAVA.get(java_type, 'TEXT')
                if java_type in {'Long', 'long', 'Integer', 'int'}:
                    identity = key_type + (' AUTO_INCREMENT PRIMARY KEY' if db_engine.upper() == 'MYSQL' else ' GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY')
                else:
                    if db_engine.upper() == 'MYSQL':
                        key_type = key_type.replace('UUID', 'BINARY(16)')
                    identity = key_type + ' PRIMARY KEY'
                columns.append(f"    {column} {identity}")
                continue
            sql_type = _SQL_TYPE_FROM_JAVA.get(java_type, "TEXT")
            if db_engine.upper() == 'MYSQL':
                sql_type = sql_type.replace('TIMESTAMP WITH TIME ZONE', 'TIMESTAMP(6)').replace('UUID', 'BINARY(16)')
            constraint = "" if getattr(attribute, "nullable", True) and not getattr(attribute, "required", False) else " NOT NULL"
            if getattr(attribute, 'isUnique', False):
                constraint += ' UNIQUE'
            columns.append(f"    {column} {sql_type}{constraint}")
        if not columns:
            # An entity with no attributes would emit invalid DDL; give it a key.
            identity = 'BIGINT AUTO_INCREMENT PRIMARY KEY' if db_engine.upper() == 'MYSQL' else 'BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY'
            columns.append(f"    id {identity}")
        statements.append(
            f"CREATE TABLE IF NOT EXISTS {table_name} (\n" + ",\n".join(columns) + "\n);"
        )
        statements.append("")

    # Emit all tables first, then explicit constraints, including forward references.
    by_name={entity.name:entity for entity in normalized_entities}
    for entity in normalized_entities:
        for attribute in entity.attributes:
            if not attribute.referencesEntity:
                continue
            target=by_name[attribute.referencesEntity]
            primary=next(item for item in target.attributes if item.isPrimaryKey)
            column=attribute.columnName or _snake_case(attribute.name)
            target_column=primary.columnName or _snake_case(primary.name)
            statements.append(f'ALTER TABLE {entity.tableName} ADD CONSTRAINT fk_{entity.tableName}_{column} '
                f'FOREIGN KEY ({column}) REFERENCES {target.tableName}({target_column});')

    if not emitted:
        statements.append("-- The blueprint declared no entities.\n")
    return "\n".join(statements)
