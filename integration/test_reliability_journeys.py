"""Runner unit contracts; full acceptance is executed by reliability_smoke, never mocked as green."""
from pathlib import Path
import pytest
from integration.reliability_smoke import environment,run_suite,report_counts,SUITES
from integration.reliability_fixtures import ROOT

def test_runner_rejects_user_workspace(tmp_path):
    with pytest.raises(ValueError,match='aislado'):
        run_suite('journeys',ROOT/'backend/workspaces',tmp_path)

def test_runtime_requires_explicit_docker(tmp_path):
    with pytest.raises(ValueError,match='--docker'):
        run_suite('runtime',tmp_path/'isolated',tmp_path/'evidence')

def test_credentials_removed_and_platform_import_isolated(tmp_path,monkeypatch):
    monkeypatch.setenv('EXAMPLE_API_KEY','test-sentinel')
    monkeypatch.setenv('GH_TOKEN','test-sentinel')
    env=environment(tmp_path,tmp_path/'backend')
    assert 'EXAMPLE_API_KEY' not in env and 'GH_TOKEN' not in env
    assert env['PYTHONPATH'].split(__import__('os').pathsep)[0]==str(tmp_path/'backend')
    assert env['ALLOW_HERMETIC_FALLBACK']=='false'

def test_journeys_cover_delivery_repair_git_and_event_contracts():
    assert {'test_e2e_flow.py','test_persisted_repair.py','test_git_safety.py','test_session_events.py'}<=set(SUITES['journeys'])

def test_xml_counts_include_failures_and_skips(tmp_path):
    report=tmp_path/'results.xml'
    report.write_text('<testsuites><testsuite tests="3" failures="1" errors="0" skipped="1"/></testsuites>')
    assert report_counts(report)==dict(tests=3,failures=1,errors=0,skipped=1)
