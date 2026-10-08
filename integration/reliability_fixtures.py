"""Owned, isolated resources for dual-studio regression tests. No production mocks."""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import os
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent.parent
PROTECTED = tuple(ROOT / backend / directory
    for backend in ('backend','systems/quarkus/backend')
    for directory in ('workspaces','specifications','quarkus_workspaces','quarkus_specifications'))


def assert_isolated(path: Path) -> Path:
    path = path.resolve()
    if path == ROOT or any(path == p.resolve() or path.is_relative_to(p.resolve()) for p in PROTECTED):
        raise ValueError('Pruebas requieren un workspace aislado, nunca datos de usuario')
    if path.name in {'studio.db', 'cost_tracking.db','quarkus_studio.db','quarkus_cost_tracking.db'}:
        raise ValueError('No usar bases de datos originales')
    return path


@dataclass(frozen=True)
class IsolatedStudio:
    root: Path
    identifier: str

    @property
    def labels(self):
        return {'agentia.reliability-test': self.identifier}

    @property
    def environment(self):
        return {
            'DATABASE_URL': f'sqlite:///{(self.root / "test-session.db").as_posix()}',
            'WORKSPACE_DIR': str(self.root / 'workspaces'),
            'SPECIFICATION_DIR': str(self.root / 'specifications'),
            'COST_STORE_PATH': str(self.root / 'test-cost.db'),
            'ALLOW_OFFLINE_MOCK': 'false',
            'ALLOW_HERMETIC_FALLBACK': 'false',
            'MLFLOW_TRACKING_URI': (self.root / 'mlruns').as_uri(),
        }

    def owns(self, labels):
        return labels.get('agentia.reliability-test') == self.identifier


@contextmanager
def isolated_studio(parent=None):
    if parent is not None:
        parent = assert_isolated(Path(parent))
        parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='reliability-', dir=parent) as directory:
        studio = IsolatedStudio(assert_isolated(Path(directory)), uuid.uuid4().hex)
        previous = {key: os.environ.get(key) for key in studio.environment}
        try:
            os.environ.update(studio.environment)
            yield studio
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def ledger_draft():
    return {
        'serviceName': 'ledger-service', 'packageName': 'com.audit.custom', 'basePort': 18088,
        'databaseMode': 'H2',
        'entities': [{'name': 'LedgerEntry', 'tableName': 'ledger_entries', 'attributes': [
            {'name': 'entryId', 'type': 'UUID', 'nullable': False, 'isPrimaryKey': True},
            {'name': 'email', 'type': 'String', 'nullable': False, 'isUnique': True, 'validationRules': ['@Email']},
            {'name': 'balance', 'type': 'BigDecimal', 'nullable': False, 'validationRules': ['@Positive']},
            {'name': 'bookedAt', 'type': 'Instant', 'nullable': False},
        ]}],
        'userStories': [{'id': 'US-1', 'priority': 'P1', 'role': 'contable', 'intent': 'registrar un asiento',
                        'benefit': 'mantener el libro correcto', 'scenarios': [
                            {'scenarioId': 'AC-1.1', 'given': 'un correo válido y saldo positivo',
                             'when': 'se crea un asiento', 'then': 'se conserva su UUID y fecha'}]}],
        'assumptions': [], 'markdownSpec': 'Libro contable personalizado',
        'inputInterface': {'buildToolPreference': 'maven'},
    }


def relational_ledger_draft():
    """Add explicitly declared UUID foreign key and both calendar date types."""
    draft=ledger_draft()
    draft['entities'].insert(0,{'name':'LedgerAccount','tableName':'ledger_accounts','attributes':[
        {'name':'accountId','columnName':'account_key','type':'UUID','isPrimaryKey':True,'nullable':False},
        {'name':'name','type':'String','nullable':False}]})
    draft['entities'][1]['attributes'].extend([
        {'name':'accountKey','columnName':'owner_account','type':'UUID','nullable':False,'referencesEntity':'LedgerAccount','referencesAttribute':'accountId'},
        {'name':'effectiveDate','type':'LocalDate','nullable':False},
        {'name':'recordedAt','type':'LocalDateTime','nullable':False}])
    return draft
