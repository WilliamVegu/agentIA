"""Git publication preserves history and sends credentials only in process memory."""
import base64
import re
import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit, quote
import git
from app.services.secret_redaction import redact


def sanitize_git_url(url: str) -> str:
    return re.sub(r"://([^@]+)@", "://", url)


def prepare_authenticated_url(repo_url: str, token: Optional[str]) -> str:
    """Compatibility helper: credentials are never encoded in URLs."""
    return sanitize_git_url(repo_url)


class GitPublishConflict(RuntimeError):
    pass


def _validate(branch, repository_url, allow_local):
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch or "")
            or any(x in branch for x in ("..", "//"))
            or branch.startswith("refs/") or branch.endswith(("/", ".", ".lock"))
            or any(part.startswith(".") or part.endswith(".lock") for part in branch.split("/"))):
        raise ValueError("Invalid branch name")
    check = subprocess.run(["git", "check-ref-format", "--branch", branch], capture_output=True, text=True, timeout=15)
    if check.returncode:
        raise ValueError("Invalid branch name")
    clean = sanitize_git_url(repository_url)
    parts = urlsplit(clean)
    if any(ord(char) < 32 for char in clean) or clean.startswith('-'):
        raise ValueError("Invalid repository URL")
    if allow_local and (parts.scheme == 'file' or Path(clean).is_absolute()):
        return clean
    if parts.scheme not in ('https', 'http') or not parts.hostname or parts.query or parts.fragment:
        raise ValueError("Repository must use HTTP(S); local repositories are test-only")
    return clean


def publish_to_git(workspace_path, repository_url, branch_name, git_token=None,
                   commit_message="feat: generated sources", *, allow_local=False):
    clean_url = _validate(branch_name, repository_url, allow_local)
    if git_token and urlsplit(clean_url).scheme != 'https':
        raise ValueError("Token authentication requires HTTPS")
    ws_dir = Path(workspace_path).resolve()
    if not ws_dir.is_dir():
        raise ValueError("Workspace does not exist")
    if (ws_dir / '.git').is_symlink():
        raise ValueError("Linked Git directory is not permitted")
    try:
        repo = git.Repo(ws_dir)
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        repo = git.Repo.init(ws_dir)
    git_dir = Path(repo.git_dir).resolve()
    if not git_dir.is_relative_to(ws_dir):
        raise ValueError("Git metadata outside workspace is not permitted")
    config_path = git_dir / 'config'
    if config_path.is_symlink() or not config_path.resolve().is_relative_to(git_dir):
        raise ValueError("Linked Git configuration is not permitted")
    with repo.config_writer() as config:
        config.set_value('user', 'name', 'Microservice Code Studio')
        config.set_value('user', 'email', 'studio@corp.internal')
    if repo.head.is_valid():
        if branch_name in [head.name for head in repo.heads]:
            repo.heads[branch_name].checkout()
        else:
            repo.create_head(branch_name).checkout()
    else:
        repo.git.symbolic_ref('HEAD', 'refs/heads/' + branch_name)
    # Do not commit generated runtime credentials, caches or build outputs.
    ignore = ws_dir / '.gitignore'
    if ignore.is_symlink() or not ignore.resolve().is_relative_to(ws_dir):
        repo.close()
        raise ValueError('Linked ignore file is not permitted')
    patterns = '\n.env\n.env.*\n!.env.example\n.agentia-runtime/\n.operation-locks/\ntarget/\nbuild/\n.gradle/\n'
    if not ignore.exists():
        ignore.write_text(patterns, encoding='utf-8')
    else:
        old = ignore.read_text(encoding='utf-8')
        missing = [line for line in patterns.splitlines() if line and line not in old.splitlines()]
        if missing:
            ignore.write_text(old.rstrip() + '\n' + '\n'.join(missing) + '\n', encoding='utf-8')
    repo.git.add(A=True)
    if not repo.head.is_valid() or repo.is_dirty(index=True, working_tree=False, untracked_files=False):
        repo.index.commit(redact(commit_message))
    commit_hash = repo.head.commit.hexsha
    # Retain an existing origin. Push to a clean URL directly, never store a PAT.
    if 'origin' not in [remote.name for remote in repo.remotes]:
        repo.create_remote('origin', clean_url)
    environment = {'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_NOSYSTEM': '1',
                   'GIT_TRACE': '0', 'GIT_CURL_VERBOSE': '0'}
    authorization = None
    pairs = [('credential.helper', ''), ('http.followRedirects', 'false')]
    if git_token:
        authorization = base64.b64encode(f'x-access-token:{git_token}'.encode()).decode()
        host_scope = 'https://' + urlsplit(clean_url).netloc + '/'
        pairs.insert(0, ('http.' + host_scope + '.extraHeader', 'Authorization: Basic ' + authorization))
    environment['GIT_CONFIG_COUNT'] = str(len(pairs))
    for index, (key, value) in enumerate(pairs):
        environment[f'GIT_CONFIG_KEY_{index}'] = key
        environment[f'GIT_CONFIG_VALUE_{index}'] = value
    try:
        with repo.git.custom_environment(**environment):
            repo.git.push(clean_url, f'{branch_name}:{branch_name}')
    except Exception as exc:
        repo.close()
        message = str(exc)
        for sensitive in (git_token, authorization):
            if sensitive:
                message = message.replace(sensitive, '[REDACTED]')
        message = redact(message)
        if any(reason in message.lower() for reason in ('non-fast-forward', 'fetch first', '[rejected]')):
            raise GitPublishConflict('Remote history diverged; reconcile before publishing') from None
        raise RuntimeError('Git push failed to ' + redact(clean_url) + ': ' + message) from None
    repo.close()
    web = clean_url.removesuffix('.git')
    branch_path = quote(branch_name, safe='/')
    return {'branchUrl': f'{web}/tree/{branch_path}', 'commitHash': commit_hash,
            'pullRequestUrl': f'{web}/pull/new/{branch_path}', 'branchName': branch_name}
