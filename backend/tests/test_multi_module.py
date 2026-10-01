"""Tests for the multi-module layout ("capa X en proyecto Y") — item 4."""
from app.orchestrator.stages.deterministic import module_layout
from app.orchestrator.stages.deterministic.scaffolder import emit as scaffold_emit
from app.orchestrator.stages.deterministic.domain import emit as domain_emit

HEX = {"profile": "hexagonal", "buildTool": "maven", "databaseType": "h2",
       "modules": ["domain", "application", "infrastructure", "adapter-in/rest", "adapter-out/db"],
       "libraries": [], "reasons": []}
LAYERED = {"profile": "layered", "buildTool": "maven", "databaseType": "h2",
           "modules": ["controller", "service", "repository", "model"],
           "libraries": [], "reasons": []}


def _blueprint(input_interface=None):
    bp = {
        "serviceName": "order-service", "packageName": "com.corp.order",
        "basePort": 8080, "databaseMode": "PostgreSQL",
        "entities": [{"name": "Order", "tableName": "orders",
                      "attributes": [{"name": "id", "type": "Long", "isPrimaryKey": True}]}],
        "userStories": [{"id": "US-1", "priority": "P1", "role": "cliente", "intent": "crear",
                         "benefit": "registrar",
                         "scenarios": [{"scenarioId": "AC-1", "given": "dado", "when": "cuando", "then": "entonces"}]}],
    }
    if input_interface is not None:
        bp["inputInterface"] = input_interface
    return bp


# --- layout ---

def test_layered_is_single_module():
    assert module_layout.is_multi_module(None) is False
    assert module_layout.is_multi_module(LAYERED) is False


def test_hexagonal_is_multi_module():
    assert module_layout.is_multi_module(HEX) is True


def test_module_prefix_mapping():
    assert module_layout.module_prefix_for("SCAFFOLDER", HEX) == "bootstrap/"
    assert module_layout.module_prefix_for("DOMAIN", HEX) == "model/"
    assert module_layout.module_prefix_for("SERVICE", HEX) == "service/"
    assert module_layout.module_prefix_for("CONTROLLER", HEX) == "controller/"
    assert module_layout.module_prefix_for("TEST", HEX) == "bootstrap/"
    assert module_layout.module_prefix_for("DOMAIN", LAYERED) == ""


# --- reactor poms ---

def test_reactor_parent_pom():
    poms = module_layout.render_reactor_poms("order-service", "com.corp.order", HEX)
    parent = poms["pom.xml"]
    assert "<packaging>pom</packaging>" in parent
    for m in ["model", "service", "controller", "bootstrap"]:
        assert f"<module>{m}</module>" in parent


def test_reactor_child_poms_present():
    poms = module_layout.render_reactor_poms("order-service", "com.corp.order", HEX)
    for m in ["model", "service", "controller", "bootstrap"]:
        assert f"{m}/pom.xml" in poms


def test_reactor_module_dependency_graph():
    poms = module_layout.render_reactor_poms("order-service", "com.corp.order", HEX)
    assert "<artifactId>order-service-model</artifactId>" in poms["service/pom.xml"]     # service depends on model
    assert "<artifactId>order-service-service</artifactId>" in poms["controller/pom.xml"]  # controller depends on service
    # model depends on no other reactor module (only its own artifactId appears)
    for other in ["service", "controller", "bootstrap"]:
        assert f"order-service-{other}" not in poms["model/pom.xml"]


# --- scaffolder wiring ---

def test_scaffolder_emits_reactor_for_hexagonal(tmp_path):
    state = {"blueprint": _blueprint({"architecturePreference": "hexagonal"}),
             "workspace_path": str(tmp_path), "generated_files": {}, "logs": []}
    result = scaffold_emit(state)
    files = result["generated_files"]
    assert "<packaging>pom</packaging>" in files["pom.xml"]
    assert "bootstrap/pom.xml" in files and "model/pom.xml" in files
    # Application class + config land in bootstrap
    assert any(k.startswith("bootstrap/src/main/java/") and k.endswith("Application.java") for k in files)
    assert "bootstrap/src/main/resources/application.yml" in files


def test_scaffolder_single_module_when_layered(tmp_path):
    state = {"blueprint": _blueprint(), "workspace_path": str(tmp_path), "generated_files": {}, "logs": []}
    result = scaffold_emit(state)
    files = result["generated_files"]
    assert "pom.xml" in files and "bootstrap/pom.xml" not in files
    assert "<packaging>pom</packaging>" not in files["pom.xml"]


# --- downstream stage re-pointing ---

def test_domain_stage_writes_into_model_module(tmp_path):
    state = {"blueprint": _blueprint({"architecturePreference": "hexagonal"}),
             "workspace_path": str(tmp_path), "generated_files": {},
             "logs": [], "architecture_plan": HEX}
    result = domain_emit(state)
    paths = list(result["generated_files"].keys())
    assert all(p.startswith("model/src/main/java/") for p in paths), paths
