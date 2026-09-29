"""QE coverage: the API surface a client actually meets.

Two areas that were thinly covered:

* ``app/main.py``'s centralised error handlers (68%). Principle III makes the error
  envelope a contract, and a contract nobody tests is a contract that drifts. A
  client parsing ``status``/``message``/``details`` should be able to rely on it.
* ``app/api/routes_requirements.py``'s session endpoints (42%). The LLM
  transform/refine paths were covered; the endpoints the UI uses to *read back* and
  *save* a requirements draft were not, including the 404 for an unknown session.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.main import app, generic_exception_handler, validation_exception_handler  # noqa: E402
from app.models.session import (  # noqa: E402
    GenerationSessionDB,
    SessionLocal,
    SessionPhase,
    SessionStatus,
)

client = TestClient(app, raise_server_exceptions=False)
SESSION_ID = "qe-requirements-session"


# ---------------------------------------------------------------------------
# The error envelope (Principle III)
# ---------------------------------------------------------------------------
def test_the_generic_handler_returns_the_documented_500_envelope():
    response = asyncio.run(generic_exception_handler(None, ValueError("boom")))

    assert response.status_code == 500
    body = json.loads(response.body)
    assert body["status"] == 500
    assert body["message"] == "Internal server error occurred"
    assert "boom" in body["details"][0], "the cause is hidden from the operator"
    assert "timestamp" in body


def test_the_validation_handler_returns_the_documented_400_envelope():
    from fastapi.exceptions import RequestValidationError

    exc = RequestValidationError([
        {"loc": ("body", "serviceName"), "msg": "Field required", "type": "missing"}
    ])

    response = asyncio.run(validation_exception_handler(None, exc))

    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["status"] == 400
    assert body["message"] == "Validation error in specification payload"
    assert any("serviceName" in detail for detail in body["details"])
    assert "timestamp" in body


def test_an_invalid_request_body_gets_the_400_envelope_from_the_live_app():
    """End to end through the ASGI stack, not just the handler in isolation."""
    response = client.post("/api/v1/specifications", json={"serviceName": "Bad Service Name"})

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == 400
    assert "message" in body and "details" in body


def test_the_health_endpoint_reports_the_app_identity():
    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UP"
    assert body["app"] == settings.APP_NAME
    assert body["version"] == settings.APP_VERSION


# ---------------------------------------------------------------------------
# Requirements read-back and save
# ---------------------------------------------------------------------------
@pytest.fixture
def session(tmp_path, monkeypatch):
    """A session row plus a redirected workspace, cleaned up afterwards."""
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    workspace = tmp_path / SESSION_ID
    workspace.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == SESSION_ID).delete()
        db.add(GenerationSessionDB(
            id=SESSION_ID, spec_id="spec-qe", spec_name="order-service",
            status=SessionStatus.QUEUED, phase=SessionPhase.INITIALIZATION,
            current_lifecycle_phase="REQUIREMENTS", lifecycle_mode="GUIDED_STEP",
            repair_attempts=0,
        ))
        db.commit()
    finally:
        db.close()

    yield workspace

    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == SESSION_ID).delete()
        db.commit()
    finally:
        db.close()


def test_reading_requirements_for_an_unknown_session_is_a_404():
    response = client.get("/api/v1/requirements/sessions/qe-no-such-session")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_reading_requirements_without_files_reports_no_draft(session):
    response = client.get(f"/api/v1/requirements/sessions/{SESSION_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["sessionId"] == SESSION_ID
    assert body["serviceName"] == "order-service"
    assert body["rawPrompt"] == ""
    assert body["hasDraft"] is False
    assert body["draft"] is None


def test_reading_requirements_returns_the_prompt_and_the_stored_stories(session):
    (session / "spec.md").write_text("# Order Service\n\nGestionar órdenes.\n", encoding="utf-8")
    stories = [{
        "id": "US-1", "priority": "P1", "role": "Customer",
        "intent": "create an order", "benefit": "buy things",
        "scenarios": [{"scenarioId": "AC-1.1", "given": "a valid cart", "when": "the order is submitted", "then": "201 Created is returned"}],
    }]
    (session / "user_stories.json").write_text(json.dumps(stories), encoding="utf-8")

    response = client.get(f"/api/v1/requirements/sessions/{SESSION_ID}")

    assert response.status_code == 200
    body = response.json()
    assert "Gestionar órdenes" in body["rawPrompt"]
    assert body["hasDraft"] is True
    assert body["draft"]["serviceName"] == "order-service"
    assert body["draft"]["packageName"] == "com.corp.order.service"
    assert body["draft"]["userStories"] == stories


def test_reading_requirements_tolerates_a_corrupt_stories_file(session):
    """A malformed draft must not turn a read into a 500."""
    (session / "user_stories.json").write_text("{not json", encoding="utf-8")

    response = client.get(f"/api/v1/requirements/sessions/{SESSION_ID}")

    assert response.status_code == 200
    assert response.json()["hasDraft"] is False


def test_saving_requirements_persists_the_draft_and_reports_the_count(session):
    payload = {
        "serviceName": "order-service",
        "packageName": "com.corp.order",
        "basePort": 8080,
        "entities": [],
        "userStories": [
            {
                "id": "US-1", "priority": "P1", "role": "Customer",
                "intent": "create an order", "benefit": "buy things",
                "scenarios": [{"scenarioId": "AC-1.1", "given": "a valid cart", "when": "the order is submitted", "then": "201 Created is returned"}],
            },
            {
                "id": "US-2", "priority": "P2", "role": "Admin",
                "intent": "list orders", "benefit": "audit",
                "scenarios": [{"scenarioId": "AC-2.1", "given": "an authenticated admin", "when": "orders are listed", "then": "200 OK is returned"}],
            },
        ],
        "assumptions": [],
        "markdownSpec": "# Order Service\n\nSaved by the QE test.\n",
    }

    response = client.post(f"/api/v1/requirements/sessions/{SESSION_ID}/save", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "SAVED"
    assert response.json()["storiesCount"] == 2

    stored = json.loads((session / "user_stories.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in stored] == ["US-1", "US-2"]
    assert "Saved by the QE test" in (session / "spec.md").read_text(encoding="utf-8")


def test_saving_requirements_without_a_markdown_spec_leaves_the_file_absent(session):
    payload = {
        "serviceName": "order-service", "packageName": "com.corp.order", "basePort": 8080,
        "entities": [], "userStories": [], "assumptions": [],
    }

    response = client.post(f"/api/v1/requirements/sessions/{SESSION_ID}/save", json=payload)

    assert response.status_code == 200
    assert response.json()["storiesCount"] == 0
    assert not (session / "spec.md").exists(), "an empty spec.md was written"


def test_a_scenario_shorter_than_the_contract_allows_is_rejected(session):
    """The draft model requires at least 3 characters per Given/When/Then clause.

    Pinned here because it is a real API contract a QE will meet: a client posting
    placeholder text gets the 400 envelope rather than a stored draft. The first
    draft of this file used single-character clauses and was rejected, which is how
    the constraint was found.
    """
    payload = {
        "serviceName": "order-service", "packageName": "com.corp.order", "basePort": 8080,
        "entities": [], "assumptions": [],
        "userStories": [{
            "id": "US-1", "priority": "P1", "role": "Customer",
            "intent": "create an order", "benefit": "buy things",
            "scenarios": [{"scenarioId": "AC-1.1", "given": "g", "when": "w", "then": "t"}],
        }],
    }

    response = client.post(f"/api/v1/requirements/sessions/{SESSION_ID}/save", json=payload)

    assert response.status_code == 400
    assert response.json()["status"] == 400
    assert not (session / "user_stories.json").exists(), "an invalid draft was persisted"


# ---------------------------------------------------------------------------
# Offline mode does not use the prompt -- pinned as a contract, not a surprise
# ---------------------------------------------------------------------------
def test_the_offline_decomposition_ignores_the_prompt_and_declares_itself():
    """Two unrelated prompts produce byte-identical output, and it says so.

    Reported from a real session: a "cafe" service and a "cevichez0" service showed
    the same three user stories, because `_generate_mock_decomposition` never reads
    `raw_text`. That read as hardcoded output -- correctly, since it is one.

    Pinned here so the behaviour is a stated contract rather than a discovery: if the
    offline path is ever made prompt-aware, this test fails and whoever changes it
    must also drop the OFFLINE SAMPLE marker.
    """
    from app.services.requirements_service import _generate_mock_decomposition

    first = _generate_mock_decomposition(raw_text="cafe", service_name="cafe")
    second = _generate_mock_decomposition(raw_text="un ceviche con leche de tigre", service_name="cevichez0")

    assert [s.intent for s in first.userStories] == [s.intent for s in second.userStories]
    assert [e.name for e in first.entities] == [e.name for e in second.entities] == ["Order"]

    assert "OFFLINE SAMPLE" in first.assumptions[0], (
        "the offline decomposition no longer declares itself a fixed template; the UI "
        "would again present it as a response to the prompt"
    )
    assert "NOT used" in first.assumptions[0]


def test_the_generic_handler_also_logs_the_traceback(caplog):
    """A 500 with no logged cause is an undiagnosable 500.

    Eight `POST /requirements/transform` 500s appeared in the access log with not one
    line saying why, so the cause (DeepSeek rejecting `response_format`) had to be
    reproduced by hand from outside the running server. The handler now logs the stack.
    """
    import logging

    with caplog.at_level(logging.ERROR, logger="app.main"):
        asyncio.run(generic_exception_handler(None, ValueError("deepseek said no")))

    assert any("deepseek said no" in record.getMessage() for record in caplog.records), (
        "the handler returned an envelope without recording why"
    )


def test_the_handler_still_answers_when_the_request_object_is_unusable():
    """An error handler must not fail while reporting an error."""
    response = asyncio.run(generic_exception_handler(None, ValueError("boom")))

    assert response.status_code == 500
    assert json.loads(response.body)["status"] == 500
