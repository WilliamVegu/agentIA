import re
from pathlib import Path
from typing import Optional, Dict, Any
import git

def sanitize_git_url(url: str) -> str:
    """Removes embedded tokens or credentials from git URLs for safe logging and UI display."""
    return re.sub(r"://([^@]+)@", "://", url)

def prepare_authenticated_url(repo_url: str, token: Optional[str]) -> str:
    """Embeds ephemeral PAT in memory for push without persisting to filesystem."""
    if not token:
        return repo_url
    clean = sanitize_git_url(repo_url)
    if clean.startswith("https://"):
        return clean.replace("https://", f"https://oauth2:{token}@")
    return repo_url

def publish_to_git(
    workspace_path: str,
    repository_url: str,
    branch_name: str,
    git_token: Optional[str] = None,
    commit_message: str = "feat: initial autonomous generation and verified test suite"
) -> Dict[str, Any]:
    """
    Executes an atomic git commit and pushes to a dedicated feature branch.
    Follows Constitution Principle VI (zero persisted credentials).
    """
    ws_dir = Path(workspace_path).resolve()
    clean_url = sanitize_git_url(repository_url)

    # Initialize or open Git repository
    try:
        repo = git.Repo(ws_dir)
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        repo = git.Repo.init(ws_dir)

    # Configure committer
    with repo.config_writer() as config:
        config.set_value("user", "name", "Microservice Code Studio")
        config.set_value("user", "email", "studio@corp.internal")

    # Checkout or create feature branch
    try:
        current_branch = repo.create_head(branch_name)
        current_branch.checkout()
    except Exception:
        repo.git.checkout("-B", branch_name)

    # Stage all files
    repo.git.add(A=True)

    # Commit
    try:
        commit = repo.index.commit(commit_message)
        commit_hash = commit.hexsha
    except Exception:
        commit_hash = repo.head.commit.hexsha if repo.head.is_valid() else "initial"

    # Check if the environment has stubbed the remote with _FakeRemote in test_qe_publish_git
    remote_name = "origin"
    if remote_name in [r.name for r in repo.remotes]:
        repo.remote(remote_name).set_url(clean_url)
    else:
        repo.create_remote(remote_name, clean_url)
    import base64
    environment = {"GIT_TERMINAL_PROMPT": "0"}
    if git_token:
        from urllib.parse import urlsplit
        if urlsplit(clean_url).scheme != "https":
            raise ValueError("Token authentication requires HTTPS")
        authorization = base64.b64encode(f"x-access-token:{git_token}".encode()).decode()
        environment.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.extraHeader",
                           GIT_CONFIG_VALUE_0=f"Authorization: Basic {authorization}")
    try:
        with repo.git.custom_environment(**environment):
            repo.git.push(remote_name, f"{branch_name}:{branch_name}")
    except Exception as exc:
        message = str(exc)
        if git_token:
            message = message.replace(git_token, "[REDACTED]").replace(authorization, "[REDACTED]")
        raise RuntimeError(f"Git push failed to {clean_url}: {message}") from None

    # Build web URL for branch inspection
    web_base = clean_url.removesuffix(".git")
    branch_url = f"{web_base}/tree/{branch_name}"
    pr_url = f"{web_base}/pull/new/{branch_name}"

    return {
        "branchUrl": branch_url,
        "commitHash": commit_hash,
        "pullRequestUrl": pr_url,
        "branchName": branch_name
    }

