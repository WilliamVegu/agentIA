"""Resolve saved project settings without probing Docker or the network."""
import json
from pathlib import Path
from app.services.build_layout import build_layout


def resolve_configuration(workspace, session_id=None, database=None, port=None):
    ws = Path(workspace)
    saved = {}
    authority=None
    if session_id:
        from app.models.session import SessionLocal
        from app.models.reliability import SessionConfiguration
        with SessionLocal() as db:
            authority=db.query(SessionConfiguration).filter_by(session_id=session_id).order_by(SessionConfiguration.version.desc()).first()
            if authority:
                saved={'databaseEngine':authority.database_engine,'hostPort':authority.host_port}
    path = ws / 'ASSET_CONFIGURATION.json'
    if not authority and path.is_file():
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(saved, dict) or saved.get('formatVersion') != 1 or (session_id and saved.get('sessionId') != session_id):
                raise ValueError('identity')
            if saved.get('databaseEngine') not in {'POSTGRESQL', 'MYSQL', 'H2'} or type(saved.get('hostPort')) is not int or not 1024 <= saved['hostPort'] <= 65535:
                raise ValueError('settings')
        except (ValueError, TypeError) as exc:
            raise ValueError('Configuración local inválida o ajena; no se reemplaza por defaults.') from exc
    engine = database.value if hasattr(database, 'value') else database
    engine = str(engine).upper() if engine is not None else None
    if authority and ((engine is not None and engine != authority.database_engine) or (port is not None and port != authority.host_port)):
        raise ValueError('Conflicto con la configuración aprobada; guarde una nueva revisión antes de cambiar motor o puerto.')
    engine = engine or saved.get('databaseEngine')
    if engine is None and session_id:
        from app.models.session import SessionLocal, GenerationSessionDB
        with SessionLocal() as db:
            row = db.get(GenerationSessionDB, session_id)
            engine = row.database_engine if row else None
    engine = str(engine or 'POSTGRESQL').upper()
    selected_port = port if port is not None else saved.get('hostPort', 8080)
    if engine not in {'POSTGRESQL', 'MYSQL', 'H2'} or type(selected_port) is not int or not 1024 <= selected_port <= 65535:
        raise ValueError('Motor o puerto local inválido; corrija la configuración explícitamente.')
    tool, directory, manifest = build_layout(ws)
    return {'databaseEngine': engine, 'hostPort': selected_port, 'buildTool': tool,
            'buildDirectory': directory, 'buildManifest': manifest}
