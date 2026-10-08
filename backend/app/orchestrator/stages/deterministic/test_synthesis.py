"""Deterministic (offline) implementation of a generation stage.

Moved verbatim from ``app/orchestrator/nodes/test_node.py`` as part of T020.
The f-string logic is unchanged: identical input MUST yield identical output,
identical disk writes, and identical return values. That equivalence is what
keeps the frozen pre-migration baseline a valid comparison target.

The node module of the same name now delegates to the stage execution
boundary, which dispatches here for DETERMINISTIC sessions.
"""

from app.services.workspace_guard import io_path
from pathlib import Path
from typing import Dict, Any
from app.orchestrator.state import GenerationAgentState
from app.orchestrator.stages.deterministic import module_layout
from app.models.session import SessionPhase

__test__ = False

def _to_pascal_case(text: str) -> str:
    cleaned = text.replace("-", " ").replace("_", " ")
    return "".join(word.capitalize() for word in cleaned.split())

#: Java literal for each attribute type the emitters produce. A type that is not here
#: cannot be given a value safely, so the slice test for that entity is SKIPPED rather
#: than emitted uncompilable -- a test that does not compile breaks the build, which is
#: strictly worse than a missing test.
def _sample_expression(java_type: str) -> str | None:
    return {
        "String": '"sample"',
        "Long": "1L", "long": "1L", "Integer": "1", "int": "1",
        "Double": "1.0", "Float": "1.0f", "Boolean": "true", "boolean": "true",
        "BigDecimal": 'new java.math.BigDecimal("1.00")',
        "Instant": "java.time.Instant.now()",
        "LocalDate": "java.time.LocalDate.now()",
        "LocalDateTime": "java.time.LocalDateTime.now()",
        "UUID": "java.util.UUID.randomUUID()",
    }.get(java_type.strip())


def _setter_name(field: str) -> str:
    return "set" + field[:1].upper() + field[1:]


def emit(state: GenerationAgentState) -> Dict[str, Any]:
    from app.services.domain_descriptor import normalize_blueprint
    blueprint = normalize_blueprint(state.get("blueprint", {}))
    state["blueprint"] = blueprint
    package_name = blueprint.get("packageName") or blueprint.get("package_name", "com.corp.service")
    service_name = blueprint.get("serviceName") or blueprint.get("service_name", "sample-service")
    workspace_path = state.get("workspace_path", "./workspaces/sample")
    generated_files = state.get("generated_files", {})
    prefix = module_layout.module_prefix_for("TEST", state.get("architecture_plan"))
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
    app_test_path = f"{prefix}src/test/java/{pkg_path}/{pascal_name}ApplicationTests.java"
    generated_files[app_test_path] = app_test
    at_fp = base_dir / app_test_path
    io_path(at_fp.parent).mkdir(parents=True, exist_ok=True)
    io_path(at_fp).write_text(app_test, encoding="utf-8")

    # 2. Service Unit Tests with Mockito
    for ent in entities:
        ent_name = ent.get("name", "Entity")
        from app.services.domain_descriptor import identifier
        id_name, id_type = identifier(ent)
        id_cap = id_name[0].upper() + id_name[1:]
        valid_id = 'java.util.UUID.fromString("00000000-0000-0000-0000-000000000001")' if id_type == 'java.util.UUID' else '"key-1"' if id_type == 'String' else '1' if id_type == 'Integer' else '1L'
        missing_id = 'java.util.UUID.fromString("00000000-0000-0000-0000-000000000099")' if id_type == 'java.util.UUID' else '"key-99"' if id_type == 'String' else '99' if id_type == 'Integer' else '99L'

        attrs = ent.get("attributes", [])
        non_id_attrs = [a for a in attrs if not (a.get("isPrimaryKey") or a.get("is_identifier") or a.get("name") == "id")]

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
        test_path = f"{prefix}src/test/java/{pkg_path}/service/{ent_name}ServiceTest.java"
        generated_files[test_path] = test_src
        t_fp = base_dir / test_path
        io_path(t_fp.parent).mkdir(parents=True, exist_ok=True)
        io_path(t_fp).write_text(test_src, encoding="utf-8")

        logs.append(f"[TEST] Generated Mockito unit tests for {ent_name}Service")

        plural = ent_name.lower() + "s"

        # 2a. @DataJpaTest -- the ONLY generated test that exercises persistence.
        #
        # The Mockito test above substitutes the repository, so no persistence provider
        # and no pre-insert entity validation runs. A deployed service returned 500 on
        # every POST while its unit suite passed, because the entity carried @NotNull on
        # a database-generated id and Hibernate rejected it before the insert.
        sample_setters, unsupported = [], []
        for attr in non_id_attrs:
            expression = sample_expression(attr)
            if expression is None:
                unsupported.append(str(attr.get("type")))
                continue
            sample_setters.append(f"        entity.{_setter_name(attr.get('name', 'field'))}({expression});")

        if unsupported:
            logs.append(
                f"[TEST] Skipped @DataJpaTest for {ent_name}: no sample value for type(s) "
                f"{', '.join(sorted(set(unsupported)))} -- an uncompilable test would "
                f"break the build"
            )
        else:
            setters_block = "\n".join(sample_setters)
            repo_test = f"""package {package_name}.repository;

import {package_name}.model.entity.{ent_name};
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
class {ent_name}RepositoryTest {{

    @Autowired
    private {ent_name}Repository repository;

    @Test
    void savesAndReadsBackARow() {{
        {ent_name} entity = new {ent_name}();
{setters_block}

        {ent_name} saved = repository.save(entity);

        assertThat(saved.get{id_cap}()).isNotNull();
        assertThat(repository.findById(saved.get{id_cap}())).isPresent();
    }}
}}
"""
            repo_path = f"{prefix}src/test/java/{pkg_path}/repository/{ent_name}RepositoryTest.java"
            generated_files[repo_path] = repo_test
            r_fp = base_dir / repo_path
            io_path(r_fp.parent).mkdir(parents=True, exist_ok=True)
            io_path(r_fp).write_text(repo_test, encoding="utf-8")
            logs.append(f"[TEST] Generated @DataJpaTest repository slice for {ent_name}")

        # 2b. @WebMvcTest -- the transport contract, with the service mocked.
        # @MockBean, not @MockitoBean: this project targets Spring Boot 3.2.3.
        controller_test = f"""package {package_name}.controller;

import {package_name}.service.{ent_name}Service;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest({ent_name}Controller.class)
class {ent_name}ControllerTest {{

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private {ent_name}Service service;

    @Test
    void listingReturns200() throws Exception {{
        given(service.findAll()).willReturn(List.of());

        mockMvc.perform(get("/api/v1/{plural}"))
               .andExpect(status().isOk());
    }}
}}
"""
        ctrl_path = f"{prefix}src/test/java/{pkg_path}/controller/{ent_name}ControllerTest.java"
        generated_files[ctrl_path] = controller_test
        c_fp = base_dir / ctrl_path
        io_path(c_fp.parent).mkdir(parents=True, exist_ok=True)
        io_path(c_fp).write_text(controller_test, encoding="utf-8")
        logs.append(f"[TEST] Generated @WebMvcTest controller slice for {ent_name}")

    return {
        "current_phase": SessionPhase.TEST_SYNTHESIS.value,
        "generated_files": generated_files,
        "logs": logs
    }
