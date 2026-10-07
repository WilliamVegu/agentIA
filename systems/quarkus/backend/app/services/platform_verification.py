"""Platform-authored verification: an acceptance signal the generator cannot author.

**Why this module exists.** Every test that decides whether a generated service is
acceptable is currently written by the same model, in the same pipeline, whose
instruction says to *mock the repository*. That is not a verification gap in
theory: the one real correctness defect this project found by inspection -- the
generated ``schema.sql`` contradicting the generated JPA entities -- was caught by
a deterministic cross-artifact checker and **could not** have been caught by a
suite that mocks persistence out. Commit0 supplies its unit tests; ProgramBench
generates its behavioural tests by agent-driven fuzzing. The platform should do
the same: own at least one test the generator never sees.

**What the test asserts.** Hibernate validates each entity's mapping against the
database it is actually given. Booting a JPA context with ``ddl-auto=validate``
against a database created from the project's own ``schema.sql`` therefore fails
whenever the two disagree -- which is the executable form of the check that was
previously only a text comparison. It needs no instance construction, so it is
deterministically generatable from the artifacts alone.

**What it is not.** It is not a correctness oracle: it proves the schema, the
entities and the repository wiring are mutually consistent, not that the service
behaves. That is the same honest boundary the conformance instrument has, and it
is precisely why it targets *consistency* rather than style.

**Dispatch rule.** The test is injected into the workspace *after* the generation
stages and *before* the build, and is deliberately **not** merged into
``generated_files``: the model must not be able to see it, edit it, or learn from
it. A verifier the candidate can read is not a verifier.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

#: Fixed file name. The model owns ``src/test/java/**`` in general, but this path
#: is written after every stage has finished, so no stage can collide with it.
PLATFORM_TEST_CLASS = "PlatformPersistenceContractTest"

#: Directories that must never reach the build. A ``.git`` directory in a
#: scaffolded workspace is not merely noise: Cursor's audit found 63% of
#: "successful" SWE-bench Pro resolutions *retrieved* the fix rather than derived
#: it, and public SWE-bench Pro images that leaked ``.git`` offered 100% exploit
#: success. Generated workspaces are published to Git, so history can arrive by
#: accident.
VCS_DIRECTORIES = (".git", ".hg", ".svn")

_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
_REPOSITORY_RE = re.compile(
    r"(?:public\s+)?interface\s+(\w+)\s+extends\s+[\w.]*Repository\s*<",
)
_H2_IDENTITY_IN_SCHEMA_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?(\w+)",
    re.IGNORECASE,
)


def _iter_java(workspace: Path, kind: str) -> List[Path]:
    """Java sources under a ``<kind>`` package directory, in any module, deterministically ordered.

    Multi-module aware: the workspace may be a Maven reactor, so ``src/main/java``
    appears under each module directory rather than only at the workspace root.
    """
    results: List[Path] = []
    for root in workspace.rglob("src/main/java"):
        results.extend(path for path in root.rglob("*.java") if path.parent.name == kind)
    return sorted(results)


def _find_application(workspace: Path) -> Optional[Tuple[str, str]]:
    """``(module_prefix, package)`` of the generated application entry point.

    The entry point may sit at the workspace root (single-module) or inside a module
    directory (multi-module). The prefix is ``"<module>/"`` in the latter case and
    ``""`` in the former, so the injected test lands in the module whose classpath
    actually carries the application class.
    """
    for path in sorted(workspace.rglob("*Application.java")):
        match = _PACKAGE_RE.search(path.read_text(encoding="utf-8", errors="replace"))
        if not match:
            continue
        parts = path.relative_to(workspace).parts
        prefix = f"{parts[0]}/" if len(parts) > 1 and parts[1] == "src" else ""
        return prefix, match.group(1)
    return None


def base_package(workspace: Path) -> Optional[str]:
    """The generated application's base package, read from its entry point.

    Derived from the artifact rather than assumed: the blueprint does not carry a
    package name, so the model chooses one, and hardcoding ``com.example...``
    would place the injected test where component scanning cannot see the
    application class.
    """
    found = _find_application(workspace)
    return found[1] if found else None


def repository_types(workspace: Path) -> List[Tuple[str, str]]:
    """``(simple name, package)`` for every generated Spring Data repository."""
    found: List[Tuple[str, str]] = []
    for path in _iter_java(workspace, "repository"):
        text = path.read_text(encoding="utf-8", errors="replace")
        package = _PACKAGE_RE.search(text)
        if not package:
            continue
        for name in _REPOSITORY_RE.findall(text):
            found.append((name, package.group(1)))
    return found


def render_contract_test(workspace: Path) -> Optional[Tuple[str, str]]:
    """Render the platform test as ``(workspace_relative_path, content)``.

    Returns ``None`` when the workspace cannot support the test -- no application
    class, no ``schema.sql``, or no repositories. **Absence is reported, not
    silently treated as a pass**: the caller must record that no platform
    verification ran rather than let a missing precondition look like success
    (the feature-012 rule, applied one level down).
    """
    found = _find_application(workspace)
    if found is None:
        return None
    module_prefix, package = found

    schema_path = workspace / "schema.sql"
    if not schema_path.is_file():
        return None

    declared_tables = _H2_IDENTITY_IN_SCHEMA_RE.findall(
        schema_path.read_text(encoding="utf-8", errors="replace")
    )
    if not declared_tables:
        return None

    repositories = repository_types(workspace)
    if not repositories:
        return None

    package_path = package.replace(".", "/")
    rel_path = f"{module_prefix}src/test/java/{package_path}/{PLATFORM_TEST_CLASS}.java"

    imports = "\n".join(
        sorted({f"import {repo_package}.{name};" for name, repo_package in repositories})
    )
    bean_assertions = "\n".join(
        f"        assertThat(context.getBean({name}.class)).isNotNull();"
        for name, _ in repositories
    )

    content = f'''package {package};

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;
import org.springframework.test.context.TestPropertySource;
{imports}

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Platform-authored persistence contract test.
 *
 * <p>Not written by the generation model, and not visible to it. Hibernate is
 * asked to <em>validate</em> every entity mapping against a database created from
 * this project's own {{@code schema.sql}}. If the schema and the entities disagree,
 * the context fails to start and this test fails with it.
 *
 * <p>This is the executable form of a check that was previously only a text
 * comparison between two generated files. It does not assert that the service
 * behaves correctly -- only that its persistence layer is internally consistent.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestPropertySource(properties = {{
        // H2 in PostgreSQL mode: the generated DDL is written to be compatible
        // with both, and the datasource must be in-memory so the build stays
        // hermetic.
        "spring.datasource.url=jdbc:h2:mem:platformcontract;MODE=PostgreSQL;DB_CLOSE_DELAY=-1",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.datasource.username=sa",
        "spring.datasource.password=",
        // Validate, never generate: a generated schema would make this test pass
        // by construction and prove nothing.
        "spring.jpa.hibernate.ddl-auto=validate",
        // The schema is the project's own artifact, at the workspace root.
        "spring.sql.init.mode=always",
        "spring.sql.init.schema-locations=file:./schema.sql",
        "spring.jpa.defer-datasource-initialization=false",
}})
class {PLATFORM_TEST_CLASS} {{

    @Autowired
    private ApplicationContext context;

    @Test
    void the_schema_the_entities_and_the_repositories_agree() {{
        assertThat(context).isNotNull();
{bean_assertions}
    }}
}}
'''
    return rel_path, content


def inject_contract_test(workspace_path: str) -> Optional[str]:
    """Write the platform test into the workspace. Returns its path, or ``None``.

    ``None`` means the preconditions were absent and no platform verification ran.
    The caller must surface that rather than treat it as a pass.
    """
    workspace = Path(workspace_path)
    rendered = render_contract_test(workspace)
    if rendered is None:
        return None
    rel_path, content = rendered
    target = workspace / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return rel_path


def strip_vcs_metadata(workspace_path: str) -> Tuple[str, ...]:
    """Remove version-control metadata from the workspace. Returns what was removed.

    A generated workspace is published to Git, so a ``.git`` directory can arrive
    by accident; leaving one in place hands the build any history it contains.
    """
    import shutil

    workspace = Path(workspace_path)
    removed: List[str] = []
    for name in VCS_DIRECTORIES:
        for candidate in sorted(workspace.rglob(name)):
            if not candidate.is_dir():
                continue
            shutil.rmtree(candidate, ignore_errors=True)
            removed.append(str(candidate.relative_to(workspace)))
    return tuple(removed)
