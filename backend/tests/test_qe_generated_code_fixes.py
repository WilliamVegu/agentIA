"""The generated `@NotNull`-on-a-generated-id defect, and its correction.

Found in a deployed service: `POST` returned 500 on every attempt while `GET` worked
and the build was green.

    POST /api/v1/customers -> 500 {"message": "An unexpected error occurred"}
    select count(*) from customers -> 0        (nothing was ever inserted)

The generated entity carried `@NotNull` on a database-generated id. Hibernate runs Bean
Validation before insert, when the id is still null, so the entity was rejected and no
SQL ever ran -- which is why Postgres logged nothing. The blueprint says "id: Long PK
NOT NULL" and the generator emitted `@NotNull`, but a primary key is non-null *in the
table* while `@NotNull` is checked *before* the value exists.

The generated Mockito tests cannot catch it: they mock the repository, so no Hibernate
and no validation run. 21 of them passed on a service whose only write path was broken.
A `@WebMvcTest` would not catch it either -- it mocks the service layer too. The layer
that would is `@DataJpaTest`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.generated_code_fixes import (  # noqa: E402
    fix_generated_id_not_null,
    normalise_generated_entities,
)

BROKEN = """package com.corp.helpdesk.model.entity;

import jakarta.persistence.*;
import jakarta.validation.constraints.*;

@Entity
@Table(name = "customers")
public class Customer {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(nullable = false)
    @NotNull
    private Long id;

    @Column(nullable = false)
    @NotBlank
    private String email;

    @NotNull
    @Column(nullable = false)
    private Instant createdAt;
}
"""


def test_not_null_is_removed_from_a_generated_id():
    corrected, changed = fix_generated_id_not_null(BROKEN)

    assert changed == ["id"]

    id_block = corrected.split("private Long id;")[0].rsplit("@Id", 1)[1]
    assert "@NotNull" not in id_block
    assert "@GeneratedValue" in id_block, "the id must stay database-generated"


def test_a_genuine_required_field_keeps_its_not_null():
    """Only the generated id is exempt; stripping every @NotNull would be a data bug."""
    corrected, _ = fix_generated_id_not_null(BROKEN)

    assert "@NotNull" in corrected.split("private Instant createdAt")[0].rsplit("private Long id;", 1)[-1]
    assert "@NotBlank" in corrected, "unrelated constraints must survive"


def test_the_annotation_that_is_kept_is_untouched():
    corrected, _ = fix_generated_id_not_null(BROKEN)

    assert '@Column(nullable = false)' in corrected
    assert "@GeneratedValue(strategy = GenerationType.IDENTITY)" in corrected


def test_it_is_idempotent():
    once, _ = fix_generated_id_not_null(BROKEN)
    twice, changed = fix_generated_id_not_null(once)

    assert twice == once
    assert changed == []


def test_a_correct_entity_is_returned_byte_identical():
    """The pass runs after every domain stage; it must not churn a healthy tree."""
    healthy = BROKEN.replace("    @NotNull\n    private Long id;", "    private Long id;")

    corrected, changed = fix_generated_id_not_null(healthy)

    assert corrected == healthy
    assert changed == []


def test_a_not_null_on_the_wrong_field_is_not_touched():
    """The block belongs to the field below it -- the bug that shipped once before."""
    source = BROKEN.replace(
        "    @Column(nullable = false)\n    @NotBlank\n    private String email;",
        "    @Column(nullable = false)\n    @NotBlank\n    @NotNull\n    private String email;",
    )

    corrected, changed = fix_generated_id_not_null(source)

    assert changed == ["id"], "only the generated id may be corrected"
    assert corrected.count("@NotNull") == 2, "email's @NotNull was removed by mistake"


# ---------------------------------------------------------------------------
# The workspace pass
# ---------------------------------------------------------------------------
def _entity(tmp_path, name="Customer", body=None):
    path = tmp_path / f"src/main/java/com/corp/x/model/entity/{name}.java"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body if body is not None else BROKEN, encoding="utf-8")
    return path


def test_the_pass_corrects_every_entity(tmp_path):
    _entity(tmp_path, "Customer")
    _entity(tmp_path, "Ticket")

    fixed = normalise_generated_entities(tmp_path)

    assert len(fixed) == 2
    for path in (tmp_path / "src/main/java/com/corp/x/model/entity").glob("*.java"):
        assert "@GeneratedValue" in path.read_text(encoding="utf-8")
        block = path.read_text(encoding="utf-8").split("private Long id;")[0].rsplit("@Id", 1)[1]
        assert "@NotNull" not in block


def test_a_second_pass_changes_nothing(tmp_path):
    _entity(tmp_path)

    normalise_generated_entities(tmp_path)
    before = {p: p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.java")}

    assert normalise_generated_entities(tmp_path) == {}
    assert {p: p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.java")} == before


def test_a_workspace_without_entities_is_not_an_error(tmp_path):
    assert normalise_generated_entities(tmp_path) == {}


def test_a_non_entity_file_is_never_touched(tmp_path):
    """Only `model/entity/*.java`; a controller may legitimately use @NotNull."""
    controller = tmp_path / "src/main/java/com/corp/x/controller/C.java"
    controller.parent.mkdir(parents=True, exist_ok=True)
    controller.write_text(
        "class C {\n    @NotNull\n    private String id;\n}\n", encoding="utf-8"
    )

    assert normalise_generated_entities(tmp_path) == {}
    assert controller.read_text(encoding="utf-8").count("@NotNull") == 1


# ---------------------------------------------------------------------------
# Test annotations the pinned Spring Boot version does not provide
# ---------------------------------------------------------------------------
def test_mockito_bean_is_rewritten_to_mock_bean(tmp_path):
    """`@MockitoBean` arrived in Spring Boot 3.4; this project pins 3.2.3.

    A generated controller test imported
    `org.springframework.test.context.bean.override.mockito.MockitoBean` and failed to
    compile with "package ... does not exist", which consumed the repair budget and
    blocked the session. The instruction set states the rule, but an instruction is a
    request and a model may not follow it.
    """
    from app.services.generated_code_fixes import normalise_generated_tests

    target = tmp_path / "src/test/java/com/corp/x/controller/FooControllerTest.java"
    target.parent.mkdir(parents=True)
    target.write_text(
        "package com.corp.x.controller;\n"
        "import org.springframework.test.context.bean.override.mockito.MockitoBean;\n"
        "@WebMvcTest(FooController.class)\n"
        "class FooControllerTest {\n"
        "    @MockitoBean private FooService service;\n"
        "}\n",
        encoding="utf-8",
    )

    fixed = normalise_generated_tests(tmp_path)

    assert list(fixed) == ["src/test/java/com/corp/x/controller/FooControllerTest.java"]
    text = target.read_text(encoding="utf-8")
    assert "@MockitoBean" not in text
    assert "@MockBean private FooService service;" in text
    assert "import org.springframework.boot.test.mock.mockito.MockBean;" in text, (
        "rewriting only the annotation leaves the unresolvable import behind"
    )


def test_an_existing_mock_bean_is_never_touched():
    """The word boundary matters: `@MockitoBean` must not match inside `@MockBean`."""
    from app.services.generated_code_fixes import fix_spring_test_annotations

    source = "@MockBean private FooService a;\n@MockitoBean private BarService b;\n"

    corrected, changed = fix_spring_test_annotations(source)

    assert corrected.count("@MockBean") == 2
    assert "@MockitoBean" not in corrected
    assert set(changed) == {"@MockitoBean"}


def test_a_correct_test_file_is_byte_identical():
    from app.services.generated_code_fixes import fix_spring_test_annotations

    source = "import org.springframework.boot.test.mock.mockito.MockBean;\n@MockBean private A a;\n"

    assert fix_spring_test_annotations(source) == (source, [])


# ---------------------------------------------------------------------------
# An unmapped path must be answered with 404, not 500
# ---------------------------------------------------------------------------
_ADVICE_WITH_NESTED_RECORD = '''package com.corp.x.controller;

import java.time.Instant;
import java.util.Map;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiError> handleGeneral(Exception ex) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(null);
    }

    public record ApiError(Instant timestamp, int status, String message, Map<String, String> details) {
    }
}
'''


def test_an_unmapped_path_gets_a_404_handler(tmp_path):
    """Measured on a real deployment: `GET /api/borrowers` -> 500, `/api/v1/customers` -> 200.

    An endpoint that does not exist was indistinguishable from a server fault, which is why
    a playground call to the wrong service was diagnosed as a container failure.
    """
    from app.services.generated_code_fixes import ensure_not_found_handler

    target = tmp_path / "src/main/java/com/corp/x/controller/GlobalExceptionHandler.java"
    target.parent.mkdir(parents=True)
    target.write_text(_ADVICE_WITH_NESTED_RECORD, encoding="utf-8")

    changed = ensure_not_found_handler(tmp_path)

    assert list(changed) == ["src/main/java/com/corp/x/controller/GlobalExceptionHandler.java"]
    text = target.read_text(encoding="utf-8")
    assert "NoResourceFoundException" in text
    assert "NOT_FOUND" in text


def test_the_handler_works_with_any_error_type(tmp_path):
    """The model path declares a nested `record ApiError`; the deterministic template uses
    a plain `Map`. A handler naming either would fail to compile in the other, so it uses a
    wildcard return type and a `Map` body, and fully-qualified names so no import is added.
    """
    from app.services.generated_code_fixes import ensure_not_found_handler

    target = tmp_path / "src/main/java/com/corp/x/controller/GlobalExceptionHandler.java"
    target.parent.mkdir(parents=True)
    target.write_text(_ADVICE_WITH_NESTED_RECORD, encoding="utf-8")

    ensure_not_found_handler(tmp_path)
    text = target.read_text(encoding="utf-8")

    assert "ResponseEntity<?>" in text, "must not name the file's own error type"
    assert text.count("{") == text.count("}"), "the insertion must not unbalance the class"
    # No import lines were added: everything is fully qualified.
    assert "import org.springframework.web.servlet" not in text


def test_the_handler_is_inserted_inside_the_class(tmp_path):
    """It must land before the closing brace, not after the file."""
    from app.services.generated_code_fixes import ensure_not_found_handler

    target = tmp_path / "src/main/java/com/corp/x/controller/GlobalExceptionHandler.java"
    target.parent.mkdir(parents=True)
    target.write_text(_ADVICE_WITH_NESTED_RECORD, encoding="utf-8")

    ensure_not_found_handler(tmp_path)
    text = target.read_text(encoding="utf-8")

    assert text.rstrip().endswith("}")
    assert text.index("handleNoResourceFound") < text.rindex("}")


def test_a_deterministic_template_is_left_alone(tmp_path):
    """The deterministic emitter already declares the handler."""
    from app.services.generated_code_fixes import ensure_not_found_handler

    target = tmp_path / "src/main/java/com/corp/x/controller/GlobalExceptionHandler.java"
    target.parent.mkdir(parents=True)
    original = _ADVICE_WITH_NESTED_RECORD.replace(
        "@RestControllerAdvice",
        "@RestControllerAdvice\n// already declares NoResourceFoundException handling",
    )
    target.write_text(original, encoding="utf-8")

    assert ensure_not_found_handler(tmp_path) == {}
    assert target.read_text(encoding="utf-8") == original


def test_a_file_without_the_advice_is_ignored(tmp_path):
    from app.services.generated_code_fixes import ensure_not_found_handler

    target = tmp_path / "src/main/java/com/corp/x/service/ThingService.java"
    target.parent.mkdir(parents=True)
    original = "package com.corp.x.service;\npublic class ThingService {}\n"
    target.write_text(original, encoding="utf-8")

    assert ensure_not_found_handler(tmp_path) == {}
    assert target.read_text(encoding="utf-8") == original


def test_invalid_size_constraint_on_uuid_is_removed():
    from app.services.generated_code_fixes import fix_invalid_type_constraints

    source = """package com.corp.almacen.stock.model.entity;
import jakarta.persistence.*;
import jakarta.validation.constraints.*;
import java.util.UUID;

@Entity
public class Producto {
    @Column(name = "categoria_id")
    @Size(max = 36)
    private UUID categoriaId;

    @NotBlank
    @Size(min = 2, max = 150)
    private String nombre;
}
"""
    corrected, changed = fix_invalid_type_constraints(source)
    assert any("categoriaId" in c for c in changed)
    assert "@Size(max = 36)" not in corrected
    assert "private UUID categoriaId;" in corrected
    assert "@Size(min = 2, max = 150)" in corrected
    assert "@NotBlank" in corrected


def test_invalid_size_constraint_on_record_dto_is_removed():
    from app.services.generated_code_fixes import fix_invalid_type_constraints

    source = """package com.corp.almacen.stock.model.dto;
import jakarta.validation.constraints.*;
import java.util.UUID;

public record CreateProductoRequest(
    @NotBlank
    @Size(min = 4, max = 40)
    String sku,

    @Size(max = 36)
    UUID categoriaId,

    @NotNull
    Boolean activo
) {}
"""
    corrected, changed = fix_invalid_type_constraints(source)
    assert any("categoriaId" in c for c in changed)
    assert "@Size(max = 36)" not in corrected
    assert "UUID categoriaId," in corrected
    assert "@Size(min = 4, max = 40)" in corrected
    assert "@NotBlank" in corrected

