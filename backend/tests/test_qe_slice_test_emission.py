"""The generated suite must include the layers that can actually see persistence.

Two real failures motivated this, and both shipped green:

1. A deployed service returned 500 on every `POST` while `GET` worked. The generated
   entity carried `@NotNull` on a database-generated id, so Hibernate's pre-insert Bean
   Validation rejected it and no SQL ever ran. **The Mockito unit tests passed** -- they
   substitute the repository, so no persistence provider and no validation runs. A
   `@DataJpaTest` is the only generated layer that calls `save()` for real.
2. The generated handler returned a tidy error envelope and logged nothing, so the
   failure was undiagnosable until the annotation was found by hand.

**What these tests establish, and what they do not.** They assert the emitted source
contains the right annotations, paths and imports, and that a legitimate slice test is
not rejected by the compliance gate. They do NOT establish that the Java compiles: no
JDK or Maven is available to this suite, and the frozen offline baseline never compiled
anything either (`capture_conditions.sandbox_verifier_invoked` is false in the artifact).
Compilation is verified by the hermetic sandbox, which is a container.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "backend/tests"))

from test_generation_stages_offline import CORPUS_DIR, _run_offline  # noqa: E402


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    workspace = tmp_path_factory.mktemp("slice") / "svc"
    workspace.mkdir()
    blueprint = json.loads((CORPUS_DIR / "minimal.json").read_text(encoding="utf-8"))
    _run_offline(blueprint, workspace)
    return workspace


def test_a_data_jpa_slice_is_emitted_per_entity(generated):
    tests = list(generated.rglob("*RepositoryTest.java"))
    assert tests, "no @DataJpaTest was emitted; nothing exercises persistence"

    source = tests[0].read_text(encoding="utf-8")
    assert "@DataJpaTest" in source
    assert "repository.save(" in source, "the slice test must actually save a row"
    assert "repository.findById(" in source, "…and read it back, or it proves nothing"
    assert "@Autowired" in source
    assert "assertThat(saved.getId()).isNotNull()" in source, (
        "the assertion that would have caught the @NotNull-on-a-generated-id defect"
    )


def test_a_web_mvc_slice_is_emitted_per_entity(generated):
    tests = list(generated.rglob("*ControllerTest.java"))
    assert tests, "no @WebMvcTest was emitted; the HTTP contract is untested"

    source = tests[0].read_text(encoding="utf-8")
    assert "@WebMvcTest(" in source
    assert "@MockBean" in source, "the service must be mocked in a web slice"
    assert "MockMvc" in source
    assert "status().isOk()" in source


def test_the_web_slice_targets_the_path_the_controller_declares(generated):
    """A slice test against a path the controller does not serve fails for the wrong reason."""
    controller_test = next(generated.rglob("*ControllerTest.java")).read_text(encoding="utf-8")
    controller_src = next(generated.rglob("*Controller.java")).read_text(encoding="utf-8")

    tested = re.search(r'get\("(/api/v1/[a-z]+)"\)', controller_test).group(1)
    assert tested in controller_src, f"{tested} is not a path the controller serves"


def test_the_mockbean_style_matches_the_spring_boot_version(generated):
    """@MockitoBean does not exist in Spring Boot 3.2.3; @MockBean does."""
    source = next(generated.rglob("*ControllerTest.java")).read_text(encoding="utf-8")

    assert "org.springframework.boot.test.mock.mockito.MockBean" in source
    assert "MockitoBean" not in source.replace("@MockBean", "")


def test_an_entity_with_an_unsupported_attribute_type_skips_the_slice_test(tmp_path):
    """A slice test that cannot be given a value is skipped, never emitted broken."""
    from app.orchestrator.stages.deterministic import test_synthesis

    blueprint = {
        "serviceName": "odd-service", "packageName": "com.corp.odd",
        "entities": [{
            "name": "Odd",
            "attributes": [
                {"name": "id", "type": "Long", "isPrimaryKey": True},
                {"name": "payload", "type": "SomeUnmappableType"},
            ],
        }],
        "userStories": [],
    }
    state = {"blueprint": blueprint, "workspace_path": str(tmp_path), "generated_files": {}, "logs": []}
    result = test_synthesis.emit(state)

    assert not list(Path(tmp_path).rglob("*RepositoryTest.java")), "an uncompilable test was emitted"
    assert any("Skipped @DataJpaTest" in line for line in result["logs"]), (
        "the skip was silent; an operator cannot tell that coverage is missing"
    )
    assert list(Path(tmp_path).rglob("*ControllerTest.java")), "the web slice needs no values"


# ---------------------------------------------------------------------------
# The false positive that blocked the whole pipeline
# ---------------------------------------------------------------------------
def test_data_jpa_test_is_not_reported_as_a_prohibited_lombok_annotation(generated):
    """`@DataJpaTest` CONTAINS the substring `@Data`.

    The Lombok prohibition rule matched with `prohibited in content`, so a legitimate
    Spring Boot test slice was reported as a prohibited `@Data` annotation -- a HIGH
    violation, which blocked export with 403 and stopped the devops step. Nothing was
    generated. The remediation path already matched with `\\b@Data\\b`, so the checker and
    the fixer disagreed about the same file.
    """
    from app.services.security_service import audit_workspace

    report = audit_workspace(str(generated), "slice-diag", "notes")
    data = report.model_dump() if hasattr(report, "model_dump") else dict(report)
    offenders = [
        v for v in (data.get("violations") or [])
        if v.get("offendingElement") in ("@Data", "@Value", "@SneakyThrows")
    ]

    assert not offenders, (
        f"a legitimate slice test was reported as prohibited Lombok: "
        f"{[(v.get('id'), v.get('filePath')) for v in offenders]}"
    )


def test_a_genuine_prohibited_lombok_annotation_is_still_caught(tmp_path):
    """Narrowing the match must not blind the rule."""
    from app.services.security_service import audit_workspace

    target = tmp_path / "src/main/java/com/corp/x/model/entity/Bad.java"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "package com.corp.x.model.entity;\nimport lombok.Data;\n@Data\npublic class Bad {}\n",
        encoding="utf-8",
    )

    report = audit_workspace(str(tmp_path), "lombok-diag", "x")
    data = report.model_dump() if hasattr(report, "model_dump") else dict(report)
    caught = [
        v for v in (data.get("violations") or [])
        if v.get("offendingElement") == "@Data"
    ]

    assert caught, "a real @Data annotation is no longer detected"
    assert caught[0]["severity"].value == "HIGH" if hasattr(caught[0]["severity"], "value") else True
