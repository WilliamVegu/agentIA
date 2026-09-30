"""Lifecycle artifacts must reach the workspace before code generation runs.

Reported as "requirements, architecture and more tabs are lost after build is done ...
in history access they're gone". The tabs read from the session workspace, but the
8-node code-generation path writes only code -- no `spec.md`, `user_stories.json`,
`architecture.json` or `schema.sql`. A session on that path showed its content during
the run from the frontend's in-memory state and lost it on reload, because nothing had
ever been written.

The same gap broke deployment. `docker-compose.yml` bind-mounts
`./schema.sql:/docker-entrypoint-initdb.d/01-schema.sql`, and **when a bind-mount source
does not exist, Docker creates it as a directory**:

    psql: error: /docker-entrypoint-initdb.d/01-schema.sql: Permission denied

so the init script silently never ran and Hibernate's `ddl-auto` built the schema,
making a broken deploy look green.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.lifecycle_artifacts import (  # noqa: E402
    LIFECYCLE_ARTIFACTS,
    blueprint_from_generated_code,
    ensure_lifecycle_artifacts,
)


@pytest.fixture
def blueprint():
    return {
        "serviceName": "help-desk",
        "packageName": "com.corp.helpdesk",
        "entities": [
            {
                "name": "Customer", "tableName": "customers",
                "attributes": [
                    {"name": "id", "type": "Long", "isPrimaryKey": True, "nullable": False},
                    {"name": "email", "type": "String", "nullable": False},
                    {"name": "fullName", "type": "String", "nullable": False},
                ],
            },
            {
                "name": "Ticket", "tableName": "tickets",
                "attributes": [
                    {"name": "id", "type": "Long", "isPrimaryKey": True, "nullable": False},
                    {"name": "subject", "type": "String", "nullable": False},
                ],
            },
        ],
        "userStories": [
            {
                "id": "US-1", "priority": "P1", "role": "support agent",
                "intent": "register a customer", "benefit": "I can serve them",
                "scenarios": [
                    {"scenarioId": "AC-1.1", "given": "a valid email",
                     "when": "the agent registers", "then": "the customer is stored"},
                    {"scenarioId": "AC-1.2", "given": "a malformed email",
                     "when": "the agent registers", "then": "400 is returned"},
                ],
            }
        ],
    }


def test_every_artifact_is_written(tmp_path, blueprint):
    result = ensure_lifecycle_artifacts(tmp_path, blueprint)

    assert set(result["written"]) == set(LIFECYCLE_ARTIFACTS)
    for name in LIFECYCLE_ARTIFACTS:
        assert (tmp_path / name).is_file(), f"{name} was not written as a file"


def test_the_schema_is_real_ddl_for_this_blueprint(tmp_path, blueprint):
    """Not a stub: the tables the entities declare, with their constraints."""
    ensure_lifecycle_artifacts(tmp_path, blueprint)

    sql = (tmp_path / "schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS customers" in sql
    assert "CREATE TABLE IF NOT EXISTS tickets" in sql
    assert "email VARCHAR(255) NOT NULL" in sql
    assert "full_name VARCHAR(255) NOT NULL" in sql, "camelCase was not mapped to a column name"


def test_spec_md_is_a_spec_kit_document_not_a_stub(tmp_path, blueprint):
    """The path used to write a title plus the raw prompt, which is not a spec."""
    ensure_lifecycle_artifacts(tmp_path, blueprint)

    spec = (tmp_path / "spec.md").read_text(encoding="utf-8")

    assert "# Feature Specification:" in spec
    assert "**Status**: Draft" in spec
    assert "## User Scenarios & Testing" in spec
    assert "### User Story 1" in spec
    assert "AC-1.1" in spec, "the acceptance scenarios are missing"

    # The change that broke deploys was a two-line stub. Guard the shape, not the size.
    assert len(spec) > 200


def test_the_architecture_is_marked_as_derived(tmp_path, blueprint):
    """Honest provenance: derived from the blueprint, not designed by a model."""
    ensure_lifecycle_artifacts(tmp_path, blueprint)

    arch = json.loads((tmp_path / "architecture.json").read_text(encoding="utf-8"))

    assert arch["generatedFrom"] == "blueprint"
    assert {c["name"] for c in arch["components"]} >= {"CustomerController", "TicketRepository"}
    assert any(e["path"] == "/api/v1/customers" for e in arch["endpoints"])


def test_the_stories_are_persisted_so_the_tab_survives_a_reload(tmp_path, blueprint):
    ensure_lifecycle_artifacts(tmp_path, blueprint)

    stories = json.loads((tmp_path / "user_stories.json").read_text(encoding="utf-8"))

    assert stories[0]["id"] == "US-1"
    assert len(stories[0]["scenarios"]) == 2


# ---------------------------------------------------------------------------
# Non-destructive: an authored artifact must survive
# ---------------------------------------------------------------------------
def test_an_existing_artifact_is_never_overwritten(tmp_path, blueprint):
    """A session that ran the real lifecycle has better artifacts than these."""
    (tmp_path / "architecture.json").write_text('{"authored": true}', encoding="utf-8")
    (tmp_path / "spec.md").write_text("# Authored spec", encoding="utf-8")

    result = ensure_lifecycle_artifacts(tmp_path, blueprint)

    assert (tmp_path / "architecture.json").read_text(encoding="utf-8") == '{"authored": true}'
    assert (tmp_path / "spec.md").read_text(encoding="utf-8") == "# Authored spec"
    assert set(result["skipped"]) == {"architecture.json", "spec.md"}
    assert set(result["written"]) == {"user_stories.json", "schema.sql", "domain_model.json"}


def test_it_is_idempotent(tmp_path, blueprint):
    first = ensure_lifecycle_artifacts(tmp_path, blueprint)
    second = ensure_lifecycle_artifacts(tmp_path, blueprint)

    assert set(first["written"]) == set(LIFECYCLE_ARTIFACTS)
    assert second["written"] == []
    assert set(second["skipped"]) == set(LIFECYCLE_ARTIFACTS)


def test_an_empty_directory_in_the_way_is_replaced(tmp_path, blueprint):
    """What Docker creates when a bind-mount source is missing -- the deploy bug."""
    (tmp_path / "schema.sql").mkdir()

    result = ensure_lifecycle_artifacts(tmp_path, blueprint)

    assert (tmp_path / "schema.sql").is_file(), "the directory was not replaced by a file"
    assert "schema.sql" in result["written"]


def test_a_non_empty_directory_is_left_alone(tmp_path, blueprint):
    """Never delete real content to make room for a derived file."""
    victim = tmp_path / "schema.sql"
    victim.mkdir()
    (victim / "important.sql").write_text("keep me", encoding="utf-8")

    result = ensure_lifecycle_artifacts(tmp_path, blueprint)

    assert victim.is_dir() and (victim / "important.sql").exists()
    assert any("schema.sql" in s for s in result["skipped"])


def test_a_blueprint_with_no_entities_still_produces_files(tmp_path):
    """Degenerate input must not raise: the run still needs the files to exist."""
    result = ensure_lifecycle_artifacts(tmp_path, {"serviceName": "empty"})

    assert set(result["written"]) == set(LIFECYCLE_ARTIFACTS)
    assert "declared no entities" in (tmp_path / "schema.sql").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Recovering a blueprint from code already generated
# ---------------------------------------------------------------------------
def test_a_blueprint_is_recovered_from_the_generated_entities(tmp_path):
    """For sessions generated before this fix, the code is the only surviving source."""
    entity = tmp_path / "src/main/java/com/corp/helpdesk/model/entity/Customer.java"
    entity.parent.mkdir(parents=True)
    entity.write_text(
        "package com.corp.helpdesk.model.entity;\n"
        "@Entity\n@Table(name = \"customers\")\n"
        "public class Customer {\n"
        "    @Id\n    @GeneratedValue(strategy = GenerationType.IDENTITY)\n"
        "    @Column(nullable = false)\n    private Long id;\n"
        "    @Column(nullable = false)\n    @NotBlank\n    private String email;\n"
        "    @Column(nullable = true)\n    private String nickname;\n"
        "}\n",
        encoding="utf-8",
    )

    recovered = blueprint_from_generated_code(tmp_path)

    assert [e["name"] for e in recovered["entities"]] == ["Customer"]
    entity_out = recovered["entities"][0]
    assert entity_out["tableName"] == "customers"
    fields = {a["name"]: a for a in entity_out["attributes"]}
    assert fields["id"]["isPrimaryKey"] is True
    assert fields["email"]["nullable"] is False, "a NOT NULL column was recovered as nullable"
    assert fields["nickname"]["nullable"] is True


def test_recovery_of_an_empty_workspace_is_not_an_error(tmp_path):
    assert blueprint_from_generated_code(tmp_path)["entities"] == []


def test_recovered_entities_produce_a_usable_schema(tmp_path):
    entity = tmp_path / "src/main/java/com/corp/x/model/entity/Order.java"
    entity.parent.mkdir(parents=True)
    entity.write_text(
        "package com.corp.x.model.entity;\n@Table(name = \"orders\")\n"
        "public class Order {\n    @Id\n    private Long id;\n"
        "    @Column(nullable = false)\n    private String reference;\n}\n",
        encoding="utf-8",
    )

    blueprint = blueprint_from_generated_code(tmp_path)
    ensure_lifecycle_artifacts(tmp_path, blueprint)

    sql = (tmp_path / "schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS orders" in sql
    assert "reference VARCHAR(255) NOT NULL" in sql


def test_the_domain_model_is_persisted_so_the_tab_survives_a_reload(tmp_path, blueprint):
    """Reported as "modelos & SQL disappear".

    The Models & SQL tab read its content from React state only. It was populated while the
    step ran and empty after any reload, resume or history access -- with `schema.sql` on
    disk the whole time. There was no GET endpoint for the model and nothing persisted it,
    so the tab had no way to reconstruct what it had shown a moment earlier.
    """
    import json

    result = ensure_lifecycle_artifacts(tmp_path, blueprint)

    assert "domain_model.json" in result["written"]
    model = json.loads((tmp_path / "domain_model.json").read_text(encoding="utf-8"))

    # Shaped like the API's DataModelSynthesisResponse, because the view reads these keys.
    assert {e["name"] for e in model["entities"]} == {"Customer", "Ticket"}
    assert model["sqlSchema"]["schemaDdl"].startswith("--")
    assert "CREATE TABLE IF NOT EXISTS customers" in model["sqlSchema"]["schemaDdl"]
    assert model["mermaidErDiagram"]

    # Marked derived: it is a mechanical reconstruction, not a model-designed schema.
    assert model["generatedFrom"] == "blueprint"


def test_the_domain_model_carries_the_attribute_fields_the_view_renders(tmp_path, blueprint):
    """The view renders columnName/javaType/sqlType per attribute."""
    import json

    ensure_lifecycle_artifacts(tmp_path, blueprint)
    model = json.loads((tmp_path / "domain_model.json").read_text(encoding="utf-8"))

    customer = next(e for e in model["entities"] if e["name"] == "Customer")
    fields = {a["name"]: a for a in customer["attributes"]}
    assert fields["fullName"]["columnName"] == "full_name"
    assert fields["fullName"]["javaType"] == "String"
    assert fields["id"]["sqlType"] == "BIGINT"
    assert fields["id"]["isPrimaryKey"] is True
    assert fields["email"]["nullable"] is False
