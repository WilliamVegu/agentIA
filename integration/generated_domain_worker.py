"""Generate an isolated native Java fixture, with no LLM provider calls."""
import argparse
import json
from pathlib import Path
from integration.reliability_fixtures import ledger_draft, relational_ledger_draft, assert_isolated
from app.orchestrator.stages.deterministic import scaffolder,domain,service,controller,test_synthesis
from app.services.model_sql_service import schema_sql_from_draft
from app.models.requirements import SpecificationDraft


def generate(workspace, build_tool, database, extended=False):
    workspace=assert_isolated(Path(workspace));workspace.mkdir(parents=True,exist_ok=True)
    from app.services.llm_factory import LLMFactory
    def forbidden(*args,**kwargs): raise AssertionError('Live provider calls are forbidden in generated-domain fixtures')
    LLMFactory.get_llm=forbidden
    blueprint=relational_ledger_draft() if extended else ledger_draft();blueprint['databaseMode']=database
    blueprint['inputInterface']['buildToolPreference']=build_tool
    state={'blueprint':blueprint,'workspace_path':str(workspace),'generated_files':{},'logs':[]}
    for module in [scaffolder,domain,service,controller,test_synthesis]:
        state.update(module.emit(state))
    (workspace/'schema.sql').write_text(schema_sql_from_draft(SpecificationDraft.model_validate(blueprint),database),encoding='utf-8')
    (workspace/'fixture-input.json').write_text(json.dumps(blueprint,indent=2,ensure_ascii=False),encoding='utf-8')
    return {'workspace':str(workspace),'files':len(state['generated_files']),'buildTool':build_tool,'databaseEngine':database,'logs':state['logs']}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',required=True)
    parser.add_argument('--build-tool',choices=['maven','gradle'],required=True)
    parser.add_argument('--database',choices=['H2','POSTGRESQL','MYSQL'],required=True)
    parser.add_argument('--extended',action='store_true')
    args=parser.parse_args();print(json.dumps(generate(args.workspace,args.build_tool,args.database,args.extended)))
