import os
import pytest
from integration.reliability_fixtures import ROOT, assert_isolated, isolated_studio, ledger_draft


def test_original_workspaces_and_databases_rejected():
    for path in (ROOT, ROOT / 'backend/workspaces/x', ROOT / 'systems/quarkus/backend/workspaces/x', ROOT / 'studio.db',
                 ROOT / 'systems/quarkus/backend/quarkus_workspaces/x',
                 ROOT / 'systems/quarkus/backend/quarkus_specifications/x',
                 ROOT / 'systems/quarkus/backend/quarkus_studio.db'):
        with pytest.raises(ValueError):
            assert_isolated(path)


def test_environment_restored_and_resources_owned(tmp_path):
    previous = os.environ.get('DATABASE_URL')
    with isolated_studio(tmp_path) as studio:
        assert studio.root.exists()
        assert os.environ['DATABASE_URL'].endswith('test-session.db')
        assert studio.owns(studio.labels)
        assert not studio.owns({'agentia.reliability-test': 'someone-else'})
        directory = studio.root
    assert not directory.exists()
    assert os.environ.get('DATABASE_URL') == previous


def test_draft_contains_audit_regression_inputs():
    draft = ledger_draft()
    assert draft['basePort'] == 18088
    assert draft['entities'][0]['attributes'][0]['type'] == 'UUID'
