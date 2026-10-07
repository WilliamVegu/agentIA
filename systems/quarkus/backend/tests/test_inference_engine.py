"""Tests for the architecture-first inference (levantando_observaciones)."""
import pytest

from app.models.blueprint import (
    ArchitectureBlueprint,
    DomainEntity,
    EntityAttribute,
    InputInterface,
    UserStoryRecord,
    AcceptanceScenarioRecord,
)
from app.models.architecture_plan import ArchitecturePlan
from app.services import architecture_catalog as catalog
from app.services.inference_engine import infer_architecture


def make_blueprint(**kw) -> ArchitectureBlueprint:
    entity = DomainEntity(
        name="Order",
        tableName="orders",
        attributes=[EntityAttribute(name="id", type="Long", isPrimaryKey=True)],
    )
    story = UserStoryRecord(
        id="US-1", role="cliente", intent="crear pedido", benefit="registrar",
        scenarios=[AcceptanceScenarioRecord(scenarioId="AC-1", given="dado", when="cuando", then="entonces")],
    )
    return ArchitectureBlueprint(
        serviceName="order-service",
        packageName="com.corp.order",
        entities=[entity],
        userStories=[story],
        **kw,
    )


# --- catalog ---

def test_catalog_profiles():
    assert catalog.profile_names() == ["layered", "hexagonal", "hexagonal-ddd"]


def test_catalog_hexagonal_modules():
    mods = catalog.modules_for("hexagonal")
    assert mods == ["domain", "application", "infrastructure", "adapter-in/rest", "adapter-out/db"]


def test_catalog_build_tool_default():
    assert catalog.build_tool_for("layered") == "maven"


def test_catalog_unknown_profile_raises():
    with pytest.raises(KeyError):
        catalog.get_profile("nope")


# --- inference: profile ---

def test_infer_default_no_interface():
    plan = infer_architecture(make_blueprint())
    assert isinstance(plan, ArchitecturePlan)
    assert plan.profile == "layered"
    assert plan.buildTool == "maven"
    assert plan.databaseType == "postgresql"  # respeta databaseMode por defecto


def test_infer_explicit_hexagonal():
    plan = infer_architecture(make_blueprint(inputInterface=InputInterface(architecturePreference="hexagonal")))
    assert plan.profile == "hexagonal"
    assert "adapter-in/rest" in plan.modules


def test_infer_hexagonal_from_messaging():
    plan = infer_architecture(make_blueprint(inputInterface=InputInterface(integrations=["messaging"])))
    assert plan.profile == "hexagonal"


def test_infer_layered_from_crud():
    plan = infer_architecture(make_blueprint(inputInterface=InputInterface(integrations=["none"], requestVolume="low")))
    assert plan.profile == "layered"


# --- inference: database ---

def test_infer_high_volume_postgres():
    plan = infer_architecture(make_blueprint(inputInterface=InputInterface(requestVolume="high")))
    assert plan.databaseType == "postgresql"


def test_infer_low_volume_h2():
    plan = infer_architecture(make_blueprint(inputInterface=InputInterface(requestVolume="low")))
    assert plan.databaseType == "h2"


def test_infer_document_degrades_to_postgres():
    plan = infer_architecture(make_blueprint(inputInterface=InputInterface(dataNeeds=["document"])))
    assert plan.databaseType == "postgresql"
    assert any("document" in r for r in plan.reasons)


# --- inference: build tool + libraries ---

def test_infer_build_tool_preference():
    plan = infer_architecture(make_blueprint(inputInterface=InputInterface(buildToolPreference="gradle")))
    assert plan.buildTool == "gradle"


def test_infer_libraries_are_allowlisted():
    plan = infer_architecture(make_blueprint(inputInterface=InputInterface(requestVolume="high")))
    for lib in plan.libraries:
        assert lib in catalog.ALLOWED_DEPENDENCIES["web"] + catalog.ALLOWED_DEPENDENCIES["persistence"] + \
            catalog.ALLOWED_DEPENDENCIES["test"] + ["postgresql", "h2"]
    assert "spring-boot-starter-data-jpa" in plan.libraries
    assert "postgresql" in plan.libraries
    assert "spring-boot-starter-test" in plan.libraries


def test_infer_reasons_recorded():
    plan = infer_architecture(make_blueprint(inputInterface=InputInterface(requestVolume="high", architecturePreference="hexagonal")))
    assert len(plan.reasons) >= 2
