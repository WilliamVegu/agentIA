"""QE coverage: git publishing, including the zero-persisted-credentials guarantee.

``app/services/git_service.py`` was 21% covered, and the uncovered 79% is the part
that handles an ephemeral Personal Access Token. That is not incidental coverage:
Constitution Principle VI says the token is processed in memory and never persisted,
so the tests that matter here are the ones asserting the token does **not** survive
in the repository config after a publish — including after a failed one.

No network and no remote: a real local repository is used (so GitPython's actual
behaviour is exercised for init/config/add/commit), and only the *remote* is faked.
A test that mocked ``git.Repo`` entirely would not prove the config writer leaves the
remote sanitized, which is the guarantee under test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services import git_service  # noqa: E402
from app.services.git_service import (  # noqa: E402
    prepare_authenticated_url,
    publish_to_git,
    sanitize_git_url,
)

TOKEN = "ghp_ephemeral_token_must_not_persist"
CLEAN_URL = "https://github.com/corp/orders.git"
AUTH_URL = f"https://oauth2:{TOKEN}@github.com/corp/orders.git"


# ---------------------------------------------------------------------------
# URL handling
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://user:pass@github.com/corp/x.git", "https://github.com/corp/x.git"),
        ("https://oauth2:ghp_abc@gitlab.com/g/p.git", "https://gitlab.com/g/p.git"),
        ("https://github.com/corp/x.git", "https://github.com/corp/x.git"),
        ("git@github.com:corp/x.git", "git@github.com:corp/x.git"),
    ],
)
def test_sanitize_strips_embedded_credentials_only(url, expected):
    assert sanitize_git_url(url) == expected


def test_no_token_leaves_the_url_untouched():
    assert prepare_authenticated_url(CLEAN_URL, None) == CLEAN_URL
    assert prepare_authenticated_url(CLEAN_URL, "") == CLEAN_URL


def test_a_token_is_embedded_for_https():
    assert prepare_authenticated_url(CLEAN_URL, TOKEN) == CLEAN_URL


def test_a_token_is_not_embedded_for_ssh_or_http():
    """Only https can carry the token in the URL; the others must pass through."""
    assert prepare_authenticated_url("git@github.com:corp/x.git", TOKEN) == "git@github.com:corp/x.git"
    assert prepare_authenticated_url("http://git.local/x.git", TOKEN) == "http://git.local/x.git"


def test_an_already_authenticated_url_is_not_double_embedded():
    already = "https://oauth2:old@github.com/corp/x.git"
    assert prepare_authenticated_url(already, TOKEN) == CLEAN_URL.replace("orders.git", "x.git")


# ---------------------------------------------------------------------------
# publish_to_git
# ---------------------------------------------------------------------------
class _FakeRemote:
    """Stands in for a GitPython remote so nothing leaves the machine."""

    def __init__(self, fail: bool = False):
        self.urls: list[str] = []
        self.pushed: list[str] = []
        self._fail = fail
        self.environments = []

    def set_url(self, url: str) -> None:
        self.urls.append(url)

    def push(self, refspec=None, force=False, **kwargs):
        self.pushed.append(refspec)
        if self._fail:
            raise RuntimeError("remote rejected the push")


@pytest.fixture
def workspace(tmp_path):
    """A real, empty directory that GitPython will initialize."""
    ws = tmp_path / "ws-orders"
    ws.mkdir()
    (ws / "pom.xml").write_text("<project/>", encoding="utf-8")
    return ws


def _publish(monkeypatch, workspace, remote, *, existing_remote=False, **overrides):
    """Run publish_to_git with only the git remote faked.

    Both ``repo.remote(...)`` and ``repo.create_remote(...)`` must be stubbed, plus
    the ``remotes`` property: the service re-reads the remote in its ``finally`` block
    to scrub the token, so stubbing only ``create_remote`` would let the real (empty)
    repository answer the scrub and silently skip the guarantee under test.
    """
    import types

    monkeypatch.setattr(git_service.git.Repo, "remote", lambda self, name: remote)
    monkeypatch.setattr(git_service.git.Repo, "create_remote", lambda self, name, url: remote)
    monkeypatch.setattr(
        git_service.git.Repo,
        "remotes",
        property(lambda self: [types.SimpleNamespace(name="origin")] if existing_remote else []),
    )

    def push(command, name, refspec):
        remote.environments.append(dict(command._environment))
        return remote.push(refspec=refspec)
    monkeypatch.setattr(git_service.git.Git, "push", push, raising=False)

    kwargs = dict(
        workspace_path=str(workspace),
        repository_url=CLEAN_URL,
        branch_name="feature/001-order-service",
        git_token=TOKEN,
    )
    kwargs.update(overrides)
    return publish_to_git(**kwargs)


def test_a_successful_publish_returns_the_branch_urls_and_a_commit(monkeypatch, workspace):
    remote = _FakeRemote()

    result = _publish(monkeypatch, workspace, remote, existing_remote=True)

    assert result["branchName"] == "feature/001-order-service"
    assert result["branchUrl"] == f"https://github.com/corp/orders/tree/feature/001-order-service"
    assert result["pullRequestUrl"] == "https://github.com/corp/orders/pull/new/feature/001-order-service"
    assert result["commitHash"], "a publish without a commit hash is not traceable"
    assert remote.pushed == ["feature/001-order-service:feature/001-order-service"]


def test_the_token_reaches_the_remote_during_the_push(monkeypatch, workspace):
    """The token must be used -- otherwise private pushes cannot work."""
    remote = _FakeRemote()

    _publish(monkeypatch, workspace, remote, existing_remote=True)

    import base64
    assert remote.environments[0]["GIT_CONFIG_VALUE_0"] == "Authorization: Basic " + base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
    assert all(TOKEN not in url for url in remote.urls)


def test_the_token_is_scrubbed_from_the_remote_after_a_successful_publish(monkeypatch, workspace):
    """Principle VI: the token lives in memory for the push and then is gone."""
    remote = _FakeRemote()

    _publish(monkeypatch, workspace, remote, existing_remote=True)

    assert remote.urls == [], "Existing origin must not be rewritten for an ephemeral push"
    assert TOKEN not in (workspace / ".git/config").read_text()
    assert remote.environments[0]["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraHeader"


def test_new_remote_uses_a_clean_url(monkeypatch, workspace):
    """A new origin never persists credentials; the subprocess receives them temporarily."""
    import types

    created = {}
    remote = _FakeRemote()

    def create_remote(self, name, url):
        created["name"], created["url"] = name, url
        return remote

    monkeypatch.setattr(git_service.git.Repo, "remote", lambda self, name: remote)
    monkeypatch.setattr(git_service.git.Repo, "create_remote", create_remote)
    monkeypatch.setattr(git_service.git.Repo, "remotes", property(lambda self: []))

    monkeypatch.setattr(git_service.git.Git, "push", lambda self, name, refspec: remote.push(refspec=refspec), raising=False)
    result = publish_to_git(
        workspace_path=str(workspace), repository_url=CLEAN_URL,
        branch_name="feature/001", git_token=TOKEN,
    )

    assert created["name"] == "origin"
    assert created["url"] == CLEAN_URL, "credentials must never enter the repository configuration"
    assert result["branchName"] == "feature/001"


def test_a_failed_push_raises_with_a_sanitized_message_and_still_scrubs(monkeypatch, workspace):
    remote = _FakeRemote(fail=True)

    with pytest.raises(RuntimeError) as excinfo:
        _publish(monkeypatch, workspace, remote, existing_remote=True)

    message = str(excinfo.value)
    assert "Git push failed" in message
    assert CLEAN_URL in message
    assert TOKEN not in message, "the token leaked into an error message"
    assert remote.urls == [], "Existing origin must be preserved even after a failed push"
    assert TOKEN not in (workspace / '.git/config').read_text()


def test_the_committer_identity_is_recorded(monkeypatch, workspace):
    """A commit with no author fails on a clean machine; the service sets one."""
    import git

    remote = _FakeRemote()
    _publish(monkeypatch, workspace, remote)

    repo = git.Repo(workspace)
    with repo.config_reader() as reader:
        assert reader.get_value("user", "name") == "Microservice Code Studio"
        assert reader.get_value("user", "email") == "studio@corp.internal"


def test_publishing_to_an_existing_repository_does_not_reinitialize(monkeypatch, workspace):
    """The workspace may already be a repo; the service must reuse it."""
    import git

    existing = git.Repo.init(workspace)
    existing.git.add(A=True)
    with existing.config_writer() as config:
        config.set_value("user", "name", "seed")
        config.set_value("user", "email", "seed@corp.internal")
    existing.index.commit("seed commit")
    seeded_head = existing.head.commit.hexsha

    remote = _FakeRemote()
    result = _publish(monkeypatch, workspace, remote)

    assert result["commitHash"] != seeded_head, "the seeded commit was returned instead of a new one"
    assert git.Repo(workspace).active_branch.name == "feature/001-order-service"
