"""What the platform tells you when verification did not run.

Two very different situations produced the same sentence:

    "La compilación o pruebas unitarias fallaron en el sandbox hermético."

It was a hardcoded constant on the `session_blocked` event, emitted even when the sandbox
never executed a build. Reported from session `4634d4ca`, whose own recorded reason was:

    the build did not complete verifiably: the output matches the environment pattern
    'cannot access central'

The operator was told their generated code had failed compilation. It had not been compiled.
The remedy is to prime a Maven cache, not to debug Java -- and the two cases cannot share a
message.
"""
import pytest

from app.sandbox.docker_runner import describe_missing_dependencies
from app.services.pipeline_runner import describe_block_reason

MAVEN_UNRESOLVED = (
    "[ERROR] Failed to execute goal on project help-desk: Could not resolve dependencies "
    "for project com.corp.helpdesk:help-desk:jar:1.0.0: The following artifacts could not "
    "be resolved: org.postgresql:postgresql:jar:42.7.1 (absent), "
    "org.projectlombok:lombok:jar:1.18.30 (absent), "
    "org.springframework.boot:spring-boot-starter-actuator:jar:3.2.3 (absent): Cannot "
    "access central in offline mode and the artifact has not been downloaded from it before."
)


# ---------------------------------------------------------------------------
# The blocked reason distinguishes "failed" from "not measured"
# ---------------------------------------------------------------------------
def test_a_verification_that_never_ran_is_not_reported_as_a_code_failure():
    reason = describe_block_reason(
        fallback_used=True, fallback_reason="the offline Maven cache is missing postgresql"
    )

    assert "no llegó a ejecutar" in reason
    assert "no hay resultado de pruebas" in reason
    # The specific cause survives into the message, or the operator still cannot act.
    assert "offline Maven cache" in reason


def test_a_real_failure_still_says_the_code_failed():
    reason = describe_block_reason(fallback_used=False)

    assert "fallaron" in reason
    assert "no llegó a ejecutar" not in reason


def test_the_two_reasons_are_never_identical():
    """The regression, expressed directly: these were the same string."""
    assert describe_block_reason(fallback_used=True, fallback_reason="x") != describe_block_reason(
        fallback_used=False
    )


def test_a_missing_reason_does_not_leave_a_dangling_label():
    reason = describe_block_reason(fallback_used=True, fallback_reason="")

    assert "Motivo:" not in reason
    assert reason.endswith("resultado de pruebas.")


# ---------------------------------------------------------------------------
# The environment cause is named, so it can be acted on
# ---------------------------------------------------------------------------
def test_the_missing_artifacts_are_named():
    described = describe_missing_dependencies(MAVEN_UNRESOLVED)

    assert described is not None
    assert "org.postgresql:postgresql:jar:42.7.1" in described
    assert "org.projectlombok:lombok:jar:1.18.30" in described
    assert "spring-boot-starter-actuator" in described
    assert "Verification did NOT run" in described, (
        "the message must not leave the reader thinking the code was checked"
    )


def test_the_project_itself_is_not_reported_as_a_missing_dependency():
    """The same sentence names the project before the list; it is not a missing artifact.

    The first version of this function reported `com.corp.helpdesk:help-desk:jar:1.0.0` as
    something to fetch.
    """
    described = describe_missing_dependencies(MAVEN_UNRESOLVED)

    assert "help-desk:jar" not in described
    assert "com.corp.helpdesk" not in described


def test_a_successful_build_reports_nothing_missing():
    assert describe_missing_dependencies("BUILD SUCCESS") is None
    assert describe_missing_dependencies("") is None


def test_the_list_is_bounded():
    """A cold cache can name hundreds; a message nobody reads is not a message."""
    output = (
        "The following artifacts could not be resolved: "
        + ", ".join(f"g{i}:a{i}:jar:1.0" for i in range(20))
        + " (absent)"
    )

    described = describe_missing_dependencies(output, limit=6)

    assert "(+14 more)" in described
    assert described.count("jar:") == 6


def test_duplicates_are_collapsed():
    output = (
        "The following artifacts could not be resolved: "
        "org.postgresql:postgresql:jar:42.7.1 (absent), "
        "org.postgresql:postgresql:jar:42.7.1 (absent)"
    )

    described = describe_missing_dependencies(output)

    assert "1 artifact(s)" in described
