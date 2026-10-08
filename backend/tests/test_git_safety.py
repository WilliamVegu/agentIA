from pathlib import Path
import pytest
import git
from app.services.git_service import publish_to_git


def commit(repo, file, content):
    (Path(repo.working_tree_dir) / file).write_text(content)
    repo.git.add(A=True)
    with repo.config_writer() as config:
        config.set_value('user', 'name', 'Fixture')
        config.set_value('user', 'email', 'fixture@example.invalid')
    return repo.index.commit('fixture')


def test_divergent_push_does_not_replace_history_and_preserves_origin(tmp_path):
    remote = git.Repo.init(tmp_path / 'remote.git', bare=True)
    first = git.Repo.init(tmp_path / 'first')
    commit(first, 'a.txt', 'initial')
    first.git.branch('-M', 'feature/test')
    first.create_remote('origin', str(tmp_path / 'original.git'))
    original_url = first.remote('origin').url
    publish_to_git(str(tmp_path / 'first'), str(tmp_path / 'remote.git'), 'feature/test', allow_local=True)
    second = git.Repo.clone_from(str(tmp_path / 'remote.git'), tmp_path / 'second', branch='feature/test')
    head = commit(second, 'a.txt', 'remote change')
    second.git.push('origin', 'feature/test')
    commit(first, 'a.txt', 'local divergent change')
    with pytest.raises(RuntimeError):
        publish_to_git(str(tmp_path / 'first'), str(tmp_path / 'remote.git'), 'feature/test', allow_local=True)
    assert remote.commit('feature/test').hexsha == head.hexsha
    assert first.remote('origin').url == original_url


def test_pat_never_enters_urls_or_config_even_when_push_fails(tmp_path, monkeypatch):
    token = 'ghp_' + 'x' * 40
    ws = tmp_path / 'source'
    ws.mkdir()
    (ws / 'A.java').write_text('class A {}')
    environments = []
    def fail(command, url, refspec):
        environments.append(dict(command._environment))
        assert token not in url
        raise RuntimeError(f'Authorization: Basic unsafe {token}')
    monkeypatch.setattr(git.Git, 'push', fail, raising=False)
    with pytest.raises(RuntimeError) as error:
        publish_to_git(str(ws), 'https://github.com/example/repo.git', 'feature/test', git_token=token)
    assert token not in str(error.value)
    assert token not in (ws / '.git/config').read_text()
    assert environments[0]['GIT_CONFIG_KEY_0'] == 'http.https://github.com/.extraHeader'
    assert environments[0]['GIT_CONFIG_VALUE_1'] == ''


@pytest.mark.parametrize('branch', ['--force', 'x..y', 'refs/heads/main', 'main:other', 'x\nmain'])
def test_invalid_branch_rejected_before_writing(tmp_path, branch, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Invalid request must never attempt a push')
    monkeypatch.setattr(git.Git, 'push', forbidden, raising=False)
    with pytest.raises(ValueError):
        publish_to_git(str(tmp_path), 'https://github.com/example/repo.git', branch)
    assert not (tmp_path / '.git').exists()
