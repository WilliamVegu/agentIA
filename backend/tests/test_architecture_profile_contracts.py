from app.orchestrator.stages.runner import architecture_profile_violations
from app.orchestrator.stages.architecture_profiles import hexagonal_instruction


def state():
    return {"blueprint": {"serviceName": "library", "packageName": "com.example.library",
                          "entities": [{"name": "Book", "attributes": []}],
                          "inputInterface": {"architecturePreference": "hexagonal", "buildToolPreference": "gradle"}},
            "generated_files": {}}


def test_layered_service_is_rejected_for_hexagonal_profile():
    candidate = {"src/main/java/com/example/library/service/impl/BookServiceImpl.java": "class BookServiceImpl {}"}
    assert architecture_profile_violations(candidate, "SERVICE", state())


def test_hexagonal_application_service_is_accepted():
    candidate = {"src/main/java/com/example/library/application/service/BookApplicationService.java": "class BookApplicationService {}"}
    assert not architecture_profile_violations(candidate, "SERVICE", state())


def test_maven_cannot_replace_requested_gradle():
    assert architecture_profile_violations({"pom.xml": "<project/>"}, "SCAFFOLDER", state())
    assert not architecture_profile_violations({"build.gradle": "plugins {}"}, "SCAFFOLDER", state())


def test_hexagonal_contract_replaces_layered_default():
    instruction = hexagonal_instruction("SERVICE", "default-layered-instruction")
    assert "default-layered-instruction" not in instruction
    assert "application/service" in instruction
    assert "infrastructure/adapter/out" in instruction
