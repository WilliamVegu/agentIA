"""Post-generation corrections for defects that are structurally predictable.

**Why a post-pass rather than an emitter change.** The emitters are frozen and shared
by two generation paths (deterministic and model-backed). A correction that runs over
the persisted files applies to both, needs no change to either emitter, and can be
tested without running a graph.

**What it fixes, and how it was found.** A deployed service returned 500 on every
`POST` while `GET` worked and the build was green:

    POST /api/v1/customers -> 500 {"message": "An unexpected error occurred"}
    select count(*) from customers -> 0        (nothing was ever inserted)

The generated entity carried `@NotNull` on a database-generated id:

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(nullable = false)
    @NotNull                    <- the id is null until the database generates it
    private Long id;

Hibernate runs Bean Validation *before* insert, so the entity was rejected while the id
was still null. Nothing reached the database -- which is why Postgres logged no error
and the row count stayed at zero -- and the generated `GlobalExceptionHandler` returned
a tidy 500 without logging the cause, so the reason was invisible.

The blueprint says "id: Long PK NOT NULL" and the generator faithfully emitted
`@NotNull`, but those are not the same claim: a primary key is non-null *in the table*,
whereas a client-side `@NotNull` on a generated value is checked *before* the value
exists.

**The generated tests cannot catch this**, and that is the point: they are Mockito unit
tests with a mocked repository, so no Hibernate and no validation run. 21 of them passed
on a service whose only write path was completely broken.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

#: Entity files are the only place a JPA id annotation appears.
_ENTITY_GLOB = "src/main/java/**/model/entity/*.java"

#: Generated test sources, where the Spring test annotations live.
_TEST_GLOB = "src/test/java/**/*.java"

#: An annotation that does not exist in the pinned Spring Boot version, and its
#: predecessor, which does. `@MockitoBean` arrived in Spring Boot 3.4;
#: `test_analysis_service` and the generated pom pin 3.2.3.
_MOCKITO_BEAN_IMPORT = "org.springframework.test.context.bean.override.mockito.MockitoBean"
_MOCK_BEAN_IMPORT = "org.springframework.boot.test.mock.mockito.MockBean"

_MARKER = "@GeneratedValue"
_OFFENDING = "@NotNull"


def _is_annotation(line: str) -> bool:
    return line.strip().startswith("@")


def _is_field(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("private ", "protected ", "public ")) and stripped.endswith(";")


def fix_generated_id_not_null(source: str) -> Tuple[str, List[str]]:
    """Remove `@NotNull` from any field whose annotation block has `@GeneratedValue`.

    Returns the corrected source and the field names changed.

    Line-based on purpose. An earlier attempt in this codebase used a fixed-width
    look-back window and edited the field *after* the intended one; here the annotation
    block is delimited by the neighbouring annotations and the blank lines around them,
    so the block examined is exactly the block that belongs to this field.
    """
    lines = source.split("\n")
    changed: List[str] = []
    drop: set[int] = set()

    for index, line in enumerate(lines):
        if line.strip() != _OFFENDING:
            continue

        # The field this annotation belongs to: the first non-annotation, non-blank
        # line below it.
        field_index = index + 1
        while field_index < len(lines) and not lines[field_index].strip():
            field_index += 1
        while field_index < len(lines) and _is_annotation(lines[field_index]):
            field_index += 1
        if field_index >= len(lines) or not _is_field(lines[field_index]):
            continue

        # Its annotation block: everything above, up to the blank line or the previous
        # statement.
        block_start = index - 1
        while block_start >= 0 and (
            _is_annotation(lines[block_start]) or not lines[block_start].strip()
        ):
            block_start -= 1
        block = lines[block_start + 1:field_index]

        if any(_MARKER in candidate for candidate in block):
            drop.add(index)
            changed.append(lines[field_index].strip().rstrip(";").split()[-1])

    if not drop:
        return source, []

    kept = [line for i, line in enumerate(lines) if i not in drop]

    # Removing a line can leave a doubled blank line where it stood.
    cleaned: List[str] = []
    for line in kept:
        if not line.strip() and cleaned and not cleaned[-1].strip():
            continue
        cleaned.append(line)

    return "\n".join(cleaned), changed


_MODEL_GLOB = "src/main/java/**/model/**/*.java"

_NON_STRING_TYPES = {
    "UUID", "Long", "long", "Integer", "int", "Short", "short",
    "Byte", "byte", "Double", "double", "Float", "float",
    "BigDecimal", "BigInteger", "Boolean", "bool", "boolean",
    "LocalDate", "LocalDateTime", "LocalTime", "Instant",
    "ZonedDateTime", "OffsetDateTime", "Date",
}

_STRING_ONLY_ANNOTATIONS = ("@Size", "@NotBlank", "@NotEmpty", "@Length", "@Pattern", "@Email")

_NON_STRING_FIELD_RE = re.compile(
    r'(?:^|[\s,(])(?:(?:java\.(?:util|lang|math|time)\.)?('
    + '|'.join(_NON_STRING_TYPES)
    + r'))\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:[;,) =]|$)'
)


def fix_invalid_type_constraints(source: str) -> Tuple[str, List[str]]:
    """Remove String-only validation constraints (e.g. @Size, @NotBlank, @Pattern)
    from non-String fields or record components (UUID, Long, Integer, Boolean, LocalDateTime, etc.).

    Hibernate Validator fails at runtime with UnexpectedTypeException HV000030
    when a CharSequence constraint is declared on a UUID or numeric/temporal field.
    """
    lines = source.split("\n")
    drop: set[int] = set()
    changed: List[str] = []

    for index, line in enumerate(lines):
        m = _NON_STRING_FIELD_RE.search(line)
        if not m:
            continue
        type_name = m.group(1)
        var_name = m.group(2)

        # Check inline annotations on the same line
        for ann in _STRING_ONLY_ANNOTATIONS:
            pat = re.compile(rf'{re.escape(ann)}(?:\([^)]*\))?\s*')
            if pat.search(lines[index]):
                lines[index] = pat.sub('', lines[index])
                changed.append(f"{ann} on {var_name}")

        # Check preceding lines in the annotation block
        block_idx = index - 1
        while block_idx >= 0 and (_is_annotation(lines[block_idx]) or not lines[block_idx].strip()):
            prev_line = lines[block_idx].strip()
            for ann in _STRING_ONLY_ANNOTATIONS:
                if re.search(rf'^\s*{re.escape(ann)}(?:\b|\()', prev_line):
                    drop.add(block_idx)
                    changed.append(f"{ann} on {var_name}")
            block_idx -= 1

    if not drop and not changed:
        return source, []

    kept = [line for i, line in enumerate(lines) if i not in drop]
    cleaned: List[str] = []
    for line in kept:
        if not line.strip() and cleaned and not cleaned[-1].strip():
            continue
        cleaned.append(line)

    return "\n".join(cleaned), changed


def normalise_generated_entities(workspace: str | Path) -> Dict[str, List[str]]:
    """Apply the corrections to every generated entity and model in the workspace.

    Idempotent: a file with no generated id, or one already corrected, is left byte
    identical, so this can run after every stage without churning the tree.
    """
    ws = Path(workspace)
    fixed: Dict[str, List[str]] = {}

    for java_file in sorted(ws.glob(_MODEL_GLOB)):
        try:
            original = java_file.read_text(encoding="utf-8")
        except OSError:
            continue
        current = original
        all_changed: List[str] = []

        if "/model/entity/" in java_file.as_posix():
            current, id_changed = fix_generated_id_not_null(current)
            all_changed.extend(id_changed)

        current, type_changed = fix_invalid_type_constraints(current)
        all_changed.extend(type_changed)

        if all_changed and current != original:
            java_file.write_text(current, encoding="utf-8")
            fixed[java_file.relative_to(ws).as_posix()] = all_changed

    return fixed


def fix_spring_test_annotations(source: str) -> Tuple[str, List[str]]:
    """Replace test annotations the pinned Spring Boot version does not provide.

    A generated controller test imported
    ``org.springframework.test.context.bean.override.mockito.MockitoBean`` and failed to
    compile with "package ... does not exist". The project pins Spring Boot 3.2.3, where
    that annotation does not exist; ``@MockBean`` is its predecessor.

    The instruction set states the rule, but an instruction is a request and a model may
    not follow it -- this session is the evidence. A correction over the emitted files
    applies whichever path produced them, which is why it lives here rather than in the
    prompt alone.

    Matched on a word boundary so ``@MockBean`` itself is never touched, and the import is
    rewritten with it, since swapping only the annotation leaves the bad import behind.
    """
    changed: List[str] = []
    out = source

    if f"{_MOCKITO_BEAN_IMPORT};" in out:
        out = out.replace(f"import {_MOCKITO_BEAN_IMPORT};", f"import {_MOCK_BEAN_IMPORT};")
        changed.append("MockitoBean import")

    if re.search(r"@MockitoBean\b", out):
        out = re.sub(r"@MockitoBean\b", "@MockBean", out)
        changed.append("@MockitoBean")

    return out, changed


def normalise_generated_tests(workspace: str | Path) -> Dict[str, List[str]]:
    """Apply the corrections to every generated test source in the workspace."""
    ws = Path(workspace)
    fixed: Dict[str, List[str]] = {}

    for java_file in sorted(ws.glob(_TEST_GLOB)):
        try:
            original = java_file.read_text(encoding="utf-8")
        except OSError:
            continue
        corrected, changed = fix_spring_test_annotations(original)
        if changed and corrected != original:
            java_file.write_text(corrected, encoding="utf-8")
            fixed[java_file.relative_to(ws).as_posix()] = changed

    return fixed


#: Handler injected when the generated advice cannot answer an unmapped path.
#:
#: Deliberately written with fully-qualified names and `ResponseEntity<?>`:
#:
#:   * no import has to be added, so the file cannot break because one was inserted in the
#:     wrong place or the class is absent from the pinned Spring version;
#:   * the return type does not name the file's own error type. The model path declares a
#:     nested `record ApiError(Instant, int, String, Map)` while the deterministic template
#:     uses a plain `Map`, so a handler written for either would fail to compile in the
#:     other. A wildcard plus a `Map` body serialises correctly in both.
_NOT_FOUND_HANDLER = '''
    /**
     * An unmapped path is a client error, not a server fault.
     *
     * Spring raises NoResourceFoundException for a request that matches no handler. Without
     * this method it reaches the generic Exception handler and is reported as 500, which
     * makes a missing endpoint -- or a request aimed at a different service -- look like an
     * internal failure.
     */
    @org.springframework.web.bind.annotation.ExceptionHandler(
            org.springframework.web.servlet.resource.NoResourceFoundException.class)
    public org.springframework.http.ResponseEntity<?> handleNoResourceFound(
            org.springframework.web.servlet.resource.NoResourceFoundException ex) {
        return org.springframework.http.ResponseEntity
                .status(org.springframework.http.HttpStatus.NOT_FOUND)
                .body(java.util.Map.of(
                        "timestamp", java.time.Instant.now().toString(),
                        "status", org.springframework.http.HttpStatus.NOT_FOUND.value(),
                        "error", "Not Found",
                        "message", "Endpoint no encontrado: /" + ex.getResourcePath()));
    }
'''


def ensure_not_found_handler(workspace: str | Path) -> Dict[str, str]:
    """Make generated advice answer an unmapped path with 404 instead of 500.

    The deterministic emitter already declares this handler; the model path does not, so
    model-generated services answer unknown paths with 500. Measured on the deployed
    help-desk service:

        GET /api/borrowers     -> 500   (no such endpoint)
        GET /api/v1/customers  -> 200

    That 500 is why a playground call aimed at the wrong service was diagnosed as a
    container failure. A 404 would have said "no such endpoint" immediately.

    Inserted before the class's closing brace, after any nested type declarations, which is
    valid for the nested record the model path emits.

    Idempotent: a file already mentioning the exception is left byte-identical.
    """
    ws = Path(workspace)
    inserted: Dict[str, str] = {}

    for java_file in sorted(ws.glob("src/main/java/**/*.java")):
        try:
            source = java_file.read_text(encoding="utf-8")
        except OSError:
            continue
        if "@RestControllerAdvice" not in source:
            continue
        if "NoResourceFoundException" in source:
            continue

        closing = source.rfind("}")
        if closing == -1:
            continue

        patched = source[:closing] + _NOT_FOUND_HANDLER + source[closing:]
        java_file.write_text(patched, encoding="utf-8")
        inserted[java_file.relative_to(ws).as_posix()] = "NoResourceFoundException -> 404"

    return inserted
