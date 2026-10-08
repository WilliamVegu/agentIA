"""Durable, additive records; each studio owns its own engine and metadata."""
from datetime import datetime, timezone
from enum import Enum
import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, CheckConstraint, Index, event
from app.models.session import Base


def now():
    return datetime.now(timezone.utc)


class OperationState(str, Enum):
    QUEUED = 'QUEUED'
    RUNNING = 'RUNNING'
    PAUSE_REQUESTED = 'PAUSE_REQUESTED'
    PAUSED = 'PAUSED'
    CANCEL_REQUESTED = 'CANCEL_REQUESTED'
    CANCELLED = 'CANCELLED'
    COMPLETED = 'COMPLETED'
    BLOCKED = 'BLOCKED'
    INTERRUPTED = 'INTERRUPTED'


class DraftRevision(Base):
    __tablename__ = 'draft_revisions'
    revision_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey('generation_sessions.id'), nullable=False, index=True)
    schema_version = Column(Integer, nullable=False, default=1)
    payload_json = Column(Text, nullable=False)
    canonical_hash = Column(String(64), nullable=False)
    source = Column(String(32), nullable=False)
    approval_status = Column(String(24), nullable=False, default='DRAFT')
    parent_revision_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False, default=now)


@event.listens_for(DraftRevision, 'before_update')
def immutable_draft(mapper, connection, target):
    from sqlalchemy import inspect
    protected = ('session_id', 'payload_json', 'canonical_hash', 'source', 'schema_version', 'parent_revision_id')
    if any(inspect(target).attrs[name].history.has_changes() for name in protected):
        raise ValueError('Una revisión es inmutable; cree otra revisión')


class SessionConfiguration(Base):
    __tablename__ = 'session_configurations'
    session_id = Column(String(36), ForeignKey('generation_sessions.id'), primary_key=True)
    version = Column(Integer, primary_key=True, default=1)
    database_engine = Column(String(20), nullable=False)
    execution_mode = Column(String(20), nullable=False)
    host_port = Column(Integer, nullable=False)
    framework = Column(String(20), nullable=False)
    build_tool = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, default=now)
    __table_args__ = (
        CheckConstraint("database_engine IN ('H2','POSTGRESQL','MYSQL')"),
        CheckConstraint("execution_mode IN ('SOURCE_ONLY','DOCKER')"),
        CheckConstraint('host_port BETWEEN 1024 AND 65535'),
        CheckConstraint("framework IN ('springboot','quarkus')"),
        CheckConstraint("build_tool IN ('maven','gradle')"),
    )


class PipelineOperation(Base):
    __tablename__ = 'pipeline_operations'
    operation_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey('generation_sessions.id'), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    target_phase = Column(String(40), nullable=False)
    revision_id = Column(String(36), ForeignKey('draft_revisions.revision_id'), nullable=True)
    config_version = Column(Integer, nullable=False, default=1)
    state = Column(String(24), nullable=False)
    checkpoint_json = Column(Text, nullable=False, default='{}')
    options_json = Column(Text, nullable=False, default='{}')
    requested_control = Column(String(24), nullable=True)
    error_code = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=now)
    updated_at = Column(DateTime, nullable=False, default=now)
    lease_until = Column(DateTime, nullable=True)


_active = PipelineOperation.state.in_(('QUEUED', 'RUNNING', 'PAUSE_REQUESTED', 'CANCEL_REQUESTED'))
Index('one_active_operation_per_session', PipelineOperation.session_id, unique=True,
      sqlite_where=_active, postgresql_where=_active)


class ArtifactProvenance(Base):
    __tablename__ = 'artifact_provenance'
    session_id = Column(String(36), ForeignKey('generation_sessions.id'), primary_key=True)
    relative_path = Column(String(1024), primary_key=True)
    phase = Column(String(40), nullable=False)
    revision_id = Column(String(36), nullable=True)
    input_hash = Column(String(64), nullable=False)
    content_hash = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default='CURRENT')
    __table_args__ = (CheckConstraint("status IN ('CURRENT','OUTDATED')"),)


class VerificationRun(Base):
    __tablename__ = 'verification_runs'
    run_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey('generation_sessions.id'), nullable=False, index=True)
    operation_id = Column(String(36), nullable=True)
    revision_id = Column(String(36), nullable=True)
    snapshot_id = Column(String(100), nullable=True)
    fingerprint = Column(String(64), nullable=True)
    outcome = Column(String(30), nullable=False)
    validity = Column(String(20), nullable=False, default='CURRENT')
    runner = Column(String(100), nullable=True)
    exit_code = Column(Integer, nullable=True)
    metrics_json = Column(Text, nullable=False, default='{}')
    report_paths_json = Column(Text, nullable=False, default='[]')
    created_at = Column(DateTime, nullable=False, default=now)


class AuditRun(Base):
    __tablename__ = 'audit_runs'
    run_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey('generation_sessions.id'), nullable=False, index=True)
    fingerprint = Column(String(64), nullable=True)
    evaluated_status = Column(String(20), nullable=False)
    validity = Column(String(20), nullable=False, default='CURRENT')
    score = Column(Integer, nullable=True)
    source_count = Column(Integer, nullable=False, default=0)
    rule_set_version = Column(String(40), nullable=False)
    findings_json = Column(Text, nullable=False, default='[]')
    created_at = Column(DateTime, nullable=False, default=now)


class DeploymentOperation(Base):
    __tablename__ = 'deployment_operations'
    operation_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey('generation_sessions.id'), nullable=False, index=True)
    source_snapshot_id = Column(String(100), nullable=True)
    fingerprint = Column(String(64), nullable=True)
    framework = Column(String(20), nullable=False)
    compose_project = Column(String(100), nullable=True)
    labels_json = Column(Text, nullable=False, default='{}')
    container_ids_json = Column(Text, nullable=False, default='[]')
    image_id = Column(String(200), nullable=True)
    bindings_json = Column(Text, nullable=False, default='{}')
    state = Column(String(30), nullable=False)
    error_code = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=now)
    updated_at = Column(DateTime, nullable=False, default=now)


class RepairAttempt(Base):
    __tablename__ = 'repair_attempts'
    repair_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey('generation_sessions.id'), nullable=False, index=True)
    operation_id = Column(String(36), nullable=True)
    relative_path = Column(String(1024), nullable=False)
    before_hash = Column(String(64), nullable=True)
    after_hash = Column(String(64), nullable=True)
    guidance_hint = Column(Text, nullable=True)
    verification_run_id = Column(String(36), nullable=True)
    outcome = Column(String(40), nullable=False)
    iteration = Column(Integer, nullable=False, default=0)
    automatic = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=now)
    __table_args__ = (CheckConstraint('automatic = 0 OR iteration BETWEEN 1 AND 3'),)


class SessionEvent(Base):
    __tablename__ = 'session_events'
    session_id = Column(String(36), ForeignKey('generation_sessions.id'), primary_key=True)
    sequence = Column(Integer, primary_key=True)
    event_type = Column(String(80), nullable=False)
    operation_id = Column(String(36), nullable=True)
    operation_version = Column(Integer, nullable=True)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=now)


class SchemaMigration(Base):
    __tablename__ = 'schema_migrations'
    migration_version = Column(Integer, primary_key=True)
    checksum = Column(String(64), nullable=False)
    applied_at = Column(DateTime, nullable=False, default=now)


@event.listens_for(VerificationRun, 'before_update')
@event.listens_for(AuditRun, 'before_update')
def immutable_outcome(mapper, connection, target):
    from sqlalchemy import inspect
    for column in mapper.columns:
        if column.key != 'validity' and inspect(target).attrs[column.key].history.has_changes():
            raise ValueError('El resultado histórico es inmutable; cree una nueva ejecución')
