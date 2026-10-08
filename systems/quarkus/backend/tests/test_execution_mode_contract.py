from test_draft_authority import session
from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)


def test_guided_session_can_choose_docker_without_probing_runtime(session,monkeypatch):
    from app.services import docker_service
    monkeypatch.setattr(docker_service,'check_docker_daemon',lambda: (_ for _ in ()).throw(AssertionError('A choice does not probe Docker')))
    result=client.patch('/api/v1/sessions/draft-authority/execution-mode',json={'executionMode':'DOCKER'})
    assert result.status_code==200,result.text
    assert result.json()['executionMode']=='DOCKER'
    from app.models.session import SessionLocal,GenerationSessionDB
    with SessionLocal() as db: assert db.get(GenerationSessionDB,'draft-authority').execution_mode=='DOCKER'


def test_active_operation_prevents_mode_change(session):
    from app.services.operation_repository import begin_operation
    begin_operation('draft-authority','CODE_TESTS')
    result=client.patch('/api/v1/sessions/draft-authority/execution-mode',json={'executionMode':'DOCKER'})
    assert result.status_code==409


def test_source_only_verification_records_unexecuted_tests_without_docker(session,monkeypatch):
    from app.services.workspace_guard import atomic_write_workspace_file
    from app.services import docker_service
    from app.orchestrator.stages.runner import run_stages
    from integration.reliability_fixtures import ledger_draft
    state=run_stages({'session_id':'draft-authority','workspace_path':str(session),'blueprint':ledger_draft(),'generation_mode':'DETERMINISTIC','generated_files':{},'logs':[]})
    assert state.get('status')!='BLOCKED'
    monkeypatch.setattr(docker_service,'check_docker_daemon',lambda: (_ for _ in ()).throw(AssertionError('Docker forbidden')))
    result=client.post('/api/v1/sessions/draft-authority/verify')
    assert result.status_code==200,result.text
    assert result.json()['metrics']['verificationSkipped'] is True
    assert result.json()['metrics']['totalTests']==0
    assert result.json()['metrics']['allPassed'] is False
    assert result.json()['status']=='COMPLETED'


def test_verification_requires_sources_before_invoking_native_tools(session):
    session.mkdir()
    result=client.post('/api/v1/sessions/draft-authority/verify')
    assert result.status_code==409


import pytest

@pytest.mark.parametrize('query',['host_port=18089','db_engine=MYSQL'])
def test_manifest_overrides_cannot_change_persisted_configuration(session,query):
    from app.services.draft_revision_service import save_revision
    from integration.reliability_fixtures import ledger_draft
    session.mkdir()
    save_revision('draft-authority',ledger_draft())
    result=client.post('/api/v1/devops/draft-authority/generate?'+query)
    assert result.status_code==409,result.text
    assert not (session/'Dockerfile').exists()


def test_active_operation_prevents_manifest_rewrite(session):
    from app.services.operation_repository import begin_operation
    session.mkdir()
    begin_operation('draft-authority','CODE_TESTS')
    result=client.post('/api/v1/devops/draft-authority/generate')
    assert result.status_code==409,result.text
    assert not (session/'Dockerfile').exists()



def test_mode_change_preserves_immutable_configuration_history(session):
    from app.services.draft_revision_service import save_revision
    from integration.reliability_fixtures import ledger_draft
    from app.models.session import SessionLocal,GenerationSessionDB
    from app.models.reliability import SessionConfiguration
    session.mkdir()
    saved=save_revision('draft-authority',ledger_draft())
    result=client.patch('/api/v1/sessions/draft-authority/execution-mode',json={'executionMode':'DOCKER'})
    assert result.status_code==200,result.text
    with SessionLocal() as db:
        row=db.get(GenerationSessionDB,'draft-authority')
        configs=db.query(SessionConfiguration).filter_by(session_id='draft-authority').order_by(SessionConfiguration.version).all()
        assert [item.execution_mode for item in configs]==['SOURCE_ONLY','DOCKER']
        assert [item.host_port for item in configs]==[18088,18088]
        assert row.configuration_version==saved['configurationVersion']+1
        assert row.revision_id==saved['revisionId']
