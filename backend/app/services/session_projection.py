"""Evidence projections preserve unknown/null values and historical outcomes."""
import json
from fastapi import HTTPException
from app.services.secret_redaction import redact


def decode(value, default=None):
    if value is None:
        return default
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return default


def require_session(db, session_id):
    from app.models.session import GenerationSessionDB
    row = db.get(GenerationSessionDB, session_id)
    if row is None:
        raise HTTPException(404, 'Session not found')
    return row


def canonical_alias(payload, canonical, *aliases):
    supplied = [payload[key] for key in (canonical, *aliases) if key in payload]
    if supplied and any(value != supplied[0] for value in supplied[1:]):
        raise HTTPException(422, f'Conflicting aliases for {canonical}')
    return supplied[0] if supplied else None


def measured_metrics(metrics):
    metrics = decode(metrics, {})
    if not isinstance(metrics, dict):
        metrics = {}
    def count(name):
        value = metrics.get(name, 0)
        return value if type(value) is int and value >= 0 else 0
    return redact({
        'totalTests': count('totalTests'),
        'passedTests': count('passedTests'),
        'failedTests': count('failedTests'),
        'qualityScore': metrics.get('qualityScore'),
        'testsExecuted': bool(count('totalTests') > 0 and not metrics.get('fallback_used')
                              and not metrics.get('verificationSkipped') and not metrics.get('verificationInterrupted')),
    })
