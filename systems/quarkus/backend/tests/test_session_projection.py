import pytest
from fastapi import HTTPException
from app.services.secret_redaction import redact, without_credentials
from app.services.session_projection import measured_metrics, canonical_alias


def test_zero_and_unknown_are_not_examples():
    assert measured_metrics({}) == {'totalTests': 0, 'passedTests': 0, 'failedTests': 0, 'qualityScore': None, 'testsExecuted': False}
    assert measured_metrics({'totalTests': '3'})['testsExecuted'] is False
    assert measured_metrics({'totalTests': 3, 'fallback_used': True})['testsExecuted'] is False
    assert measured_metrics({'qualityScore': 0})['qualityScore'] == 0


def test_alias_conflict_is_visible():
    assert canonical_alias({'database': 'H2'}, 'databaseEngine', 'database') == 'H2'
    with pytest.raises(HTTPException) as failure:
        canonical_alias({'database': 'H2', 'databaseEngine': 'MYSQL'}, 'databaseEngine', 'database')
    assert failure.value.status_code == 422


def test_credentials_removed_from_options_and_errors():
    token = 'sk-' + 'a' * 32
    payload = {'apiKey': token, 'nested': {'authorization': 'Basic private', 'name': 'safe'}, 'message': f'https://user:{token}@github.com/x {token}'}
    result = redact(payload)
    assert token not in str(result)
    clean = without_credentials(payload)
    assert 'apiKey' not in clean
    assert 'authorization' not in clean['nested']
    assert clean['nested']['name'] == 'safe'
