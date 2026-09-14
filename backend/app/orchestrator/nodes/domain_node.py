from pathlib import Path
from typing import Dict, Any, List
from app.orchestrator.state import GenerationAgentState

def _map_java_type(attr_type: str) -> str:
    t = attr_type.lower()
    if t in ("string", "str", "text"):
        return "String"
    elif t in ("int", "integer"):
        return "Integer"
    elif t in ("long", "id"):
        return "Long"
    elif t in ("double", "float"):
        return "Double"
    elif t in ("decimal", "bigdecimal"):
        return "java.math.BigDecimal"
    elif t in ("boolean", "bool"):
        return "Boolean"
    elif t in ("date", "datetime", "timestamp"):
        return "java.time.LocalDateTime"
    elif t == "uuid":
        return "java.util.UUID"
    return "String"

def domain_node(state: GenerationAgentState) -> Dict[str, Any]:
    blueprint = state.get("blueprint", {})
    package_name = blueprint.get("packageName") or blueprint.get("package_name", "com.corp.service")
    workspace_path = state.get("workspace_path", "./workspaces/sample")
    generated_files = state.get("generated_files", {})
    logs = state.get("logs", [])

    pkg_path = package_name.replace(".", "/")
    entities = blueprint.get("entities", [])

    logs.append(f"[DOMAIN] Synthesizing {len(entities)} JPA entities and Record DTOs")

    for ent in entities:
        ent_name = ent.get("name", "Entity")
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
            is_id = a.get("isPrimaryKey") or a.get("is_identifier", False) or name == "id"
            if is_id:
                jtype = "Long"
            else:
                jtype = _map_java_type(a.get("type", "String"))
            is_required = a.get("required", False) or (not a.get("nullable", True))
            
            field_annotations = []
            if is_id:
                field_annotations.append("    @Id\n    @GeneratedValue(strategy = GenerationType.IDENTITY)")
            else:
                if is_required:
                    if jtype == "String":
                        field_annotations.append("    @NotBlank")
                    else:
                        field_annotations.append("    @NotNull")
            
            ann_str = ("\n".join(field_annotations) + "\n") if field_annotations else ""
            fields_code.append(f"{ann_str}    private {jtype} {name};")
            
            cap_name = name[0].upper() + name[1:]
            getter_setter_code.append(f"""    public {jtype} get{cap_name}() {{
        return {name};
    }}

    public void set{cap_name}({jtype} {name}) {{
        this.{name} = {name};
    }}""")

        entity_src = f"""package {package_name}.model.entity;

import jakarta.persistence.*;
import jakarta.validation.constraints.*;
import java.util.Objects;

@Entity
@Table(name = "{ent_name.lower()}s")
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
        return Objects.equals(id, that.id);
    }}

    @Override
    public int hashCode() {{
        return Objects.hash(id);
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
            ann = "@NotBlank " if (is_req and jtype == "String") else ("@NotNull " if is_req else "")
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
                jtype = "Long"
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
        entity_path = f"src/main/java/{pkg_path}/model/entity/{ent_name}.java"
        create_dto_path = f"src/main/java/{pkg_path}/model/dto/Create{ent_name}Request.java"
        resp_dto_path = f"src/main/java/{pkg_path}/model/dto/{ent_name}Response.java"

        generated_files[entity_path] = entity_src
        generated_files[create_dto_path] = create_dto_src
        generated_files[resp_dto_path] = resp_dto_src

        # Write to disk
        base_dir = Path(workspace_path)
        for p, code in [(entity_path, entity_src), (create_dto_path, create_dto_src), (resp_dto_path, resp_dto_src)]:
            fp = base_dir / p
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(code, encoding="utf-8")

        logs.append(f"[DOMAIN] Generated {ent_name} entity, Create{ent_name}Request record, and {ent_name}Response record")

    return {
        "generated_files": generated_files,
        "logs": logs
    }
