from pathlib import Path
import os
import pytest
from fastapi import HTTPException
from app.config import settings
from app.models.session import SessionLocal, GenerationSessionDB, SessionStatus


@pytest.fixture
def owned_session(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path / 'workspaces'))
    with SessionLocal() as db:
        row = GenerationSessionDB(id='boundary-test', spec_id='boundary-spec', spec_name='Boundary', status=SessionStatus.BLOCKED)
        db.add(row)
        db.commit()
    ws = tmp_path / 'workspaces/boundary-test'
    ws.mkdir(parents=True)
    yield ws
    with SessionLocal() as db:
        db.query(GenerationSessionDB).filter_by(id='boundary-test').delete()
        db.commit()


def test_missing_session_repair_is_not_success(tmp_path, monkeypatch):
    from app.api.routes_tests import submit_manual_repair
    from app.models.test_analysis import ManualRepairRequest
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path))
    with pytest.raises(HTTPException) as failure:
        submit_manual_repair('missing-boundary-session', ManualRepairRequest(filePath='A.java', modifiedCode='changed'))
    assert failure.value.status_code == 404


def test_absolute_repair_does_not_write_external_sentinel(owned_session, tmp_path):
    from app.api.routes_tests import submit_manual_repair
    from app.models.test_analysis import ManualRepairRequest
    sentinel = tmp_path / 'external.txt'
    sentinel.write_text('original')
    try:
        with pytest.raises(HTTPException) as failure:
            submit_manual_repair('boundary-test', ManualRepairRequest(filePath=str(sentinel), modifiedCode='changed'))
        assert failure.value.status_code in (400, 422)
        assert sentinel.read_text() == 'original'
    finally:
        sentinel.write_text('original')


@pytest.mark.asyncio
async def test_remediation_without_session_never_searches_files(owned_session, monkeypatch):
    from app.api import routes_security
    from app.models.security_quality import RemediationRequest
    path = owned_session / 'A.java'
    path.write_text('sentinel')
    monkeypatch.setattr(routes_security, 'apply_surgical_remediation', lambda finding, file, code: (code, 'changed', 'diff'))
    with pytest.raises(HTTPException) as failure:
        await routes_security.remediate_finding(RemediationRequest(findingId='test', filePath='A.java'))
    assert failure.value.status_code in (400, 422)
    assert path.read_text() == 'sentinel'


@pytest.mark.parametrize('name', ['../external.txt', '/absolute.txt', 'C:/absolute.txt', 'C:relative.txt', '\\\\server\\share\\x', 'x:stream', 'src/../x', '.git/config', 'x\x00y'])
def test_dangerous_file_paths_rejected(owned_session, name):
    from app.services.workspace_guard import resolve_workspace_file
    with pytest.raises(HTTPException) as failure:
        resolve_workspace_file('boundary-test', name)
    assert failure.value.status_code in (400, 422)


def test_atomic_write_and_link_escape(owned_session, tmp_path):
    from app.services.workspace_guard import resolve_workspace_file, atomic_write_workspace_file
    atomic_write_workspace_file('boundary-test', 'src/A.java', 'content')
    assert (owned_session / 'src/A.java').read_text() == 'content'
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'sentinel').write_text('original')
    link = owned_session / 'linked'
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError:
        if os.name == 'nt':
            from _winapi import CreateJunction
            CreateJunction(str(outside), str(link))
        else:
            raise
    with pytest.raises(HTTPException):
        resolve_workspace_file('boundary-test', 'linked/sentinel')
    assert (outside / 'sentinel').read_text() == 'original'


def test_missing_session_checked_before_file_path(tmp_path, monkeypatch):
    from app.services.workspace_guard import resolve_workspace_file
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path))
    with pytest.raises(HTTPException) as failure:
        resolve_workspace_file('no-such-session', '/absolute')
    assert failure.value.status_code == 404
