"""Native Quarkus offline generator, restored and wired into the Studio stage boundary."""

from app.orchestrator.stages.deterministic.schema import identifier
from app.services.workspace_guard import io_path
from pathlib import Path
from typing import Dict, Any
from app.orchestrator.state import GenerationAgentState
from app.models.session import SessionPhase

__test__ = False

def _to_pascal_case(text: str) -> str:
    cleaned = text.replace("-", " ").replace("_", " ")
    return "".join(word.capitalize() for word in cleaned.split())

def emit(state: GenerationAgentState) -> Dict[str, Any]:
    from app.services.domain_descriptor import normalize_blueprint
    blueprint = normalize_blueprint(state.get("blueprint", {}))
    state["blueprint"] = blueprint
    package_name = blueprint.get("packageName") or blueprint.get("package_name", "com.corp.service")
    service_name = blueprint.get("serviceName") or blueprint.get("service_name", "sample-service")
    workspace_path = state.get("workspace_path", "./workspaces/sample")
    generated_files = state.get("generated_files", {})
    logs = state.get("logs", [])

    pkg_path = package_name.replace(".", "/")
    entities = blueprint.get("entities", [])
    pascal_name = _to_pascal_case(service_name)
    base_dir = Path(workspace_path)

    # 1. Main Application Test. @QuarkusTest boots the full Quarkus application
    # (CDI, datasource, REST layer) before this class runs, so the assertion
    # itself only needs to confirm the test reached that point -- the real
    # check is that Quarkus started at all.
    app_test = f"""package {package_name};

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertTrue;

@QuarkusTest
class {pascal_name}ApplicationTests {{

    @Test
    void contextLoads() {{
        assertTrue(true, "Quarkus application context boots successfully");
    }}
}}
"""
    app_test_path = f"src/test/java/{pkg_path}/{pascal_name}ApplicationTests.java"
    generated_files[app_test_path] = app_test
    at_fp = base_dir / app_test_path
    io_path(at_fp.parent).mkdir(parents=True, exist_ok=True)
    io_path(at_fp).write_text(app_test, encoding="utf-8")

    # 2. Service Unit Tests with Mockito
    for ent in entities:
        ent_name = ent.get("name", "Entity")
        id_name, id_type = identifier(ent)
        id_cap = id_name[0].upper() + id_name[1:]
        attrs = ent.get("attributes", [])
        non_id_attrs = [a for a in attrs if a.get("name") != id_name]

        valid_id = "java.util.UUID.fromString(\"00000000-0000-0000-0000-000000000001\")" if id_type == "java.util.UUID" else '"key-1"' if id_type == "String" else "1" if id_type == "Integer" else "1L"
        missing_id = "java.util.UUID.fromString(\"00000000-0000-0000-0000-000000000099\")" if id_type == "java.util.UUID" else '"key-99"' if id_type == "String" else "99" if id_type == "Integer" else "99L"

        from app.services.domain_descriptor import sample_expression
        dummy_args = [sample_expression(attribute) for attribute in non_id_attrs]

        args_str = ", ".join(dummy_args)

        test_src = f"""package {package_name}.service;

import {package_name}.model.dto.Create{ent_name}Request;
import {package_name}.model.dto.{ent_name}Response;
import {package_name}.model.entity.{ent_name};
import {package_name}.repository.{ent_name}Repository;
import {package_name}.service.impl.{ent_name}ServiceImpl;
import {package_name}.exception.ResourceNotFoundException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class {ent_name}ServiceTest {{

    @Mock
    private {ent_name}Repository repository;

    @InjectMocks
    private {ent_name}ServiceImpl service;

    private {ent_name} entity;

    @BeforeEach
    void setUp() {{
        entity = new {ent_name}();
        entity.set{id_cap}({valid_id});
    }}

    @Test
    void shouldCreate{ent_name}Successfully() {{
        Create{ent_name}Request request = new Create{ent_name}Request({args_str});
        when(repository.save(any({ent_name}.class))).thenReturn(entity);

        {ent_name}Response response = service.create(request);

        assertNotNull(response);
        assertEquals({valid_id}, response.{id_name}());
        verify(repository, times(1)).save(any({ent_name}.class));
    }}

    @Test
    void shouldFind{ent_name}ByIdSuccessfully() {{
        when(repository.findById({valid_id})).thenReturn(Optional.of(entity));

        {ent_name}Response response = service.findById({valid_id});

        assertNotNull(response);
        assertEquals({valid_id}, response.{id_name}());
        verify(repository, times(1)).findById({valid_id});
    }}

    @Test
    void shouldThrowExceptionWhen{ent_name}NotFound() {{
        when(repository.findById({missing_id})).thenReturn(Optional.empty());

        assertThrows(ResourceNotFoundException.class, () -> service.findById({missing_id}));
        verify(repository, times(1)).findById({missing_id});
    }}

    @Test
    void shouldFindAll{ent_name}s() {{
        when(repository.findAll()).thenReturn(List.of(entity));

        List<{ent_name}Response> list = service.findAll();

        assertNotNull(list);
        assertEquals(1, list.size());
        verify(repository, times(1)).findAll();
    }}

    @Test
    void shouldDelete{ent_name}Successfully() {{
        when(repository.existsById({valid_id})).thenReturn(true);
        doNothing().when(repository).deleteById({valid_id});

        assertDoesNotThrow(() -> service.delete({valid_id}));
        verify(repository, times(1)).deleteById({valid_id});
    }}
}}
"""
        test_path = f"src/test/java/{pkg_path}/service/{ent_name}ServiceTest.java"
        generated_files[test_path] = test_src
        t_fp = base_dir / test_path
        io_path(t_fp.parent).mkdir(parents=True, exist_ok=True)
        io_path(t_fp).write_text(test_src, encoding="utf-8")

        logs.append(f"[TEST] Generated Mockito unit tests for {ent_name}Service")

    return {
        "current_phase": SessionPhase.TEST_SYNTHESIS.value,
        "generated_files": generated_files,
        "logs": logs
    }
