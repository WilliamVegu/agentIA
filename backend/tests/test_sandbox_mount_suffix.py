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


def test_the_default_command_carries_no_mount_suffix():
    """The default must be byte-identical to before the setting existed, so no
    existing host changes behaviour."""
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
    assert cache == "/host/.m2/repository:/root/.m2/repository:ro:Z"


def test_the_offline_contract_is_untouched(monkeypatch):
    """Whatever the suffix, the sandbox stays hermetic and offline."""
    from app.config import settings

    monkeypatch.setattr(settings, "DOCKER_MOUNT_SUFFIX", ":Z", raising=False)
    cmd = _cmd()

    assert cmd[cmd.index("--network") + 1] == "none"
    assert "-o" in cmd, "offline-first was lost"
    assert cmd[-1] == "-o"
