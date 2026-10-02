"""The post-generation corrections must reach every generation path.

There are two: the graph streamed by `routes_session`, and `pipeline_runner` (quick-start,
autopilot, lifecycle). They run the same stages through different runners.

The corrections were wired into `routes_session`'s node loop only. A real run proved the
cost -- session `01f2041f` blocked with

    package org.springframework.test.context.bean.override.mockito does not exist
    cannot find symbol: class MockitoBean

which is precisely what `normalise_generated_tests` exists to fix, on the path that had not
been wired. Applying it by hand to that workspace gave BUILD SUCCESS.

`run_stages` is the shared entry point for the pipeline path, so the corrections live there
now. A correction attached to each caller is a correction that will be missing from the next
caller.
"""
from app.orchestrator.stages.runner import run_stages


def test_run_stages_corrects_the_workspace_it_just_generated(tmp_path):
    """The pipeline path: no stage runs, and the corrections still apply."""
    target = tmp_path / "src/test/java/com/corp/x/controller/FooControllerTest.java"
    target.parent.mkdir(parents=True)
    target.write_text(
        "package com.corp.x.controller;\n"
        "import org.springframework.test.context.bean.override.mockito.MockitoBean;\n"
        "@WebMvcTest(FooController.class)\n"
        "class FooControllerTest {\n"
        "    @MockitoBean private FooService service;\n"
        "}\n",
        encoding="utf-8",
    )

    run_stages({"workspace_path": str(tmp_path)}, stages=[])

    text = target.read_text(encoding="utf-8")
    assert "@MockitoBean" not in text, "the pipeline path must get the same corrections"
    assert "@MockBean private FooService service;" in text
    assert "import org.springframework.boot.test.mock.mockito.MockBean;" in text


def test_the_advice_correction_also_applies(tmp_path):
    """An unmapped path must be answered 404 on this path too."""
    target = tmp_path / "src/main/java/com/corp/x/controller/GlobalExceptionHandler.java"
    target.parent.mkdir(parents=True)
    target.write_text(
        "package com.corp.x.controller;\n"
        "import org.springframework.web.bind.annotation.RestControllerAdvice;\n"
        "@RestControllerAdvice\n"
        "public class GlobalExceptionHandler {\n"
        "}\n",
        encoding="utf-8",
    )

    run_stages({"workspace_path": str(tmp_path)}, stages=[])

    assert "NoResourceFoundException" in target.read_text(encoding="utf-8")


def test_a_workspace_with_nothing_to_correct_is_untouched(tmp_path):
    source = tmp_path / "src/main/java/com/corp/x/Application.java"
    source.parent.mkdir(parents=True)
    original = "package com.corp.x;\npublic class Application {}\n"
    source.write_text(original, encoding="utf-8")

    run_stages({"workspace_path": str(tmp_path)}, stages=[])

    assert source.read_text(encoding="utf-8") == original


def test_a_missing_workspace_does_not_break_the_run():
    """A correction must never fail a generation that otherwise succeeded."""
    assert run_stages({}, stages=[]) == {}


def test_a_correction_failure_does_not_propagate(tmp_path, monkeypatch):
    """Best-effort: a broken correction must not turn a good generation into a failure."""
    def explode(*args, **kwargs):
        raise RuntimeError("correction is broken")

    monkeypatch.setattr(
        "app.services.generated_code_fixes.normalise_generated_tests", explode, raising=False
    )

    state = run_stages({"workspace_path": str(tmp_path)}, stages=[])

    assert state["workspace_path"] == str(tmp_path)
