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
    auth_url = prepare_authenticated_url(repository_url, git_token)
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

    # Push to remote
    remote_name = "origin"
    try:
        if remote_name in [r.name for r in repo.remotes]:
            remote = repo.remote(remote_name)
            remote.set_url(auth_url)
        else:
            remote = repo.create_remote(remote_name, auth_url)

        remote.push(refspec=f"{branch_name}:{branch_name}", force=True)
    except Exception as push_err:
        # Clear authenticated remote to avoid leaking tokens
        try:
            repo.remote(remote_name).set_url(clean_url)
        except Exception:
            pass
        raise RuntimeError(f"Git push failed to {clean_url}: {str(push_err)}")
    finally:
        # Always sanitize remote URL after push
        try:
            repo.remote(remote_name).set_url(clean_url)
        except Exception:
            pass

    # Build web URL for branch inspection
    web_base = clean_url.rstrip(".git")
    branch_url = f"{web_base}/tree/{branch_name}"
    pr_url = f"{web_base}/pull/new/{branch_name}"

    return {
        "branchUrl": branch_url,
        "commitHash": commit_hash,
        "pullRequestUrl": pr_url,
        "branchName": branch_name
    }

