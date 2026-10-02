"""Observe real Git configuration writes in a disposable repo; no remote publish.

The destination is an unreachable localhost port and the token is an audit sentinel,
never the DeepSeek credential. Python tracing observes the original service unchanged.
"""
import json
import os
import sys
from pathlib import Path

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parents[1]/'backend'))
from app.services.git_service import publish_to_git
workspace=OUT/'runtime'/'git-probe'
workspace.mkdir(exist_ok=True)
(workspace/'audit.txt').write_text('Disposable Git audit witness',encoding='utf8')
token='AUDIT_TOKEN_SENTINEL_ONLY'
observations=[]
def trace(frame,event,arg):
    if frame.f_code.co_name=='publish_to_git' and event=='line':
        config=workspace/'.git'/'config'
        if config.exists() and token in config.read_text(encoding='utf8'):
            observations.append({'line':frame.f_lineno,'credential_on_disk':True})
    return trace
os.environ['GIT_TERMINAL_PROMPT']='0'
sys.settrace(trace)
try:
    publish_to_git(str(workspace),'https://127.0.0.1:9/audit.git','audit-probe',git_token=token)
except Exception as e:
    error=str(e).replace(token,'[AUDIT_TOKEN]')
else:
    error=None
finally:
    sys.settrace(None)
data={'credential_observed_on_disk':bool(observations),'observations':observations,
      'credential_remaining_after_failure':token in (workspace/'.git'/'config').read_text(encoding='utf8'),
      'error':error}
(OUT/'git-results.json').write_text(json.dumps(data,indent=2),encoding='utf8')
print(json.dumps(data,indent=2))
