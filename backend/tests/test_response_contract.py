"""The model-response contract (feature 015 follow-up: the real blocker).

The first real baseline recorded no rule violation anywhere, across five sessions
and 25 stage runs, because **no candidate ever reached the compliance gate**: every
model response failed to parse, so each stage spent its whole correction budget and
persisted nothing. The record then read as "nothing wrong", which is what made a
generation-transport bug look like non-compliance and sent a whole feature in the
wrong direction.

Two halves are pinned here:

* the extractor accepts the shapes a real model actually produces — bare JSON,
  fenced JSON, prose-wrapped JSON, and code blocks whose path is in a heading;
* the request TELLS the model the wire format, so the budget is not spent on
  avoidable rejections.

The safety properties matter as much as the tolerance: a partial set, or a block
whose file cannot be named, must still fail closed. A mis-associated artifact is
worse than a rejected one, because it persists content under the wrong path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.orchestrator.stages.runner import (  # noqa: E402
    extract_artifacts,
    render_stage_request,
)

ARTIFACT_MAP = {
    "artifacts": {
        "pom.xml": "<project/>",
        "src/main/resources/application.yml": "spring:\n  application:\n    name: s\n",
    }
}
BARE_JSON = json.dumps(ARTIFACT_MAP)

HEADED_BLOCKS = (
    "Here is the implementation.\n\n"
    "### src/main/java/com/corp/orders/OrderService.java\n\n"
    "```java\npackage com.corp.orders;\n\npublic class OrderService {}\n```\n\n"
    "### pom.xml\n\n"
    "```xml\n<project/>\n```\n"
)


# ---------------------------------------------------------------------------
# The shapes a real model produces must parse
# ---------------------------------------------------------------------------
def test_bare_json_still_parses():
    artifacts, ok = extract_artifacts(BARE_JSON)
    assert ok is True
    assert artifacts["pom.xml"] == "<project/>"


def test_fenced_json_parses():
    """The single most common real shape, and the one the old parser rejected."""
    artifacts, ok = extract_artifacts("```json\n" + BARE_JSON + "\n```")
    assert ok is True, "a fenced JSON response was rejected; every attempt is spent"
    assert set(artifacts) == set(ARTIFACT_MAP["artifacts"])


def test_prose_wrapped_json_parses():
    artifacts, ok = extract_artifacts("Here are the artifacts:\n\n" + BARE_JSON)
    assert ok is True
    assert artifacts["pom.xml"] == "<project/>"


def test_prose_wrapped_fenced_json_parses():
    text = "Sure — here you go:\n\n```json\n" + BARE_JSON + "\n```\n\nLet me know!"
    artifacts, ok = extract_artifacts(text)
    assert ok is True
    assert set(artifacts) == set(ARTIFACT_MAP["artifacts"])


def test_code_blocks_with_the_path_in_a_heading_parse():
    artifacts, ok = extract_artifacts(HEADED_BLOCKS)
    assert ok is True, "a heading-labelled code block was rejected"
    assert set(artifacts) == {
        "src/main/java/com/corp/orders/OrderService.java",
        "pom.xml",
    }
    assert "package com.corp.orders;" in artifacts[
        "src/main/java/com/corp/orders/OrderService.java"
    ]


def test_path_on_the_fence_line_still_parses():
    artifacts, ok = extract_artifacts("```pom.xml\n<project/>\n```")
    assert ok is True
    # The body is taken verbatim, including the newline before the closing fence.
    assert artifacts["pom.xml"].strip() == "<project/>"


def test_a_mixed_response_parses():
    """One block names its path on the fence, the other in a heading."""
    text = "```pom.xml\n<project/>\n```\n\n### src/main/resources/application.yml\n\n```yaml\nspring: {}\n```"
    artifacts, ok = extract_artifacts(text)
    assert ok is True
    assert set(artifacts) == {"pom.xml", "src/main/resources/application.yml"}


# ---------------------------------------------------------------------------
# Safety: the tolerance must not become sloppiness
# ---------------------------------------------------------------------------
def test_a_block_whose_file_cannot_be_named_fails_closed():
    """Never a partial set: content must not be persisted under a guessed path."""
    artifacts, ok = extract_artifacts("Example:\n\n```java\nclass X {}\n```")
    assert (artifacts, ok) == ({}, False)


def test_a_path_hint_does_not_reach_back_past_an_unrelated_line():
    """Association is local and conservative.

    Here an earlier heading names a file but the nearest line before the block does
    not. Reaching back would attach the block to an unrelated heading, and a
    mis-associated artifact is worse than a rejected one.
    """
    text = (
        "### pom.xml\n\n"
        "And now some unrelated prose with no path in it.\n\n"
        "```java\nclass X {}\n```\n"
    )
    artifacts, ok = extract_artifacts(text)
    assert (artifacts, ok) == ({}, False)


def test_a_complete_json_map_inside_an_unclosed_fence_is_recovered():
    """Deliberate tolerance: the JSON is complete, so nothing is truncated.

    The unclosed-fence guard exists to stop a TRUNCATED response from being
    half-parsed. Where the payload is a complete, self-describing JSON map, there
    is nothing partial to persist, so recovering it is the better outcome.
    """
    artifacts, ok = extract_artifacts("```json\n" + BARE_JSON)
    assert ok is True
    assert set(artifacts) == set(ARTIFACT_MAP["artifacts"])


def test_a_truncated_payload_inside_an_unclosed_fence_fails_closed():
    truncated = '```json\n{"artifacts": {"pom.xml": "<project/>", "src/main/'
    assert extract_artifacts(truncated) == ({}, False)


def test_prose_containing_braces_before_the_payload_parses():
    """A brace in the prose must not defeat the scan."""
    text = 'See {the notes} above.\n\n' + BARE_JSON
    artifacts, ok = extract_artifacts(text)
    assert ok is True
    assert set(artifacts) == set(ARTIFACT_MAP["artifacts"])


def test_empty_and_whitespace_responses_fail_closed():
    assert extract_artifacts("") == ({}, False)
    assert extract_artifacts("   \n\t ") == ({}, False)


def test_truncated_json_fails_closed():
    assert extract_artifacts('{"artifacts": {"pom.xml": "<proj') == ({}, False)


def test_an_unsafe_path_in_the_json_map_fails_closed():
    for path in ("../escape.java", "/etc/passwd", "a/../../b.java"):
        text = json.dumps({"artifacts": {path: "x"}})
        assert extract_artifacts(text) == ({}, False), f"{path} was accepted"


def test_a_json_object_without_artifacts_fails_closed():
    assert extract_artifacts(json.dumps({"edits": []})) == ({}, False)
    assert extract_artifacts(json.dumps({"artifacts": {}})) == ({}, False)


def test_a_non_string_artifact_value_fails_closed():
    assert extract_artifacts(json.dumps({"artifacts": {"pom.xml": 42}})) == ({}, False)


# ---------------------------------------------------------------------------
# The request states the wire format
# ---------------------------------------------------------------------------
def test_the_request_states_the_response_format():
    request = render_stage_request(
        {
            "blueprint": {"serviceName": "s", "packageName": "com.corp.s", "entities": []},
            "workspace_path": "/tmp/ws",
            "generated_files": {},
            "logs": [],
        },
        "SCAFFOLDER",
        "STAGE INSTRUCTION",
    )

    assert "## Response format" in request, (
        "the model is told what to produce but not how to encode it; that is the "
        "omission that cost a whole baseline run"
    )
    assert '"artifacts"' in request
    assert "no markdown fences" in request.lower() or "no prose" in request.lower()
    # The instruction and payload must survive: the format section is additive.
    assert "STAGE INSTRUCTION" in request
    assert "## Task payload" in request
