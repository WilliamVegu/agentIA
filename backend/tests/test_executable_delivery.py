import pytest
from fastapi import HTTPException
from app.models.session import SessionLocal, GenerationSessionDB, SessionStatus
from app.services.executable_delivery import export_executable


def test_source_package_does_not_probe_docker(monkeypatch):
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id='source-executable-rejection', spec_id='test', spec_name='service',
            execution_mode='SOURCE_ONLY', status=SessionStatus.COMPLETED))
        db.commit()
    monkeypatch.setattr('app.services.executable_delivery.subprocess.check_output',
                        lambda *a, **kw: pytest.fail('Source mode invoked Docker'))
    with pytest.raises(HTTPException) as raised:
        export_executable('source-executable-rejection')
    assert raised.value.status_code == 409


def test_missing_session_package_rejected_without_docker(monkeypatch):
    monkeypatch.setattr('app.services.executable_delivery.subprocess.check_output',
                        lambda *a, **kw: pytest.fail('Missing session invoked Docker'))
    with pytest.raises(HTTPException) as raised:
        export_executable('missing-executable')
    assert raised.value.status_code == 404
