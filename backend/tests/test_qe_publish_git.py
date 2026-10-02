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

import base64
import contextlib
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
    assert prepare_authenticated_url(CLEAN_URL, TOKEN) == AUTH_URL


def test_a_token_is_not_embedded_for_ssh_or_http():
    """Only https can carry the token in the URL; the others must pass through."""
    assert prepare_authenticated_url("git@github.com:corp/x.git", TOKEN) == "git@github.com:corp/x.git"
    assert prepare_authenticated_url("http://git.local/x.git", TOKEN) == "http://git.local/x.git"


def test_an_already_authenticated_url_is_not_double_embedded():
    already = "https://oauth2:old@github.com/corp/x.git"
    assert prepare_authenticated_url(already, TOKEN) == f"https://oauth2:{TOKEN}@github.com/corp/x.git"


# ---------------------------------------------------------------------------
# publish_to_git
# ---------------------------------------------------------------------------
class _FakeRemote:
    """Stands in for a GitPython remote so nothing leaves the machine.

    It records every URL the service sets, which is what the Principle VI assertions
    read. ``fail`` is forwarded to ``_PushLog``: the remote object no longer performs
    the push, so it cannot be the thing that fails.
    """

    def __init__(self, fail: bool = False):
        self.urls: list[str] = []
        self.fail = fail

    def set_url(self, url: str) -> None:
        self.urls.append(url)


class _PushLog:
    """Records the push and the environment it ran under.

    ``publish_to_git`` pushes through ``repo.git.push`` inside a
    ``repo.git.custom_environment`` block: the token travels to git as an
    ``http.extraHeader`` config value, never in the remote URL. Those two calls are the
    boundary to the outside world, so they are what a test replaces -- ``git add`` and
    ``git commit`` still run for real, which is the point of using a real repository.
    """

    def __init__(self, fail: bool = False):
        self.refspecs: list[str] = []
        self.environments: list[dict] = []
        self._fail = fail
        self._active_environment: dict = {}

    @contextlib.contextmanager
    def custom_environment(self, **kwargs):
        previous, self._active_environment = self._active_environment, dict(kwargs)
        try:
            yield
        finally:
            self._active_environment = previous

    def push(self, remote_name, refspec, **kwargs):
        self.refspecs.append(f"{remote_name} {refspec}")
        self.environments.append(dict(self._active_environment))
        if self._fail:
            raise RuntimeError("remote rejected the push")


def _install_push_log(monkeypatch, fail: bool = False) -> _PushLog:
    """Fake ``repo.git.push`` and the ``custom_environment`` it runs inside."""
    log = _PushLog(fail=fail)
    monkeypatch.setattr(git_service.git.Git, "custom_environment", log.custom_environment)
    # `push` is resolved dynamically by GitPython, so it is not a class attribute and the
    # patch would be rejected unless `raising=False`.
    monkeypatch.setattr(git_service.git.Git, "push", log.push, raising=False)
    return log


@pytest.fixture
def workspace(tmp_path):
    """A real, empty directory that GitPython will initialize."""
    ws = tmp_path / "ws-orders"
    ws.mkdir()
    (ws / "pom.xml").write_text("<project/>", encoding="utf-8")
    return ws


def _publish(monkeypatch, workspace, remote, *, existing_remote=False, **overrides):
    """Run publish_to_git with the git remote and the push faked.

    Both ``repo.remote(...)`` and ``repo.create_remote(...)`` must be stubbed, plus
    the ``remotes`` property: the service re-reads the remote to decide whether to
    create or update it, so stubbing only ``create_remote`` would let the real (empty)
    repository answer and take the other branch.
    """
    import types

    monkeypatch.setattr(git_service.git.Repo, "remote", lambda self, name: remote)
    monkeypatch.setattr(git_service.git.Repo, "create_remote", lambda self, name, url: remote)
    monkeypatch.setattr(
        git_service.git.Repo,
        "remotes",
        property(lambda self: [types.SimpleNamespace(name="origin")] if existing_remote else []),
    )
    push_log = _install_push_log(monkeypatch, fail=remote.fail)

    kwargs = dict(
        workspace_path=str(workspace),
        repository_url=CLEAN_URL,
        branch_name="feature/001-order-service",
        git_token=TOKEN,
    )
    kwargs.update(overrides)
    return publish_to_git(**kwargs), push_log


def test_a_successful_publish_returns_the_branch_urls_and_a_commit(monkeypatch, workspace):
    remote = _FakeRemote()

    result, pushes = _publish(monkeypatch, workspace, remote, existing_remote=True)

    assert result["branchName"] == "feature/001-order-service"
    assert result["branchUrl"] == f"https://github.com/corp/orders/tree/feature/001-order-service"
    assert result["pullRequestUrl"] == "https://github.com/corp/orders/pull/new/feature/001-order-service"
    assert result["commitHash"], "a publish without a commit hash is not traceable"
    assert pushes.refspecs == ["origin feature/001-order-service:feature/001-order-service"]


def test_the_token_reaches_the_remote_during_the_push(monkeypatch, workspace):
    """The token must be used -- otherwise private pushes cannot work.

    It is no longer embedded in the remote URL. The service hands git an
    ``http.extraHeader`` config value through ``custom_environment``, so the credential
    still reaches the push without ever being written into ``.git/config``.
    """
    remote = _FakeRemote()

    _, pushes = _publish(monkeypatch, workspace, remote, existing_remote=True)

    assert pushes.environments, "the push ran without the credential environment"
    authorization = base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
    assert pushes.environments[0]["GIT_CONFIG_KEY_0"] == "http.extraHeader"
    assert pushes.environments[0]["GIT_CONFIG_VALUE_0"] == f"Authorization: Basic {authorization}"


def test_the_token_is_never_written_to_the_remote_url(monkeypatch, workspace):
    """Principle VI: the token lives in memory for the push and is never persisted.

    This replaces the "scrub after the push" assertion. The guarantee is now stronger:
    the authenticated URL is not written and then removed, it is never written at all,
    so a crash between the write and the scrub cannot leave the token on disk. Every URL
    the remote is given is the clean one.
    """
    remote = _FakeRemote()

    _, pushes = _publish(monkeypatch, workspace, remote, existing_remote=True)

    assert remote.urls, "the remote was never configured"
    assert all(url == CLEAN_URL for url in remote.urls)
    assert not any(TOKEN in url for url in remote.urls)

    # And the on-disk config the next process would read carries no credential either.
    assert TOKEN not in (workspace / ".git" / "config").read_text(encoding="utf-8")
    assert pushes.environments, "the credential header was never set for the push"


def test_a_new_remote_is_created_with_the_clean_url_and_the_token_goes_to_the_push(monkeypatch, workspace):
    """The create-remote branch: no origin exists, so it is created with the clean URL.

    The token still has to reach the push; it travels in the push environment, not in
    the URL the remote is created with.
    """
    created = {}
    remote = _FakeRemote()
    pushes = _install_push_log(monkeypatch)

    def create_remote(self, name, url):
        created["name"], created["url"] = name, url
        return remote

    monkeypatch.setattr(git_service.git.Repo, "remote", lambda self, name: remote)
    monkeypatch.setattr(git_service.git.Repo, "create_remote", create_remote)
    monkeypatch.setattr(git_service.git.Repo, "remotes", property(lambda self: []))

    result = publish_to_git(
        workspace_path=str(workspace), repository_url=CLEAN_URL,
        branch_name="feature/001", git_token=TOKEN,
    )

    assert created["name"] == "origin"
    assert created["url"] == CLEAN_URL, "the token was written into the new remote's URL"
    assert pushes.environments, "the token never reached the push"
    value = pushes.environments[0]["GIT_CONFIG_VALUE_0"]
    assert TOKEN not in value, "the raw token was sent as the header value"
    assert value == "Authorization: Basic " + base64.b64encode(
        f"x-access-token:{TOKEN}".encode()
    ).decode()
    assert result["branchName"] == "feature/001"


def test_a_failed_push_raises_with_a_sanitized_message_and_still_scrubs(monkeypatch, workspace):
    remote = _FakeRemote(fail=True)

    with pytest.raises(RuntimeError) as excinfo:
        _publish(monkeypatch, workspace, remote, existing_remote=True)

    message = str(excinfo.value)
    assert "Git push failed" in message
    assert CLEAN_URL in message
    assert TOKEN not in message, "the token leaked into an error message"
    assert remote.urls[-1] == CLEAN_URL, "the token persisted after a FAILED push"


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
    result, _ = _publish(monkeypatch, workspace, remote)

    assert result["commitHash"] != seeded_head, "the seeded commit was returned instead of a new one"
    assert git.Repo(workspace).active_branch.name == "feature/001-order-service"
