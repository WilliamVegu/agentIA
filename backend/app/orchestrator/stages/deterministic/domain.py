"""Deterministic (offline) implementation of a generation stage.

Originally moved from ``app/orchestrator/nodes/domain_node.py`` as part of T020.
Entity mappings now preserve table/column names and supported Java types so the
generated database migrations can be validated against the actual JPA model.

The node module of the same name now delegates to the stage execution
boundary, which dispatches here for DETERMINISTIC sessions.
"""

from app.services.workspace_guard import io_path
from pathlib import Path
from typing import Dict, Any, List
from app.orchestrator.state import GenerationAgentState
from app.orchestrator.stages.deterministic import module_layout

def _map_java_type(attr_type: str) -> str:
    from app.services.domain_descriptor import java_type
    return java_type(attr_type)

def emit(state: GenerationAgentState) -> Dict[str, Any]:
    from app.services.domain_descriptor import normalize_blueprint
    blueprint = normalize_blueprint(state.get("blueprint", {}))
    state["blueprint"] = blueprint
    package_name = blueprint.get("packageName") or blueprint.get("package_name", "com.corp.service")
    workspace_path = state.get("workspace_path", "./workspaces/sample")
    generated_files = state.get("generated_files", {})
    logs = state.get("logs", [])

    pkg_path = package_name.replace(".", "/")
    entities = blueprint.get("entities", [])
    prefix = module_layout.module_prefix_for("DOMAIN", state.get("architecture_plan"))

    logs.append(f"[DOMAIN] Synthesizing {len(entities)} JPA entities and Record DTOs")

    for ent in entities:
        ent_name = ent.get("name", "Entity")
        from app.services.domain_descriptor import identifier, constraints
        id_name, id_type = identifier(ent)
        from app.services.model_sql_service import to_plural_table_name, to_snake_case
        table_name = ent.get("tableName") or ent.get("table_name") or to_plural_table_name(ent_name)
        attrs = ent.get("attributes", [])
        
        # Ensure 'id' exists
        has_id = any(a.get("name") == "id" or a.get("isPrimaryKey") or a.get("is_identifier") for a in attrs)
        if not has_id:
            attrs = [{"name": "id", "type": "Long", "required": True, "is_identifier": True, "isPrimaryKey": True}] + attrs

        # 1. JPA Entity
        fields_code = []
        getter_setter_code = []
        for a in attrs:
            name = a.get("name")
            is_id = name == id_name
            if is_id:
                jtype = id_type
            else:
                jtype = _map_java_type(a.get("type", "String"))
            is_required = a.get("required", False) or (not a.get("nullable", True))
            
            field_annotations = []
            column_name = a.get('columnName') or to_snake_case(name)
            unique = ', unique = true' if a.get('isUnique') else ''
            precision = ', precision = 19, scale = 2' if jtype == 'java.math.BigDecimal' else ''
            field_annotations.append(f'    @Column(name = "{column_name}", nullable = {str(not (is_required or is_id)).lower()}{unique}{precision})')
            if is_id:
                strategy = "UUID" if id_type in ("java.util.UUID", "String") else "IDENTITY"
                field_annotations.append(f"    @Id\n    @GeneratedValue(strategy = GenerationType.{strategy})")
            else:
                if is_required:
                    if jtype == "String":
                        field_annotations.append("    @NotBlank")
                    else:
                        field_annotations.append("    @NotNull")
            
            if not is_id:
                for rule in constraints(a):
                    if '    '+rule not in field_annotations:
                        field_annotations.append('    '+rule)
            ann_str = ("\n".join(field_annotations) + "\n") if field_annotations else ""
            fields_code.append(f"{ann_str}    private {jtype} {name};")
            
            cap_name = name[0].upper() + name[1:]
            getter_setter_code.append(f"""    public {jtype} get{cap_name}() {{
        return {name};
    }}

    public void set{cap_name}({jtype} {name}) {{
        this.{name} = {name};
    }}""")

        # Keep scalar FK DTO fields and add a read-only association for JPA schema validation.
        for attribute in attrs:
            target=attribute.get('referencesEntity')
            if target:
                column=attribute.get('columnName') or to_snake_case(attribute['name'])
                target_entity=next(entity for entity in entities if entity['name']==target)
                primary=next(item for item in target_entity['attributes'] if item['name']==attribute['referencesAttribute'])
                referenced=primary.get('columnName') or to_snake_case(primary['name'])
                fields_code.append(f'    @ManyToOne(fetch = FetchType.LAZY)\n'
                    f'    @JoinColumn(name = "{column}", referencedColumnName = "{referenced}", insertable = false, updatable = false)\n'
                    f'    private {target} {attribute["name"]}Reference;')

        entity_src = f"""package {package_name}.model.entity;

import jakarta.persistence.*;
import jakarta.validation.constraints.*;
import java.util.Objects;

@Entity
@Table(name = "{table_name}")
public class {ent_name} {{

{chr(10).join(fields_code)}

    public {ent_name}() {{
    }}

{chr(10).join(getter_setter_code)}

    @Override
    public boolean equals(Object o) {{
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        {ent_name} that = ({ent_name}) o;
        return Objects.equals({id_name}, that.{id_name});
    }}

    @Override
    public int hashCode() {{
        return Objects.hash({id_name});
    }}
}}
"""

        # 2. Record DTOs (Principle II)
        # Create Request DTO (excluding id)
        non_id_attrs = [a for a in attrs if not (a.get("isPrimaryKey") or a.get("is_identifier") or a.get("name") == "id")]
        create_params = []
        for a in non_id_attrs:
            jtype = _map_java_type(a.get("type", "String"))
            is_req = a.get("required", False) or (not a.get("nullable", True))
            ann = " ".join(constraints(a)) + (" " if constraints(a) else "")
            create_params.append(f"{ann}{jtype} {a.get('name')}")

        create_dto_src = f"""package {package_name}.model.dto;

import jakarta.validation.constraints.*;

public record Create{ent_name}Request(
    {f',{chr(10)}    '.join(create_params)}
) {{}}
"""

        # Response DTO
        resp_params = []
        from_entity_mappings = []
        for a in attrs:
            aname = a.get("name")
            is_id = a.get("isPrimaryKey") or a.get("is_identifier", False) or aname == "id"
            if is_id:
                jtype = id_type
            else:
                jtype = _map_java_type(a.get("type", "String"))
            cap_name = aname[0].upper() + aname[1:]
            resp_params.append(f"{jtype} {aname}")
            from_entity_mappings.append(f"entity.get{cap_name}()")

        resp_dto_src = f"""package {package_name}.model.dto;

import {package_name}.model.entity.{ent_name};

public record {ent_name}Response(
    {f',{chr(10)}    '.join(resp_params)}
) {{
    public static {ent_name}Response fromEntity({ent_name} entity) {{
        if (entity == null) return null;
        return new {ent_name}Response(
            {f',{chr(10)}            '.join(from_entity_mappings)}
        );
    }}
}}
"""

        # Record files in map
        entity_path = f"{prefix}src/main/java/{pkg_path}/model/entity/{ent_name}.java"
        create_dto_path = f"{prefix}src/main/java/{pkg_path}/model/dto/Create{ent_name}Request.java"
        resp_dto_path = f"{prefix}src/main/java/{pkg_path}/model/dto/{ent_name}Response.java"

        generated_files[entity_path] = entity_src
        generated_files[create_dto_path] = create_dto_src
        generated_files[resp_dto_path] = resp_dto_src

        # Write to disk
        base_dir = Path(workspace_path)
        for p, code in [(entity_path, entity_src), (create_dto_path, create_dto_src), (resp_dto_path, resp_dto_src)]:
            fp = base_dir / p
            io_path(fp.parent).mkdir(parents=True, exist_ok=True)
            io_path(fp).write_text(code, encoding="utf-8")

        logs.append(f"[DOMAIN] Generated {ent_name} entity, Create{ent_name}Request record, and {ent_name}Response record")

    return {
        "generated_files": generated_files,
        "logs": logs
    }
