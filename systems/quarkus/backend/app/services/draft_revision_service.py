"""Immutable SQLite authority for complete drafts; files are projections only."""
import hashlib
import json
from pathlib import Path
from fastapi import HTTPException
from pydantic import ValidationError
from app.models.session import SessionLocal, GenerationSessionDB
from app.models.reliability import DraftRevision, SessionConfiguration, ArtifactProvenance, VerificationRun, AuditRun, PipelineOperation
from app.models.requirements import SpecificationDraft
from app.services.secret_redaction import without_credentials
from app.services.workspace_guard import get_validated_workspace_path, atomic_write_workspace_file
from app.services.session_operation_lock import SessionOperationLock


def canonical(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def representation(row):
    return {'revisionId': row.revision_id, 'canonicalHash': row.canonical_hash,
            'schemaVersion': row.schema_version, 'source': row.source,
            'approvalStatus': row.approval_status, 'draft': json.loads(row.payload_json)}


def validate(payload):
    try:
        from app.services.domain_descriptor import normalize_blueprint
        validated=SpecificationDraft.model_validate(without_credentials(payload)).model_dump()
        normalize_blueprint(validated)
        return validated
    except ValueError as error:
        if not isinstance(error, ValidationError):
            raise HTTPException(422, str(error))

        raise HTTPException(422, detail=error.errors(include_context=False))


def save_revision(session_id, payload, *, expected_revision_id=None, expected_version=None, source='MANUAL', _operation_id=None):
    get_validated_workspace_path(session_id, require_exists=True)
    payload = validate(payload)
    lock = SessionOperationLock(session_id)
    if _operation_id is None and not lock.acquire(False):
        raise HTTPException(409, 'Otra operación escribe esta sesión')
    try:
        from app.services.workspace_guard import resolve_workspace_file
        for relative in ('specification_draft.json', 'user_stories.json', 'entities.json', 'spec.md'):
            projection = resolve_workspace_file(session_id, relative)
            if projection.exists() and not projection.is_file():
                raise HTTPException(409, 'La proyección no es un archivo: ' + relative)
        with SessionLocal() as db:
            session = db.get(GenerationSessionDB, session_id)
            if expected_version is not None and (session.configuration_version or 0) != expected_version:
                raise HTTPException(409, 'La configuración ha cambiado; recargue antes de guardar')
            if expected_revision_id is not None and session.revision_id != expected_revision_id:
                raise HTTPException(409, 'La revisión ha cambiado; recargue antes de guardar')
            active = db.query(PipelineOperation).filter_by(session_id=session_id).filter(
                PipelineOperation.state.in_(['QUEUED', 'RUNNING', 'PAUSE_REQUESTED', 'CANCEL_REQUESTED'])).first()
            if active and active.operation_id != _operation_id:
                raise HTTPException(409, 'La operación activa conserva su revisión; espere o cancele')
            row = DraftRevision(session_id=session_id, payload_json=canonical(payload),
                canonical_hash=hashlib.sha256(canonical(payload).encode()).hexdigest(), source=source,
                approval_status='DRAFT', parent_revision_id=session.revision_id)
            db.add(row); db.flush()
            session.revision_id = row.revision_id
            session.database_engine = payload["databaseMode"].upper()
            session.configuration_version = (session.configuration_version or 0) + 1
            mode = getattr(session, 'execution_mode', 'SOURCE_ONLY')
            mode = getattr(mode, 'value', mode)
            db.add(SessionConfiguration(session_id=session_id, version=session.configuration_version,
                database_engine=payload['databaseMode'].upper(), execution_mode=mode,
                host_port=payload['basePort'], framework='quarkus',
                build_tool=(payload.get('inputInterface') or {}).get('buildToolPreference') or 'maven'))
            for model in (ArtifactProvenance,):
                db.query(model).filter_by(session_id=session_id).update({'status': 'OUTDATED'})
            for model in (VerificationRun, AuditRun):
                db.query(model).filter_by(session_id=session_id).update({'validity': 'OUTDATED'})
            if _operation_id:
                if not active or active.operation_id != _operation_id or active.revision_id is not None:
                    raise HTTPException(409, 'No se puede sustituir la revisión capturada')
                active.revision_id = row.revision_id
                active.config_version = session.configuration_version
            db.commit()
            result = {**representation(row), 'configurationVersion':session.configuration_version}
        # Failure remains observable. The committed revision is retrievable even if projection fails.
        project_revision(session_id, payload)
        return result
    finally:
        if _operation_id is None:
            lock.release()


def project_revision(session_id, payload):
    from app.services.requirements_service import serialize_draft_to_markdown
    for name, data in [('specification_draft.json', payload), ('user_stories.json', payload['userStories']),
                       ('entities.json', payload['entities'])]:
        atomic_write_workspace_file(session_id, name, json.dumps(data, indent=2, ensure_ascii=False))
    atomic_write_workspace_file(session_id, 'spec.md', payload['markdownSpec'] or serialize_draft_to_markdown(SpecificationDraft.model_validate(payload)))


def approve_revision(session_id, revision_id, *, expected_version=None):
    get_validated_workspace_path(session_id, require_exists=True)
    lock = SessionOperationLock(session_id)
    if not lock.acquire(False):
        raise HTTPException(409, 'Otra operación escribe esta sesión')
    try:
        with SessionLocal() as db:
            session = db.get(GenerationSessionDB, session_id)
            row = db.get(DraftRevision, revision_id)
            if expected_version is not None and (session.configuration_version or 0) != expected_version:
                raise HTTPException(409, 'La configuración ha cambiado; recargue antes de aprobar')
            if not row or row.session_id != session_id:
                raise HTTPException(404, 'Revisión inexistente')
            if session.revision_id != revision_id:
                raise HTTPException(409, 'Sólo puede aprobar la revisión vigente')
            validate(json.loads(row.payload_json))
            row.approval_status = 'APPROVED'
            db.commit()
            return {**representation(row), 'configurationVersion':session.configuration_version}
    finally:
        lock.release()


def get_revision(session_id, revision_id=None):
    ws = get_validated_workspace_path(session_id, require_exists=True)
    with SessionLocal() as db:
        session = db.get(GenerationSessionDB, session_id)
        row = db.get(DraftRevision, revision_id or session.revision_id) if revision_id or session.revision_id else None
        if row:
            if row.session_id != session_id:
                raise HTTPException(404, 'Revisión inexistente')
            return {**representation(row), 'configurationVersion':session.configuration_version}
    if revision_id:
        raise HTTPException(404, 'Revisión inexistente')
    path = ws / 'specification_draft.json'
    if path.exists():
        from app.services.workspace_guard import resolve_workspace_file
        path = resolve_workspace_file(session_id, 'specification_draft.json', require_exists=True)
        try:
            payload = validate(json.loads(path.read_text(encoding='utf-8')))
        except (HTTPException, ValueError):
            return {'revisionId': None, 'approvalStatus': 'NEEDS_REVIEW', 'draft': None, 'source': 'LEGACY'}
        # Read-only recovery never supplies an invented configuration or approval.
        raw = json.loads(path.read_text(encoding='utf-8'))
        required = {'serviceName','packageName','basePort','entities','userStories'}
        return {'revisionId':None, 'approvalStatus':'NEEDS_REVIEW', 'source':'LEGACY',
                'draft':without_credentials(raw) if required.issubset(raw) else None}
    return {'revisionId': None, 'approvalStatus': 'NEEDS_REVIEW', 'draft': None, 'source': None}


def record_artifact(session_id, relative_path, phase, revision_id):
    from app.services.workspace_guard import resolve_workspace_file
    file = resolve_workspace_file(session_id, relative_path, require_exists=True)
    with SessionLocal() as db:
        revision = db.get(DraftRevision, revision_id)
        if not revision or revision.session_id != session_id:
            raise HTTPException(409, 'Revisión de artefacto inválida')
        session = db.get(GenerationSessionDB, session_id)
        db.merge(ArtifactProvenance(session_id=session_id, relative_path=relative_path, phase=phase,
            revision_id=revision_id, input_hash=revision.canonical_hash,
            content_hash=hashlib.sha256(file.read_bytes()).hexdigest(),
            status='CURRENT' if session.revision_id == revision_id else 'OUTDATED'))
        db.commit()


def prepare_regeneration(session_id, revision_id):
    """Explicit action: archive owned generated files before removing outdated projections."""
    import uuid,zipfile,os
    from app.services.workspace_guard import resolve_workspace_file,io_path
    ws=get_validated_workspace_path(session_id,require_exists=True)
    lock=SessionOperationLock(session_id)
    if not lock.acquire(False): raise HTTPException(409,'Otra operación escribe esta sesión')
    try:
        with SessionLocal() as db:
            session=db.get(GenerationSessionDB,session_id)
            if session.revision_id!=revision_id: raise HTTPException(409,'La revisión ha cambiado')
            if db.query(PipelineOperation).filter_by(session_id=session_id).filter(PipelineOperation.state.in_(['QUEUED','RUNNING','PAUSE_REQUESTED','CANCEL_REQUESTED'])).first():
                raise HTTPException(409,'Espere a la operación activa')
            items=db.query(ArtifactProvenance).filter_by(session_id=session_id,status='OUTDATED').all()
            if not items: raise HTTPException(409,'No hay artefactos obsoletos que regenerar')
            sources={item.relative_path:resolve_workspace_file(session_id,item.relative_path,require_exists=True) for item in items}
            directory=ws/'.agentia-runtime/backups'
            from app.services.workspace_guard import _reject_links
            _reject_links(directory,ws)
            io_path(directory).mkdir(parents=True,exist_ok=True)
            backup=directory/('before-regeneration-'+uuid.uuid4().hex+'.zip')
            temporary=backup.with_suffix('.tmp')
            hashes={}
            with zipfile.ZipFile(io_path(temporary),'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for relative,file in sources.items():
                    payload=io_path(file).read_bytes();hashes[relative]=hashlib.sha256(payload).hexdigest();archive.writestr(relative,payload)
                archive.writestr('BACKUP_MANIFEST.json',canonical({'revisionId':revision_id,'files':hashes}))
            with zipfile.ZipFile(io_path(temporary)) as archive:
                if archive.testzip(): raise OSError('Backup corrupto; no se borró ninguna fuente')
            os.replace(io_path(temporary),io_path(backup))
            # A race or file change cannot silently discard the newer edit.
            for relative,file in sources.items():
                current=resolve_workspace_file(session_id,relative,require_exists=True)
                if hashlib.sha256(io_path(current).read_bytes()).hexdigest()!=hashes[relative]:
                    raise HTTPException(409,'Una fuente cambió durante el backup')
            for relative,file in sources.items(): io_path(resolve_workspace_file(session_id,relative,require_exists=True)).unlink()
            db.query(ArtifactProvenance).filter_by(session_id=session_id,status='OUTDATED').delete()
            db.commit()
            return backup
    finally: lock.release()



def update_execution_configuration(db,session,mode):
    """Preserve configuration history when the execution choice changes."""
    if session.execution_mode==mode: return
    current=db.query(SessionConfiguration).filter_by(session_id=session.id,version=session.configuration_version).first()
    if current:
        version=session.configuration_version+1
        db.add(SessionConfiguration(session_id=session.id,version=version,
            database_engine=current.database_engine,execution_mode=mode,host_port=current.host_port,
            framework=current.framework,build_tool=current.build_tool))
        session.configuration_version=version
    session.execution_mode=mode
