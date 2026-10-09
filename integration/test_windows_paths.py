"""Real deep-file I/O in each studio, isolated DB, no production workspace access."""
import os,subprocess
from pathlib import Path
import pytest
from integration.reliability_smoke import ROOT,environment,python_for

@pytest.mark.parametrize('studio',['springboot','quarkus'])
def test_deep_source_atomic_io(studio,tmp_path):
    backend=ROOT/('systems/quarkus/backend' if studio=='quarkus' else 'backend')
    env=environment(tmp_path,backend)
    source="""
from pathlib import Path
from app.config import settings
from app.models.session import Base,engine,SessionLocal,GenerationSessionDB
from app.services.workspace_guard import atomic_write_workspace_file,resolve_workspace_file,io_path
Base.metadata.create_all(engine)
with SessionLocal() as db:
    db.add(GenerationSessionDB(id='deep-io',spec_id='deep',spec_name='Deep'));db.commit()
relative='/'.join(['package'+str(i)+'x'*24 for i in range(12)])+'/LedgerEntry.java'
path=atomic_write_workspace_file('deep-io',relative,'class LedgerEntry {}')
assert len(str(path))>400
assert io_path(resolve_workspace_file('deep-io',relative,require_exists=True)).read_text()=='class LedgerEntry {}'
atomic_write_workspace_file('deep-io',relative,'class LedgerEntry { int value; }')
assert io_path(path).read_text()=='class LedgerEntry { int value; }'
from integration.reliability_fixtures import ledger_draft
from app.orchestrator.stages.deterministic import scaffolder,domain,service,controller,test_synthesis
workspace=Path(settings.WORKSPACE_DIR)/'deep-io'/('/'.join(['nested'+str(i)+'x'*20 for i in range(7)]))
state={'blueprint':ledger_draft(),'workspace_path':str(workspace),'generated_files':{},'logs':[]}
for module in [scaffolder,domain,service,controller,test_synthesis]: state.update(module.emit(state))
assert len(state['generated_files'])>8
for name,content in state['generated_files'].items(): assert io_path(workspace/name).read_text(encoding='utf-8')==content
from app.services.platform_verification import inject_contract_test
io_path(workspace/'schema.sql').write_text('CREATE TABLE ledger_entries (entry_id UUID PRIMARY KEY);',encoding='utf-8')
contract=inject_contract_test(str(workspace))
assert contract is not None, 'Deep workspace must retain the platform persistence gate'
assert 'PlatformPersistenceContractTest' in io_path(workspace/contract).read_text(encoding='utf-8')
from app.services.draft_revision_service import save_revision,record_artifact
from app.models.reliability import ArtifactProvenance
revision=save_revision('deep-io',ledger_draft())
relative=(workspace/contract).relative_to(Path(settings.WORKSPACE_DIR)/'deep-io').as_posix()
record_artifact('deep-io',relative,'CODE_TESTS',revision['revisionId'])
with SessionLocal() as db:
    assert db.query(ArtifactProvenance).filter_by(session_id='deep-io',relative_path=relative,status='CURRENT').one().content_hash

"""
    result=subprocess.run([python_for(studio),'-c',source],env=env,cwd=ROOT,capture_output=True,text=True,timeout=45)
    assert result.returncode==0,result.stderr
