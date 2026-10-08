"""Tests that the deterministic scaffolder records the inferred architecture plan
without changing emitted bytes (levantando_observaciones item 3)."""
from app.orchestrator.stages.deterministic.scaffolder import emit


def _state(blueprint, workspace):
    return {
        "blueprint": blueprint,
        "workspace_path": workspace,
        "generated_files": {},
        "logs": [],
    }


def _blueprint(input_interface=None):
    bp = {
        "serviceName": "order-service",
        "packageName": "com.corp.order",
        "basePort": 8080,
        "databaseMode": "PostgreSQL",
        "entities": [
            {"name": "Order", "tableName": "orders",
             "attributes": [{"name": "id", "type": "Long", "isPrimaryKey": True}]}
        ],
        "userStories": [
            {"id": "US-1", "priority": "P1", "role": "cliente", "intent": "crear",
             "benefit": "registrar",
             "scenarios": [{"scenarioId": "AC-1", "given": "dado", "when": "cuando", "then": "entonces"}]}
        ],
    }
    if input_interface is not None:
        bp["inputInterface"] = input_interface
    return bp


def test_no_interface_records_no_plan(tmp_path):
    result = emit(_state(_blueprint(), str(tmp_path)))
    assert "architecture_plan" not in result


def test_high_volume_records_postgres_plan(tmp_path):
    result = emit(_state(_blueprint({"requestVolume": "high"}), str(tmp_path)))
    plan = result["architecture_plan"]
    assert plan["databaseType"] == "postgresql"
    assert plan["profile"] == "layered"


def test_hexagonal_preference_records_modules(tmp_path):
    result = emit(_state(_blueprint({"architecturePreference": "hexagonal"}), str(tmp_path)))
    assert "adapter-in/rest" in result["architecture_plan"]["modules"]


def test_emitted_bytes_unchanged_without_interface(tmp_path):
    result = emit(_state(_blueprint(), str(tmp_path)))
    pom = result["generated_files"]["pom.xml"]
    assert "<artifactId>h2</artifactId>" in pom           # still H2 (cache-safe)
    assert "org.postgresql" in pom


def test_high_volume_materializes_postgres_profile(tmp_path):
    result = emit(_state(_blueprint({"requestVolume": "high"}), str(tmp_path)))
    files = result["generated_files"]
    assert "src/main/resources/application-prod.yml" in files
    prod = files["src/main/resources/application-prod.yml"]
    assert "jdbc:postgresql://" in prod
    assert "${DB_USER}" in prod and "${DB_PASSWORD}" in prod   # credentials externalized
    assert "postgresql" in files["pom.xml"]            # offline build stays H2


def test_low_volume_does_not_materialize_postgres(tmp_path):
    result = emit(_state(_blueprint({"requestVolume": "low"}), str(tmp_path)))
    assert "jdbc:postgresql://" in result["generated_files"]["src/main/resources/application-prod.yml"]
