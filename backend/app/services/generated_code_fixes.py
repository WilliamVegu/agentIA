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

from pathlib import Path
from typing import Dict, List, Tuple

#: Entity files are the only place a JPA id annotation appears.
_ENTITY_GLOB = "src/main/java/**/model/entity/*.java"

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


def normalise_generated_entities(workspace: str | Path) -> Dict[str, List[str]]:
    """Apply the corrections to every generated entity in the workspace.

    Idempotent: a file with no generated id, or one already corrected, is left byte
    identical, so this can run after every stage without churning the tree.
    """
    ws = Path(workspace)
    fixed: Dict[str, List[str]] = {}

    for java_file in sorted(ws.glob(_ENTITY_GLOB)):
        try:
            original = java_file.read_text(encoding="utf-8")
        except OSError:
            continue
        corrected, changed = fix_generated_id_not_null(original)
        if changed and corrected != original:
            java_file.write_text(corrected, encoding="utf-8")
            fixed[str(java_file.relative_to(ws))] = changed

    return fixed
