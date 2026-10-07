"""Regression: the tuned architecture/data-model designs must survive tab navigation.

The bug: the Architecture and Models-SQL tabs held the LLM design only in React
state, so navigating away (reload/resume/history) lost it — the tabs read
``architecture.json`` / ``domain_model.json``, which only contained the mechanical
build-time derivation, not the user's tuned design.

Fix: a save endpoint persists the tuned design; the existing artifact-content
endpoint reads it back. This test locks the round-trip at the API seam.
"""
import json

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_architecture_design_save_and_retrieve(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    sid = "sess-arch-retrieval"
    design = {"serviceName": "order-service", "components": [{"name": "OrderController", "layer": "controller"}]}

    save = client.post(f"/api/v1/architecture/sessions/{sid}/save", json=design)
    assert save.status_code == 200

    read = client.get(f"/api/v1/sessions/{sid}/artifacts/content", params={"path": "architecture.json"})
    assert read.status_code == 200
    assert json.loads(read.text)["serviceName"] == "order-service"
    assert json.loads(read.text)["components"][0]["name"] == "OrderController"


def test_models_design_save_and_retrieve(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    sid = "sess-models-retrieval"
    design = {"serviceName": "order-service", "schemaSql": "CREATE TABLE orders (id bigint)"}

    save = client.post(f"/api/v1/models/sessions/{sid}/save", json=design)
    assert save.status_code == 200

    read = client.get(f"/api/v1/sessions/{sid}/artifacts/content", params={"path": "domain_model.json"})
    assert read.status_code == 200
    assert json.loads(read.text)["serviceName"] == "order-service"
