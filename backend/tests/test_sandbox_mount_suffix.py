"""The sandbox mount suffix (feature 015).

Why this exists: on a host whose container runtime applies SELinux labels to bind
mounts, a mount without ``:Z`` is unreadable inside the container. Maven then finds
no ``pom.xml`` and the session blocks -- and a BLOCKED session is indistinguishable
at the report level from one whose generated code genuinely failed to build. That
ambiguity is what this setting removes.

It is a host property, not an agent property, so it defaults to empty and the
default command is byte-identical to before.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.sandbox.docker_runner import build_docker_cmd  # noqa: E402


def _cmd():
    return build_docker_cmd(
        workspace_host_path="/host/ws",
        maven_cache_host_path="/host/.m2/repository",
        docker_image="maven:3.9-eclipse-temurin-21",
    )


def test_the_default_command_carries_no_mount_suffix(monkeypatch):
    """The default must be byte-identical to before the setting existed, so no
    existing host changes behaviour.

    Pinned explicitly rather than relying on the ambient value. The setting is
    read from the environment, so a developer who sets DOCKER_MOUNT_SUFFIX in
    backend/.env -- which is exactly what a host needing ':Z' must do -- would
    otherwise make this test fail for a reason that has nothing to do with the
    code. A test whose result depends on the operator's .env is not testing the
    default.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "DOCKER_MOUNT_SUFFIX", "", raising=False)
    cmd = _cmd()
    workspace = cmd[cmd.index("-v") + 1]
    cache = cmd[cmd.index("-v", cmd.index("-v") + 1) + 1]

    assert workspace == "/host/ws:/workspace"
    assert cache == "/host/.m2/repository:/root/.m2/repository:ro"


def test_the_suffix_is_applied_to_both_mounts_when_set(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "DOCKER_MOUNT_SUFFIX", ":Z", raising=False)
    cmd = _cmd()
    workspace = cmd[cmd.index("-v") + 1]
    cache = cmd[cmd.index("-v", cmd.index("-v") + 1) + 1]

    assert workspace == "/host/ws:/workspace:Z", (
        "the workspace mount lacked the suffix; inside the container it would be "
        "unreadable and Maven would find no pom.xml"
    )
    # Docker separates the options after the second colon with COMMAS. This
    # assertion previously pinned `:ro:Z`, which Docker rejects outright:
    #
    #     docker: invalid spec: ...:/root/.m2/repository:ro:Z: too many colons
    #
    # The command never reached Maven, so on any labelled host every session
    # reported a build failure for a reason unrelated to the generated code --
    # exactly the ambiguity this feature exists to remove. A test that pins the
    # bug is worse than no test, so the expectation is corrected here rather than
    # in a comment.
    assert cache == "/host/.m2/repository:/root/.m2/repository:ro,Z"


def test_the_suffix_is_accepted_in_any_of_the_shapes_an_operator_might_supply(monkeypatch):
    """``Z``, ``:Z`` and ``,Z`` must all produce the same valid spec.

    The setting is a host property an operator edits by hand, and the failure mode
    of getting it slightly wrong is a build that fails before Maven runs, which is
    indistinguishable from a real compilation failure. Normalising the input
    removes one way to be wrong about it.
    """
    from app.config import settings

    produced = set()
    for value in ("Z", ":Z", ",Z"):
        monkeypatch.setattr(settings, "DOCKER_MOUNT_SUFFIX", value, raising=False)
        cmd = _cmd()
        cache = cmd[cmd.index("-v", cmd.index("-v") + 1) + 1]
        produced.add(cache)

    assert produced == {"/host/.m2/repository:/root/.m2/repository:ro,Z"}


def test_the_offline_contract_is_untouched(monkeypatch):
    """Whatever the suffix, the sandbox stays hermetic and offline."""
    from app.config import settings

    monkeypatch.setattr(settings, "DOCKER_MOUNT_SUFFIX", ":Z", raising=False)
    cmd = _cmd()

    assert cmd[cmd.index("--network") + 1] == "none"
    assert "-o" in cmd, "offline-first was lost"
    assert cmd[-1] == "-o"
