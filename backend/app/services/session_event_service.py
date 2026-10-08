"""Committed event log is the dispatcher: every subscriber owns its cursor."""
import asyncio
import json
import time
from fastapi import HTTPException
from sqlalchemy import func
from app.models.session import SessionLocal, GenerationSessionDB
from app.models.reliability import SessionEvent, PipelineOperation
from app.services.operation_repository import append_event, transaction

SENSITIVE_FIELDS={'code','sourceCode','modifiedCode','generated_files','blueprint','diff','originalCode','remediatedCode'}


def event_payload(value):
    if isinstance(value, dict):
        return {key:event_payload(item) for key,item in value.items() if key not in SENSITIVE_FIELDS}
    if isinstance(value, list):
        return [event_payload(item) for item in value[:100]]
    if isinstance(value,str):
        return value[:4000]
    return value


def representation(row):
    data={**json.loads(row.payload_json), 'sessionId':row.session_id, 'sequence':row.sequence,
        'operationId':row.operation_id,'operationVersion':row.operation_version,
        'type':row.event_type,'event':row.event_type,'timestamp':row.created_at.isoformat()}
    return {'id':str(row.sequence),'event':row.event_type,'data':json.dumps(data,ensure_ascii=False)}


def publish_event(session_id,event_type,payload,retention=1000):
    with SessionLocal() as db:
        transaction(db)
        if not db.get(GenerationSessionDB,session_id):
            raise HTTPException(404,'Session not found')
        operation=db.query(PipelineOperation).filter_by(session_id=session_id).order_by(PipelineOperation.created_at.desc()).first()
        row=append_event(db,session_id,event_type,event_payload(payload),operation)
        db.flush()
        result=representation(row)
        limit=max(2,int(retention))
        db.query(SessionEvent).filter(SessionEvent.session_id==session_id,SessionEvent.sequence<=row.sequence-limit).delete()
        db.commit()
        return result


def read_events(session_id,after=0,limit=100):
    if not isinstance(after,int) or after<0:
        raise HTTPException(400,'Cursor inválido')
    with SessionLocal() as db:
        session=db.get(GenerationSessionDB,session_id)
        if not session:
            raise HTTPException(404,'Session not found')
        first,last=db.query(func.min(SessionEvent.sequence),func.max(SessionEvent.sequence)).filter_by(session_id=session_id).one()
        if (not last and after>0) or last and (after>last or after!=0 and after<first-1 or after==0 and first>1):
            return [{'id':str(last or 0),'event':'resync_required','data':json.dumps({'sessionId':session_id,
                'sequence':last or 0,'type':'resync_required','snapshot':{'status':session.status.value,
                'currentPhase':session.current_lifecycle_phase,'revisionId':session.revision_id,
                'operationVersion':session.operation_version}})}]
        rows=db.query(SessionEvent).filter(SessionEvent.session_id==session_id,SessionEvent.sequence>after).order_by(SessionEvent.sequence).limit(min(100,max(1,limit))).all()
        return [representation(row) for row in rows]


async def async_events(session_id,request,after=0):
    cursor=after
    while not await request.is_disconnected():
        events=read_events(session_id,cursor)
        for event in events:
            cursor=int(event['id'])
            yield event
        if not events:
            yield {'comment':'keepalive'}
            await asyncio.sleep(.5)


def stream_events(session_id,after=0):
    cursor=after
    while True:
        events=read_events(session_id,cursor)
        for event in events:
            cursor=int(event['id'])
            yield 'id: '+event['id']+'\nevent: '+event['event']+'\ndata: '+event['data']+'\n\n'
        if not events:
            yield ': keepalive\n\n'
            time.sleep(.5)
