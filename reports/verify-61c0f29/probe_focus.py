"""Local regression checks: session paths, gates and shared concurrency capacity."""
import asyncio,json,sys
from pathlib import Path
import httpx
OUT=Path(__file__).resolve().parent
C=httpx.Client(base_url='http://127.0.0.1:8011',timeout=30)
results={}
for name,path,data in [
    ('model_save_parent','/api/v1/models/sessions/%2e%2e/save',{'auditContainmentWitness':True}),
    ('requirements_save_parent','/api/v1/requirements/sessions/%2e%2e/save',json.loads((OUT/'draft.json').read_text(encoding='utf8'))),
    ('empty_payload_audit','/api/v1/security/audit',{'files':{},'pomXml':''}),
]:
    r=C.post(path,json=data);results[name]={'status':r.status_code,'response':r.json()}
results['outside_write_exists']=(OUT/'runtime/domain_model.json').exists()
sys.path.insert(0,str(OUT.parents[1]/'backend'))
from app.services.queue_service import ConcurrencyQueueManager
async def check_queue():
    q=ConcurrencyQueueManager(max_concurrent=1)
    await q.acquire_slot('async-worker')
    q.acquire_slot_sync('thread-worker')
    data=await q.get_queue_status()
    q.release_slot_sync('thread-worker');await q.release_slot('async-worker')
    return data
results['shared_queue_limit_one']=asyncio.run(check_queue())
(OUT/'focus-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(results,ensure_ascii=False,indent=2))
