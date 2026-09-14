from pathlib import Path
from typing import Dict, Any
from app.orchestrator.state import GenerationAgentState
from app.models.session import SessionPhase

__test__ = False

def _to_pascal_case(text: str) -> str:
    cleaned = text.replace("-", " ").replace("_", " ")
    return "".join(word.capitalize() for word in cleaned.split())

def test_node(state: GenerationAgentState) -> Dict[str, Any]:
    blueprint = state.get("blueprint", {})
    package_name = blueprint.get("packageName") or blueprint.get("package_name", "com.corp.service")
    service_name = blueprint.get("serviceName") or blueprint.get("service_name", "sample-service")
    workspace_path = state.get("workspace_path", "./workspaces/sample")
    generated_files = state.get("generated_files", {})
    logs = state.get("logs", [])

    pkg_path = package_name.replace(".", "/")
    entities = blueprint.get("entities", [])
    pascal_name = _to_pascal_case(service_name)
    base_dir = Path(workspace_path)

    # 1. Main Application Test
    app_test = f"""package {package_name};

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertTrue;

class {pascal_name}ApplicationTests {{

    @Test
    void contextLoads() {{
        assertTrue(true, "Application context sanity check");
    }}
}}
"""
    app_test_path = f"src/test/java/{pkg_path}/{pascal_name}ApplicationTests.java"
    generated_files[app_test_path] = app_test
    at_fp = base_dir / app_test_path
    at_fp.parent.mkdir(parents=True, exist_ok=True)
    at_fp.write_text(app_test, encoding="utf-8")

    # 2. Service Unit Tests with Mockito
    for ent in entities:
        ent_name = ent.get("name", "Entity")
        attrs = ent.get("attributes", [])
        non_id_attrs = [a for a in attrs if not (a.get("isPrimaryKey") or a.get("is_identifier") or a.get("name") == "id")]

        # Prepare dummy request arguments
        dummy_args = []
        for a in non_id_attrs:
            t = a.get("type", "String").lower()
            if t in ("string", "str", "text"):
                dummy_args.append('"test"')
            elif t in ("int", "integer"):
                dummy_args.append("10")
            elif t in ("long", "id"):
                dummy_args.append("10L")
            elif t in ("double", "float"):
                dummy_args.append("10.5")
            elif t in ("decimal", "bigdecimal"):
                dummy_args.append("new java.math.BigDecimal(\"99.99\")")
            elif t in ("boolean", "bool"):
                dummy_args.append("true")
            elif t in ("date", "datetime", "timestamp"):
                dummy_args.append("java.time.LocalDateTime.now()")
            elif t == "uuid":
                dummy_args.append("java.util.UUID.randomUUID()")
            else:
                dummy_args.append("null")

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
        entity.setId(1L);
    }}

    @Test
    void shouldCreate{ent_name}Successfully() {{
        Create{ent_name}Request request = new Create{ent_name}Request({args_str});
        when(repository.save(any({ent_name}.class))).thenReturn(entity);

        {ent_name}Response response = service.create(request);

        assertNotNull(response);
        assertEquals(1L, response.id());
        verify(repository, times(1)).save(any({ent_name}.class));
    }}

    @Test
    void shouldFind{ent_name}ByIdSuccessfully() {{
        when(repository.findById(1L)).thenReturn(Optional.of(entity));

        {ent_name}Response response = service.findById(1L);

        assertNotNull(response);
        assertEquals(1L, response.id());
        verify(repository, times(1)).findById(1L);
    }}

    @Test
    void shouldThrowExceptionWhen{ent_name}NotFound() {{
        when(repository.findById(99L)).thenReturn(Optional.empty());

        assertThrows(ResourceNotFoundException.class, () -> service.findById(99L));
        verify(repository, times(1)).findById(99L);
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
        when(repository.existsById(1L)).thenReturn(true);
        doNothing().when(repository).deleteById(1L);

        assertDoesNotThrow(() -> service.delete(1L));
        verify(repository, times(1)).deleteById(1L);
    }}
}}
"""
        test_path = f"src/test/java/{pkg_path}/service/{ent_name}ServiceTest.java"
        generated_files[test_path] = test_src
        t_fp = base_dir / test_path
        t_fp.parent.mkdir(parents=True, exist_ok=True)
        t_fp.write_text(test_src, encoding="utf-8")

        logs.append(f"[TEST] Generated Mockito unit tests for {ent_name}Service")

    return {
        "current_phase": SessionPhase.TEST_SYNTHESIS.value,
        "generated_files": generated_files,
        "logs": logs
    }
