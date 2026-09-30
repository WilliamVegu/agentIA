"""An ingested specification must outlive the process that ingested it.

`SPECIFICATIONS_STORE` was a process-local dict and nothing else. The upload returned a
`specId` and a summary, and that id referred to a dict entry that vanished on the next
restart -- including every `uvicorn --reload` during development. Measured against the
running server: `POST /specifications/upload` -> 201, `GET /specifications/{id}` -> 200, and
after a reload the same GET returned `{"detail": "Specification not found"}`.

The flow this breaks is the whole point of the Blueprints tab: ingest a specification you
already have, then create a session to generate from it. `POST /sessions` resolves the
`specId` through `get_specification`, so a restart between the two steps failed at the
second with no indication that the first had expired.
"""
import json

import pytest

from app.config import settings
from app.models.blueprint import (
    AcceptanceScenarioRecord,
    ArchitectureBlueprint,
    DomainEntity,
    EntityAttribute,
    UserStoryRecord,
)
from app.services import spec_service
from app.services.spec_service import get_specification, save_specification

def _valid_blueprint() -> ArchitectureBlueprint:
    """A blueprint the model accepts.

    `userStories` requires at least one entry and each story at least two scenarios with
    clauses of three or more characters -- the schema is strict, which is why a nonsense
    JSON blueprint is hard to produce by accident and why only the text entrances need a
    plausibility check.
    """
    return ArchitectureBlueprint(
        serviceName="thing-service",
        packageName="com.corp.thing",
        basePort=8080,
        entities=[DomainEntity(
            name="Thing",
            tableName="things",
            attributes=[EntityAttribute(name="id", type="Long", isPrimaryKey=True)],
        )],
        userStories=[UserStoryRecord(
            id="US-1", priority="P1", role="User",
            intent="list things", benefit="see them",
            scenarios=[
                AcceptanceScenarioRecord(
                    scenarioId="AC-1.1", given="things exist",
                    when="the list is requested", then="they are returned",
                ),
                AcceptanceScenarioRecord(
                    scenarioId="AC-1.2", given="no things exist",
                    when="the list is requested", then="an empty list is returned",
                ),
            ],
        )],
    )


DOCUMENT = (
    "# Feature Specification: T\n"
    "**Feature Branch**: `thing-service`\n\n"
    "### Key Entities\n"
    "- **Thing**: a thing. id (Long), name (String)\n\n"
    "### User Scenarios\n"
    "- **US-1**: As a User, I want to list things, so that I see them.\n"
    "  - **AC-1.1**: Given things, when GET is called, then they are returned.\n"
)


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Point the store at a temporary directory and start from an empty cache."""
    monkeypatch.setattr(settings, "SPECIFICATION_DIR", str(tmp_path / "specs"))
    spec_service.SPECIFICATIONS_STORE.clear()
    yield
    spec_service.SPECIFICATIONS_STORE.clear()


def test_a_saved_specification_is_written_to_disk():
    blueprint = _valid_blueprint()

    summary = save_specification(blueprint)

    path = spec_service._specification_path(summary.specId)
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["serviceName"] == "thing-service"


def test_it_is_readable_after_the_cache_is_lost():
    """What a restart does, expressed as a test."""
    blueprint = _valid_blueprint()
    spec_id = save_specification(blueprint).specId

    spec_service.SPECIFICATIONS_STORE.clear()  # the restart

    restored = get_specification(spec_id)
    assert restored.serviceName == "thing-service"
    assert [e.name for e in restored.entities] == ["Thing"]


def test_the_uploaded_document_survives_and_keeps_its_content():
    """Through the API, end to end, including the cache loss."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    posted = client.post(
        "/api/v1/specifications/upload",
        files={"file": ("spec.md", DOCUMENT.encode(), "text/markdown")},
    )
    assert posted.status_code == 201
    spec_id = posted.json()["specId"]

    spec_service.SPECIFICATIONS_STORE.clear()  # the restart

    fetched = client.get(f"/api/v1/specifications/{spec_id}")
    assert fetched.status_code == 200, (
        "the id the upload issued must still resolve after a restart; POST /sessions "
        "depends on it"
    )
    body = fetched.json()
    assert body["serviceName"] == "thing-service"
    assert [e["name"] for e in body["entities"]] == ["Thing"]
    assert [s["id"] for s in body["userStories"]] == ["US-1"]


def test_an_unknown_id_still_raises_keyerror():
    """Persistence must not turn a missing id into an empty success."""
    with pytest.raises(KeyError):
        get_specification("00000000-0000-0000-0000-000000000000")


def test_an_unwritable_directory_does_not_lose_the_specification(monkeypatch, tmp_path):
    """The cache is filled first, and the failure is reported rather than swallowed."""
    monkeypatch.setattr(settings, "SPECIFICATION_DIR", str(tmp_path / "nope" / "deeper"))

    def refuse(*args, **kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr("pathlib.Path.mkdir", refuse)

    blueprint = _valid_blueprint()
    summary = save_specification(blueprint)

    # Still usable in this process...
    assert get_specification(summary.specId).serviceName == "thing-service"
    # ...and it is genuinely absent from disk, so the warning was not a false alarm.
    assert not spec_service._specification_path(summary.specId).exists()
