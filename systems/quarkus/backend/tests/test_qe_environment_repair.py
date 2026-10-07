"""QE coverage: sandbox environment checks and Maven diagnostic parsing.

Two modules that were effectively untested before this file existed:

* ``app/sandbox/verify_cache.py`` — **0% covered**. It decides whether the host can
  run the hermetic sandbox at all, so every branch matters: a false "ready" sends a
  session into a build that cannot run, and a false "not installed" blocks a host
  that is perfectly capable.
* ``app/orchestrator/repair.py`` — 63%. The uncovered part is the *fallback* ladder:
  what the parser returns when the Maven output does not match the strict patterns.
  Those are the paths taken by unusual real-world build output, which is exactly when
  a diagnostic matters.

No container command is executed: ``subprocess.run`` is replaced in every test. The
constraint that the agent's shell cannot reach the runtime does not apply to the
suite, but a test that shells out to Docker would be non-deterministic on any host.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.orchestrator.repair import (  # noqa: E402
    can_retry,
    format_repair_prompt,
    parse_maven_errors,
)
from app.sandbox import verify_cache  # noqa: E402


class _Proc:
    """Stand-in for ``subprocess.CompletedProcess``."""

    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _docker_stub(version=0, info=0, image=0, image_raises=False, info_raises=False):
    """A fake ``subprocess.run`` answering the three Docker probes by command."""
    def run(cmd, *args, **kwargs):
        joined = " ".join(cmd)
        if "--version" in joined:
            return _Proc(version)
        if "info" in joined:
            if info_raises:
                raise RuntimeError("daemon socket exploded")
            return _Proc(info)
        if "image" in joined and "inspect" in joined:
            if image_raises:
                raise RuntimeError("inspect exploded")
            return _Proc(image)
        raise AssertionError(f"unexpected command: {joined}")
    return run


# ---------------------------------------------------------------------------
# verify_docker_environment -- the "can this host verify anything?" probe
# ---------------------------------------------------------------------------
def test_a_fully_provisioned_host_reports_ready(monkeypatch):
    monkeypatch.setattr(verify_cache.subprocess, "run", _docker_stub())

    result = verify_cache.verify_docker_environment()

    assert result["docker_installed"] is True
    assert result["docker_running"] is True
    assert result["image_available"] is True
    assert "pre-cached" in result["message"]


def test_a_host_without_the_cli_reports_not_installed(monkeypatch):
    def run(cmd, *args, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(verify_cache.subprocess, "run", run)

    result = verify_cache.verify_docker_environment()

    assert result["docker_installed"] is False
    assert result["docker_running"] is False
    assert "not found" in result["message"]


def test_a_cli_that_errors_is_not_reported_as_installed(monkeypatch):
    """Non-zero from `docker --version` must stop the probe, not continue."""
    monkeypatch.setattr(verify_cache.subprocess, "run", _docker_stub(version=1))

    result = verify_cache.verify_docker_environment()

    assert result["docker_installed"] is False
    assert result["docker_running"] is False, "the probe continued past a failed CLI check"
    assert "non-zero" in result["message"]


def test_a_stopped_daemon_is_reported(monkeypatch):
    monkeypatch.setattr(verify_cache.subprocess, "run", _docker_stub(info=1))

    result = verify_cache.verify_docker_environment()

    assert result["docker_installed"] is True
    assert result["docker_running"] is False
    assert "daemon is not running" in result["message"]
    assert result["image_available"] is False, "an image was reported on a dead daemon"


def test_a_missing_image_is_named_with_the_pull_command(monkeypatch):
    monkeypatch.setattr(verify_cache.subprocess, "run", _docker_stub(image=1))

    result = verify_cache.verify_docker_environment()

    assert result["docker_running"] is True
    assert result["image_available"] is False
    assert "not found locally" in result["message"]
    assert result["image_name"] in result["message"], "the operator is not told which image"


def test_an_exception_from_the_info_probe_is_caught(monkeypatch):
    monkeypatch.setattr(verify_cache.subprocess, "run", _docker_stub(info_raises=True))

    result = verify_cache.verify_docker_environment()

    assert result["docker_running"] is False
    assert "Error querying Docker daemon" in result["message"]


def test_an_exception_from_the_image_probe_is_caught(monkeypatch):
    """The final probe has no early return, so it must not escape."""
    monkeypatch.setattr(verify_cache.subprocess, "run", _docker_stub(image_raises=True))

    result = verify_cache.verify_docker_environment()

    assert result["docker_running"] is True
    assert result["image_available"] is False
    assert "Error inspecting image" in result["message"]


def test_the_report_names_the_configured_image_and_cache(monkeypatch):
    monkeypatch.setattr(verify_cache.subprocess, "run", _docker_stub())

    result = verify_cache.verify_docker_environment()

    from app.config import settings

    assert result["image_name"] == settings.DOCKER_IMAGE
    assert result["maven_cache_dir"] == settings.MAVEN_CACHE_DIR


# ---------------------------------------------------------------------------
# parse_maven_errors -- the fallback ladder
# ---------------------------------------------------------------------------
def test_a_located_compilation_error_is_parsed_with_its_position():
    output = (
        "[ERROR] COMPILATION ERROR :\n"
        "[ERROR] /ws/src/main/java/com/corp/order/OrderService.java:[28,15] cannot find symbol\n"
    )

    diag = parse_maven_errors(output)

    assert diag["error_type"] == "COMPILATION"
    assert diag["failed_file"].endswith("OrderService.java")
    assert diag["line_number"] == 28
    assert diag["column_number"] == 15
    assert "cannot find symbol" in diag["summary"]


def test_a_compilation_error_without_a_location_uses_the_generic_fallback():
    """The strict regex needs file:[line,col]; real output sometimes omits it."""
    output = "[ERROR] COMPILATION ERROR in ModuleBuilder.java but no located line"

    diag = parse_maven_errors(output)

    assert diag["error_type"] == "COMPILATION"
    assert diag["failed_file"].endswith(".java")
    assert diag["summary"] == "Compilation error detected in source tree"
    assert "ModuleBuilder" in diag["details"]


def test_a_compilation_error_with_no_java_file_names_the_source_tree():
    output = "[ERROR] package does not exist"

    diag = parse_maven_errors(output)

    assert diag["error_type"] == "COMPILATION"
    assert diag["failed_file"] == "src/main/java", "a missing file name must not become None"


def test_a_located_surefire_failure_names_class_and_method():
    output = "[ERROR] OrderServiceTest.shouldCreateOrder:45 expected: <SUCCESS> but was: <PENDING>"

    diag = parse_maven_errors(output)

    assert diag["error_type"] == "TEST_FAILURE"
    assert diag["class_name"] == "OrderServiceTest"
    assert diag["method_name"] == "shouldCreateOrder"
    assert diag["line_number"] == 45
    assert diag["failed_file"] == "OrderServiceTest.java"


def test_a_surefire_failure_without_a_line_uses_the_class_fallback():
    """Uncovered before this test: the `SomeTest.method` fallback."""
    output = "There are test failures. InventoryServiceTest.verifyStock threw an exception"

    diag = parse_maven_errors(output)

    assert diag["error_type"] == "TEST_FAILURE"
    assert diag["class_name"] == "InventoryServiceTest"
    assert diag["method_name"] == "verifyStock"
    assert diag["summary"] == "Test failure in InventoryServiceTest.verifyStock"
    assert diag["details"] == output.strip()


def test_unrecognised_output_falls_back_to_an_unknown_diagnostic():
    output = "Something went wrong while building the project"

    diag = parse_maven_errors(output)

    assert diag["error_type"] == "UNKNOWN"
    assert diag["failed_file"] == "src/main/java"
    assert diag["summary"] == "Build or test failure requiring adaptive repair"


def test_an_unknown_failure_still_names_a_layer_file_when_one_is_mentioned():
    output = "Failed while assembling PaymentController.java for the build"

    diag = parse_maven_errors(output)

    assert diag["error_type"] == "UNKNOWN"
    assert diag["failed_file"] == "PaymentController.java", (
        "a mentioned layer file is a better pointer than the source-tree root"
    )


def test_a_layer_name_without_the_java_extension_does_not_match():
    """Documents the actual contract, which a first draft of this test got wrong.

    The fallback pattern ends in ``\\.java``, so a bare class name is not treated as
    a file reference and the diagnostic falls back to the source-tree root. That is
    defensible -- guessing a path from a bare word would be inventing one -- but it
    is a real limit on how specific an UNKNOWN diagnostic can be.
    """
    output = "Error processing PaymentController during compilation planning"

    diag = parse_maven_errors(output)

    assert diag["error_type"] == "UNKNOWN"
    assert diag["failed_file"] == "src/main/java"


def test_empty_output_produces_an_unknown_diagnostic_rather_than_raising():
    diag = parse_maven_errors("")

    assert diag["error_type"] == "UNKNOWN"
    assert diag["failed_file"] == "src/main/java"


# ---------------------------------------------------------------------------
# can_retry / format_repair_prompt
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "attempt, maximum, expected",
    [(1, 3, True), (2, 3, True), (3, 3, False), (4, 3, False), (0, 1, True)],
)
def test_the_repair_budget_boundary(attempt, maximum, expected):
    assert can_retry(attempt, maximum) is expected


def test_the_repair_prompt_carries_the_diagnostic_and_the_constitution_rules():
    diag = {
        "error_type": "COMPILATION",
        "failed_file": "OrderService.java",
        "summary": "cannot find symbol",
        "details": "symbol: method setStatus",
    }

    prompt = format_repair_prompt(diag, context="stage DOMAIN")

    assert "COMPILATION" in prompt
    assert "OrderService.java" in prompt
    assert "cannot find symbol" in prompt
    assert "symbol: method setStatus" in prompt
    assert "stage DOMAIN" in prompt
    # The house rules the repair must not break.
    assert "Java 21" in prompt
    assert "Jakarta" in prompt and "javax" in prompt
    assert "Record DTOs" in prompt


def test_the_repair_prompt_states_when_there_is_no_context():
    prompt = format_repair_prompt({"error_type": "UNKNOWN"})

    assert "No additional context" in prompt
    assert "UNKNOWN" in prompt


def test_a_diagnostic_missing_its_fields_does_not_raise():
    """The prompt is built from whatever the parser produced, keys or not."""
    prompt = format_repair_prompt({})

    assert "Error Type: UNKNOWN" in prompt
    assert "Target File: " in prompt
