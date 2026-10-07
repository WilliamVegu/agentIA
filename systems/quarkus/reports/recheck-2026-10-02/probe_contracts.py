"""Recheck HTTP defects with saved real AI outputs, without generating new outputs."""
import json, shutil, sqlite3
from pathlib import Path
import httpx

OUT=Path(__file__).resolve().parent
BASELINE=OUT.parent/'audit-2026-10-01'
WS=OUT/'runtime'/'workspaces'
C=httpx.Client(base_url='http://127.0.0.1:8011',timeout=120)
results=[]
def call(name,method,url,payload=None):
    r=C.request(method,url,json=payload)
    try: data=r.json()
    except ValueError: data={'bytes':len(r.content),'contentType':r.headers.get('content-type')}
    results.append({'name':name,'status':r.status_code,'response':data})
    (OUT/'contract-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    print(name,r.status_code,flush=True)
    return data

sid=json.loads((OUT/'session.json').read_text())['sessionId']
draft=json.loads((BASELINE/'draft.json').read_text(encoding='utf8'))
models=json.loads((BASELINE/'models.json').read_text(encoding='utf8'))
shutil.copyfile(BASELINE/'draft.json',OUT/'draft.json')
shutil.copyfile(BASELINE/'models.json',OUT/'models.json')
call('save_previous_real_draft','POST',f'/api/v1/requirements/sessions/{sid}/save',draft)
retrieved=call('reload_draft','GET',f'/api/v1/requirements/sessions/{sid}')
print('draft_preserved',retrieved.get('draft')==draft,flush=True)
call('save_previous_real_models','POST',f'/api/v1/models/sessions/{sid}/save',models)
print('schema_saved',(WS/sid/'schema.sql').exists(),flush=True)
call('valid_manual_repair','POST',f'/api/v1/sessions/{sid}/manual-repair',{'filePath':'repair.txt','modifiedCode':'audit'})
call('relative_manual_escape','POST',f'/api/v1/sessions/{sid}/manual-repair',{'filePath':'../outside.txt','modifiedCode':'audit'})
call('security_absolute_read','POST','/api/v1/security/remediate',{'findingId':'audit-unsupported','filePath':str(OUT/'runtime'/'outside-sentinel.txt')})
call('empty_audit','POST','/api/v1/security/audit',{'files':{},'pomXml':''})
call('pause_idle','POST',f'/api/v1/orchestrator/pipeline/{sid}/pause')
empty=call('create_empty_session','POST','/api/v1/sessions/quick-start',{'service_name':'audit-empty-second','prompt':'Un servicio gestiona reservas de salas de reuniones.','auto_run':False})
(OUT/'browser-session.json').write_text(json.dumps(empty))
sec=call('create_security_witness','POST','/api/v1/sessions/quick-start',{'service_name':'audit-security-witness','prompt':'Un servicio registra informacion de auditoria.','auto_run':False})
security_sid=sec['sessionId']
(WS/security_sid/'VulnerableController.java').write_text('public class VulnerableController {\n private BookRepository bookRepository;\n}\n')
call('witness_audit','GET',f'/api/v1/sessions/{security_sid}/audit')
call('blocked_export','GET',f'/api/v1/sessions/{security_sid}/export')
call('blocked_bundle','GET',f'/api/v1/orchestrator/sessions/{security_sid}/export-bundle')

# Replay a real former blocked project's artifacts in a new isolated session.
state=call('create_state_witness','POST','/api/v1/sessions/quick-start',{'service_name':'audit-state-witness','prompt':'Un servicio registra libros de biblioteca.','auto_run':False})
state_sid=state['sessionId']
shutil.copytree(BASELINE/'runtime'/'workspaces'/'2adaed5f-5695-4bd1-a8e6-68a029f82086',WS/state_sid,dirs_exist_ok=True)
db=sqlite3.connect(OUT/'runtime'/'studio.db')
table=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%verification_metrics_json%'").fetchone()[0]
metrics={'totalTests':0,'passedTests':0,'failedTests':0,'allPassed':False,'fallback_used':True,'fallback_reason':'Audit: Docker unavailable, no tests executed'}
db.execute(f'UPDATE {table} SET status=?,phase=?,error_message=?,verification_metrics_json=? WHERE id=?',('BLOCKED','FAILED','Audit: no verification',json.dumps(metrics),state_sid));db.commit()
call('blocked_state_before_get','GET',f'/api/v1/sessions/{state_sid}')
call('list_preserves_blocked','GET','/api/v1/sessions')
call('blocked_state_after_get','GET',f'/api/v1/sessions/{state_sid}')
call('blocked_overview','GET',f'/api/v1/orchestrator/sessions/{state_sid}/overview')
call('persisted_zero_metrics','GET',f'/api/v1/sessions/{state_sid}/metrics')
call('blocked_repairs','GET',f'/api/v1/sessions/{state_sid}/repairs')
call('unverified_export','GET',f'/api/v1/sessions/{state_sid}/export')
db.execute(f'UPDATE {table} SET status=?,phase=? WHERE id=?',('COMPLETED','VERIFIED',state_sid));db.commit();db.close()
call('legacy_false_verified_overview','GET',f'/api/v1/orchestrator/sessions/{state_sid}/overview')
call('legacy_false_verified_metrics','GET',f'/api/v1/sessions/{state_sid}/metrics')
print('Contract recheck finished',flush=True)
