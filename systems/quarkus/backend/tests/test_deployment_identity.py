from test_draft_authority import session

def test_unowned_service_is_never_probed_or_accepted(session,monkeypatch):
    import app.services.docker_service as service
    service._active_deployments.clear()
    calls=[]
    def foreign(*args,**kwargs):
        calls.append(args)
        return type('Foreign',(),{'status_code':200,'json':lambda self:{'status':'UP'}})()
    monkeypatch.setattr(service.requests,'get',foreign)
    observed=service.get_deployment_status('draft-authority',8080)
    assert observed.status.value=='UNKNOWN'
    assert observed.testUrl is None
    assert calls==[]


def test_unknown_runtime_preserves_configured_port(session):
    from app.services.draft_revision_service import save_revision
    from integration.reliability_fixtures import ledger_draft
    from app.services.local_runtime import status
    save_revision('draft-authority',ledger_draft())
    observed=status('draft-authority',lambda *a,**k: (_ for _ in ()).throw(AssertionError('No foreign probe')))
    assert observed.hostPort==18088
    assert observed.status.value=='UNKNOWN'


def test_failed_deployment_cannot_become_healthy_via_late_callback(session):
    from app.services.local_runtime import begin,update,latest,status
    operation_id=begin('draft-authority','fingerprint','snapshot',18088)
    update(operation_id,'FAILED',error='Timed out')
    assert update(operation_id,'HEALTHY') is False
    assert latest('draft-authority').state=='FAILED'
    observed=status('draft-authority',lambda *a,**k: (_ for _ in ()).throw(AssertionError('Failed operation must not probe')))
    assert observed.status.value=='FAILED'
    assert observed.hostPort==18088
    assert observed.errorMessage=='Timed out'


def test_wait_timeout_is_persisted_before_returning(session,monkeypatch):
    import pytest
    from app.services.local_runtime import begin,latest
    from app.services.docker_service import wait_deployment
    operation_id=begin('draft-authority','fingerprint','snapshot',18088)
    with pytest.raises(RuntimeError,match='timed out'):
        wait_deployment('draft-authority',timeout=0)
    assert latest('draft-authority').state=='FAILED'
    assert latest('draft-authority').operation_id==operation_id


def test_runtime_logs_survive_memory_clear_and_redact_credentials(session):
    from app.services import docker_service
    docker_service._log_message('draft-authority','Authorization: Bearer secret-runtime-token')
    docker_service._raw_log_history.clear()
    logs=docker_service.get_deployment_logs('draft-authority')
    assert len(logs)==1
    assert 'secret-runtime-token' not in logs[0]


def test_runtime_log_subscribers_have_independent_cursors(session):
    from app.services import docker_service
    first=docker_service.stream_logs('draft-authority')
    second=docker_service.stream_logs('draft-authority')
    assert 'keep-alive' in next(first)
    assert 'keep-alive' in next(second)
    docker_service._log_message('draft-authority','[BUILD] Compiling native application')
    assert '[BUILD]' in next(first)
    assert '[BUILD]' in next(second)
    first.close();second.close()


def test_source_only_stop_never_calls_docker(session,monkeypatch):
    import pytest
    from fastapi import HTTPException
    from app.services import runtime_lifecycle
    from app.services.docker_service import stop_deployment
    monkeypatch.setattr(runtime_lifecycle,'stop_owned',lambda *a: (_ for _ in ()).throw(AssertionError('Docker is forbidden')))
    with pytest.raises(HTTPException) as error: stop_deployment('draft-authority',str(session))
    assert error.value.status_code==403


def test_real_owned_process_is_reaped_on_cancel():
    import sys, threading, pytest
    from app.services.logged_process import run_logged, CommandCancelled
    control=threading.Event()
    seen=[]
    def output(line):
        seen.append(line)
        control.set()
    with pytest.raises(CommandCancelled):
        run_logged([sys.executable,'-u','-c','import time;print("ready",flush=True);time.sleep(30)'],
                   output,cancel_event=control,timeout=5)
    assert 'ready' in seen


def test_pre_cancel_does_not_spawn_process(monkeypatch):
    import subprocess, threading, pytest
    from unittest.mock import Mock
    from app.services.logged_process import run_logged, CommandCancelled
    control=threading.Event();control.set()
    spawn=Mock(side_effect=AssertionError('spawned cancelled command'))
    monkeypatch.setattr(subprocess,'Popen',spawn)
    with pytest.raises(CommandCancelled):
        run_logged(['unused'],lambda _:None,cancel_event=control)
    spawn.assert_not_called()


def test_deploy_control_observes_parent_pause_and_stop():
    import threading
    from app.services.docker_service import _DeploymentControl
    stop,pause=threading.Event(),threading.Event()
    control=_DeploymentControl((stop,pause))
    assert not control.is_set()
    pause.set();assert control.is_set()
    pause.clear();stop.set();assert control.is_set()
