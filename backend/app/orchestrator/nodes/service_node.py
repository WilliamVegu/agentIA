from pathlib import Path
from typing import Dict, Any
from app.orchestrator.state import GenerationAgentState

def service_node(state: GenerationAgentState) -> Dict[str, Any]:
    blueprint = state.get("blueprint", {})
    package_name = blueprint.get("packageName") or blueprint.get("package_name", "com.corp.service")
    workspace_path = state.get("workspace_path", "./workspaces/sample")
    generated_files = state.get("generated_files", {})
    logs = state.get("logs", [])

    pkg_path = package_name.replace(".", "/")
    entities = blueprint.get("entities", [])
    base_dir = Path(workspace_path)

    # 1. Custom Exception
    not_found_ex = f"""package {package_name}.exception;

public class ResourceNotFoundException extends RuntimeException {{
    public ResourceNotFoundException(String message) {{
        super(message);
    }}
}}
"""
    ex_path = f"src/main/java/{pkg_path}/exception/ResourceNotFoundException.java"
    generated_files[ex_path] = not_found_ex
    fp = base_dir / ex_path
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(not_found_ex, encoding="utf-8")

    for ent in entities:
        ent_name = ent.get("name", "Entity")
        attrs = ent.get("attributes", [])
        non_id_attrs = [a for a in attrs if not (a.get("isPrimaryKey") or a.get("is_identifier") or a.get("name") == "id")]

        # 2. Repository interface
        repo_src = f"""package {package_name}.repository;

import {package_name}.model.entity.{ent_name};
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface {ent_name}Repository extends JpaRepository<{ent_name}, Long> {{
}}
"""
        repo_path = f"src/main/java/{pkg_path}/repository/{ent_name}Repository.java"
        generated_files[repo_path] = repo_src

        # 3. Service Interface
        service_iface = f"""package {package_name}.service;

import {package_name}.model.dto.Create{ent_name}Request;
import {package_name}.model.dto.{ent_name}Response;
import java.util.List;

public interface {ent_name}Service {{
    {ent_name}Response create(Create{ent_name}Request request);
    {ent_name}Response findById(Long id);
    List<{ent_name}Response> findAll();
    void delete(Long id);
}}
"""
        service_path = f"src/main/java/{pkg_path}/service/{ent_name}Service.java"
        generated_files[service_path] = service_iface

        # 4. Service Implementation
        # Setters mapping from DTO
        setters = []
        for a in non_id_attrs:
            aname = a.get("name")
            cap_name = aname[0].upper() + aname[1:]
            setters.append(f"        entity.set{cap_name}(request.{aname}());")

        setters_block = "\n".join(setters)

        service_impl = f"""package {package_name}.service.impl;

import {package_name}.model.dto.Create{ent_name}Request;
import {package_name}.model.dto.{ent_name}Response;
import {package_name}.model.entity.{ent_name};
import {package_name}.repository.{ent_name}Repository;
import {package_name}.service.{ent_name}Service;
import {package_name}.exception.ResourceNotFoundException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
@Transactional
public class {ent_name}ServiceImpl implements {ent_name}Service {{

    private final {ent_name}Repository repository;

    public {ent_name}ServiceImpl({ent_name}Repository repository) {{
        this.repository = repository;
    }}

    @Override
    public {ent_name}Response create(Create{ent_name}Request request) {{
        {ent_name} entity = new {ent_name}();
{setters_block}
        {ent_name} saved = repository.save(entity);
        return {ent_name}Response.fromEntity(saved);
    }}

    @Override
    @Transactional(readOnly = true)
    public {ent_name}Response findById(Long id) {{
        {ent_name} entity = repository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("{ent_name} not found with id: " + id));
        return {ent_name}Response.fromEntity(entity);
    }}

    @Override
    @Transactional(readOnly = true)
    public List<{ent_name}Response> findAll() {{
        return repository.findAll().stream()
                .map({ent_name}Response::fromEntity)
                .collect(Collectors.toList());
    }}

    @Override
    public void delete(Long id) {{
        if (!repository.existsById(id)) {{
            throw new ResourceNotFoundException("{ent_name} not found with id: " + id);
        }}
        repository.deleteById(id);
    }}
}}
"""
        impl_path = f"src/main/java/{pkg_path}/service/impl/{ent_name}ServiceImpl.java"
        generated_files[impl_path] = service_impl

        # Write files to disk
        for p, code in [(repo_path, repo_src), (service_path, service_iface), (impl_path, service_impl)]:
            f_p = base_dir / p
            f_p.parent.mkdir(parents=True, exist_ok=True)
            f_p.write_text(code, encoding="utf-8")

        logs.append(f"[SERVICE] Generated {ent_name}Repository, {ent_name}Service, and {ent_name}ServiceImpl")

    return {
        "generated_files": generated_files,
        "logs": logs
    }
