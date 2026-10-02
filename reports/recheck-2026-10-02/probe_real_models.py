"""Observe exceptions in the original model service during a REAL DeepSeek call."""
import json, os, sys, time
from pathlib import Path
OUT=Path(__file__).resolve().parent
os.environ['ALLOW_OFFLINE_MOCK']='false'
sys.path.insert(0,str(OUT.parents[1]/'backend'))
from app.models.requirements import SpecificationDraft
from app.services.model_sql_service import model_sql_service
errors=[]
def trace(frame,event,arg):
    if event=='exception' and frame.f_code.co_filename.endswith('model_sql_service.py'):
        kind,value,_=arg
        errors.append({'line':frame.f_lineno,'type':kind.__name__,'message':str(value).replace(os.environ['AUDIT_DEEPSEEK_KEY'],'[REDACTED]')})
    return trace
draft=SpecificationDraft(**json.loads((OUT/'draft.json').read_text(encoding='utf8')))
started=time.monotonic();sys.settrace(trace)
try:
    response=model_sql_service.synthesize_domain_models_and_sql(draft,api_key=os.environ['AUDIT_DEEPSEEK_KEY'],provider='deepseek',model_name='deepseek-flash')
    data={'seconds':round(time.monotonic()-started,2),'exceptions':errors,'response':response.model_dump(mode='json')}
finally:
    sys.settrace(None)
(OUT/'real-model-results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'seconds':data['seconds'],'exceptions':errors}),flush=True)
