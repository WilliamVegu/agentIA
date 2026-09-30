"""Persist the lifecycle artifacts a code-generation run is given, before it runs.

**The bug this fixes.** The Requirements / Architecture / Models-SQL tabs read from the
session *workspace*, but the 8-node code-generation path writes only code:

    SCAFFOLDER: pom.xml, application.yml, *Application.java
    DOMAIN:     entity/*.java, dto/*.java
    SERVICE:    repository/*, service/*, exception/*
    CONTROLLER: controller/*.java
    TEST:       test/**/*.java

No stage owns `spec.md`, `user_stories.json`, `architecture.json` or `schema.sql`. So a
session started through that path showed its content *during* the run -- from the
frontend's in-memory state -- and lost it on reload, because nothing had ever been
written. Reported as "requirements, architecture and more tabs are lost after build is
done ... in history access they're gone".

The same gap is what broke the deploy. `docker-compose.yml` mounts
`./schema.sql:/docker-entrypoint-initdb.d/01-schema.sql`, and **when a bind-mount source
does not exist, Docker creates it as a directory**. Postgres then found a directory
where it expected a SQL file:

    psql: error: /docker-entrypoint-initdb.d/01-schema.sql: Permission denied

so the init script silently never ran and Hibernate's `ddl-auto` built the schema
instead, making a broken deploy look green.

**Write-if-absent, never overwrite.** If a session ran the real lifecycle pipeline, its
authored artifacts are better than anything derivable here and must survive. This only
fills gaps.

**These are derived, and say so.** The architecture written here comes from the
blueprint, not from a model. `generatedFrom: "blueprint"` is recorded on it so nobody
mistakes a mechanical derivation for a designed architecture -- the same distinction
the rest of the platform draws between verified and not-evaluable.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

#: The files this module is responsible for, in the order a reader wants them.
LIFECYCLE_ARTIFACTS = ("spec.md", "user_stories.json", "architecture.json", "schema.sql")


@dataclass
class _Attribute:
    name: str
    type: str = "String"
    isPrimaryKey: bool = False
    nullable: bool = True
    tableName: Optional[str] = None


@dataclass
class _Entity:
    name: str
    tableName: Optional[str] = None
    attributes: List[_Attribute] = field(default_factory=list)


def _snake(name: str) -> str:
    out = []
    for index, char in enumerate(str(name)):
        if char.isupper() and index and not str(name)[index - 1].isupper():
            out.append("_")
        out.append(char.lower())
    return "".join(out)


def _plural(name: str) -> str:
    """`Customer` -> `customers`. Matches the convention the emitters use."""
    base = _snake(name)
    if base.endswith("y") and not base.endswith(("ay", "ey", "oy", "uy")):
        return base[:-1] + "ies"
    if base.endswith(("s", "x", "z", "ch", "sh")):
        return base + "es"
    return base + "s"


def _entities_from_blueprint(blueprint: Mapping[str, Any]) -> List[_Entity]:
    entities: List[_Entity] = []
    for raw in blueprint.get("entities") or []:
        if not isinstance(raw, Mapping):
            continue
        name = str(raw.get("name") or "Entity")
        attributes = []
        for attr in raw.get("attributes") or []:
            if not isinstance(attr, Mapping):
                continue
            attributes.append(_Attribute(
                name=str(attr.get("name") or "field"),
                type=str(attr.get("type") or "String"),
                isPrimaryKey=bool(attr.get("isPrimaryKey") or attr.get("is_primary_key")),
                nullable=bool(attr.get("nullable", True)),
            ))
        entities.append(_Entity(
            name=name,
            tableName=raw.get("tableName") or raw.get("table_name") or _plural(name),
            attributes=attributes,
        ))
    return entities


def _stories(blueprint: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    stories = blueprint.get("userStories") or blueprint.get("user_stories") or []
    return [s for s in stories if isinstance(s, Mapping)]


def _spec_markdown(blueprint: Mapping[str, Any], stories: List[Mapping[str, Any]]) -> str:
    """A Spec Kit document, matching what `serialize_draft_to_markdown` emits.

    The path this module serves previously wrote a two-line stub -- a title and the raw
    prompt -- so the Requirements tab showed the prompt and no specification at all.
    """
    service = str(blueprint.get("serviceName") or blueprint.get("service_name") or "service")
    lines = [
        f"# Feature Specification: {service.replace('-', ' ').title()}",
        "",
        f"**Feature Branch**: `{service}`",
        "",
        f"**Created**: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "",
        "**Status**: Draft",
        "",
        "**Note**: derived from the validated blueprint at the start of code generation.",
        "",
        "## User Scenarios & Testing *(mandatory)*",
        "",
    ]
    for index, story in enumerate(stories, start=1):
        intent = story.get("intent") or story.get("title") or f"story {index}"
        lines += [
            f"### User Story {index} - {intent} (Priority: {story.get('priority', 'P1')})",
            "",
            f"As a {story.get('role', 'user')}, I want {intent}, so that "
            f"{story.get('benefit', 'the outcome is achieved')}.",
            "",
        ]
        for scenario in story.get("scenarios") or []:
            if not isinstance(scenario, Mapping):
                continue
            lines += [
                f"**{scenario.get('scenarioId', f'AC-{index}')}**",
                f"- **Given** {scenario.get('given', '')}",
                f"- **When** {scenario.get('when', '')}",
                f"- **Then** {scenario.get('then', '')}",
                "",
            ]
    # The domain model is part of the specification, not an afterthought: the tabs and
    # the schema both derive from it, so a spec without it is incomplete.
    entities = _entities_from_blueprint(blueprint)
    if entities:
        lines += ["## Domain Entities", ""]
        for entity in entities:
            lines.append(f"### {entity.name} (`{entity.tableName}`)")
            lines.append("")
            for attr in entity.attributes:
                flags = []
                if attr.isPrimaryKey:
                    flags.append("PK")
                if not attr.nullable:
                    flags.append("required")
                suffix = f" — {', '.join(flags)}" if flags else ""
                lines.append(f"- `{attr.name}`: {attr.type}{suffix}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _architecture(blueprint: Mapping[str, Any]) -> Dict[str, Any]:
    """Components and endpoints derived from the blueprint's entities.

    Marked `generatedFrom: blueprint` because it is a mechanical derivation. A session
    that ran the architecture phase has a designed document instead, and this function
    will not touch it.
    """
    service = str(blueprint.get("serviceName") or blueprint.get("service_name") or "service")
    entities = _entities_from_blueprint(blueprint)

    components: List[Dict[str, Any]] = [
        {"name": f"{e.name}Controller", "layer": "CONTROLLER", "responsibility": f"REST endpoints for {e.name}"}
        for e in entities
    ] + [
        {"name": f"{e.name}Service", "layer": "SERVICE", "responsibility": f"Business rules for {e.name}"}
        for e in entities
    ] + [
        {"name": f"{e.name}Repository", "layer": "REPOSITORY", "responsibility": f"Persistence for {e.name}"}
        for e in entities
    ] + [
        {"name": e.name, "layer": "ENTITY", "responsibility": f"JPA entity mapped to {e.tableName}"}
        for e in entities
    ]

    endpoints = []
    for entity in entities:
        resource = f"/api/v1/{entity.tableName}"
        endpoints += [
            {"method": "POST", "path": resource, "description": f"Create a {entity.name}"},
            {"method": "GET", "path": f"{resource}/{{id}}", "description": f"Read a {entity.name}"},
            {"method": "GET", "path": resource, "description": f"List {entity.name} records"},
            {"method": "DELETE", "path": f"{resource}/{{id}}", "description": f"Delete a {entity.name}"},
        ]

    lines = ["graph TD", "    Client[Cliente HTTP] --> Controller"]
    for entity in entities:
        lines += [
            f"    Controller --> {entity.name}Controller",
            f"    {entity.name}Controller --> {entity.name}Service",
            f"    {entity.name}Service --> {entity.name}Repository",
            f"    {entity.name}Repository --> {entity.name}Table[({entity.tableName})]",
        ]

    return {
        "serviceName": service,
        "packageName": blueprint.get("packageName") or f"com.corp.{service.replace('-', '')}",
        "basePort": blueprint.get("basePort") or 8080,
        "components": components,
        "endpoints": endpoints,
        "interactions": [],
        "mermaidDiagram": "\n".join(lines),
        "entities": [e.name for e in entities],
        # Honest provenance: this is derived, not designed by a model.
        "generatedFrom": "blueprint",
    }


def _schema_sql(blueprint: Mapping[str, Any]) -> str:
    """Real DDL for the blueprint's entities.

    Reuses the tested `schema_sql_from_draft` rather than a second implementation: the
    same function that fixed the hardcoded `items` table.
    """
    from app.services.model_sql_service import schema_sql_from_draft

    class _Draft:
        entities = _entities_from_blueprint(blueprint)

    return schema_sql_from_draft(_Draft())


def _write_if_absent(path: Path, content: str, *, written: List[str], skipped: List[str]) -> None:
    """Write unless the file exists -- and clear a directory Docker may have made.

    `docker compose` creates a missing bind-mount source as a **directory**, which is
    how `schema.sql` became an empty directory and Postgres reported "Permission
    denied" trying to read it. An empty directory at an artifact path is always that
    accident, so it is removed. A non-empty one is left alone and reported, because
    deleting real content to make room for a stub would be worse than the bug.
    """
    if path.is_dir():
        if any(path.iterdir()):
            skipped.append(f"{path.name} (a non-empty directory is in the way)")
            return
        path.rmdir()
    elif path.exists():
        skipped.append(path.name)
        return
    path.write_text(content, encoding="utf-8")
    written.append(path.name)


def ensure_lifecycle_artifacts(workspace: str | Path, blueprint: Mapping[str, Any]) -> Dict[str, List[str]]:
    """Fill in any lifecycle artifact the workspace is missing. Returns what it did.

    Call this before a code-generation run. It is deliberately idempotent and
    non-destructive: `skipped` lists what already existed.
    """
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)

    stories = _stories(blueprint)
    written: List[str] = []
    skipped: List[str] = []

    _write_if_absent(ws / "spec.md", _spec_markdown(blueprint, stories), written=written, skipped=skipped)
    _write_if_absent(
        ws / "user_stories.json", json.dumps(list(stories), indent=2), written=written, skipped=skipped
    )
    _write_if_absent(
        ws / "architecture.json", json.dumps(_architecture(blueprint), indent=2), written=written, skipped=skipped
    )
    _write_if_absent(ws / "schema.sql", _schema_sql(blueprint), written=written, skipped=skipped)

    return {"written": written, "skipped": skipped}


# ---------------------------------------------------------------------------
# Recovering a blueprint from code that was already generated
# ---------------------------------------------------------------------------
_ENTITY_CLASS = re.compile(r"class\s+(\w+)")
_TABLE_NAME = re.compile(r'@Table\s*\(\s*name\s*=\s*["\']([^"\']+)["\']')
_FIELD = re.compile(r"private\s+([\w<>, .]+?)\s+(\w+)\s*;")


def blueprint_from_generated_code(workspace: str | Path) -> Dict[str, Any]:
    """Reconstruct a blueprint from the entity classes already on disk.

    Exists for sessions generated before the artifacts were persisted: the blueprint
    was never stored, so the only surviving source of truth is the code it produced.
    Reading the entities back is honest -- it recovers what was actually generated,
    not what someone wished had been -- and it is strictly better than writing an
    empty stub, which would make the tabs look populated while saying nothing.

    Best-effort by design: an unreadable file is skipped rather than aborting the
    recovery, and a workspace with no entities returns an empty blueprint that the
    caller can detect.
    """
    base = Path(workspace)
    entities: List[Dict[str, Any]] = []

    for java_file in sorted(base.glob("src/main/java/**/model/entity/*.java")):
        try:
            source = java_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        name_match = _ENTITY_CLASS.search(source)
        name = name_match.group(1) if name_match else java_file.stem
        table_match = _TABLE_NAME.search(source)
        attributes: List[Dict[str, Any]] = []

        # A field's annotations are exactly the text between the previous field and
        # this one. An earlier version used a fixed 120/160-character look-back, which
        # reached into the PREVIOUS field's block and marked the field after `id` as a
        # primary key too -- producing `reference BIGINT ... PRIMARY KEY` in the
        # recovered schema. Bounding the block by the previous match removes the guess.
        cursor = 0
        for match in _FIELD.finditer(source):
            block = source[cursor:match.start()]
            cursor = match.end()
            java_type, field = match.group(1).strip(), match.group(2)
            attributes.append({
                "name": field,
                "type": java_type,
                "isPrimaryKey": "@Id" in block,
                "nullable": "nullable = false" not in block and "@NotNull" not in block,
            })

        entities.append({
            "name": name,
            "tableName": table_match.group(1) if table_match else _plural(name),
            "attributes": attributes,
        })

    return {
        "serviceName": base.name if base.name else "service",
        "packageName": "com.corp",
        "entities": entities,
        "userStories": [],
    }
