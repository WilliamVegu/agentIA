"""Parse every application/script Python file and probe the optional inference input."""
import ast
import json
import os
import sys
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
os.environ['DATABASE_URL']=f"sqlite:///{(OUT/'runtime'/'studio.db').as_posix()}"
os.environ['WORKSPACE_DIR']=str(OUT/'runtime'/'workspaces')
sys.path.insert(0,str(ROOT/'backend'))
results={'parsed':0,'syntax_errors':[],'function_count':0,'inference':{}}
files=list((ROOT/'backend'/'app').rglob('*.py'))+list((ROOT/'backend'/'scripts').rglob('*.py'))
for f in files:
    try:
        tree=ast.parse(f.read_text(encoding='utf-8-sig'),filename=str(f))
        results['parsed']+=1
        results['function_count']+=sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) for n in ast.walk(tree))
    except Exception as e:
        results['syntax_errors'].append({'file':str(f.relative_to(ROOT)),'error':str(e)})
import app.ssl_compat
from app.models.blueprint import ArchitectureBlueprint
from app.services.inference_engine import infer_architecture
draft=json.loads((OUT/'draft.json').read_text(encoding='utf8'))
bp=ArchitectureBlueprint(**{k:draft[k] for k in ['serviceName','packageName','basePort','entities','userStories']})
for name,iface in [('optional_absent',None),('explicit_hexagonal_gradle',{'architecturePreference':'hexagonal','buildToolPreference':'gradle','requestVolume':'high'})]:
    case=bp.model_copy(update={})
    if iface is not None:
        from app.models.blueprint import InputInterface
        case.inputInterface=InputInterface(**iface)
    try:
        results['inference'][name]=infer_architecture(case).model_dump()
    except Exception as e:
        results['inference'][name]={'error':type(e).__name__,'message':str(e)}
(OUT/'static-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(results,ensure_ascii=True,indent=2))
