import {beforeEach,describe,expect,it,vi} from 'vitest';
import apiClient from '../services/apiClient';
import {requirementsService} from '../services/requirementsService';
import {sessionService} from '../services/sessionService';
import {testsService} from '../services/testsService';
import {securityService} from '../services/securityService';

describe('canonical API contracts',()=>{
 beforeEach(()=>vi.restoreAllMocks());
 it('sends the configured engine and preserves conflicting aliases for server rejection',async()=>{
  const post=vi.spyOn(apiClient,'post').mockResolvedValue({data:{}});
  await sessionService.quickStart({service_name:'ledger',databaseEngine:'MYSQL',database:'H2'});
  expect(post).toHaveBeenCalledWith('/sessions/quick-start',expect.objectContaining({databaseEngine:'MYSQL',database:'H2'}));
 });
 it('carries revision and configuration CAS versions through save and approval',async()=>{
  const post=vi.spyOn(apiClient,'post').mockResolvedValue({data:{}});
  await requirementsService.saveSessionRequirements('s',{entities:[]},'r',7);
  expect(post).toHaveBeenLastCalledWith('/requirements/sessions/s/save',{entities:[]},{params:{expectedRevisionId:'r',expectedVersion:7}});
  await requirementsService.approveSessionRequirements('s','r',7);
  expect(post).toHaveBeenLastCalledWith('/requirements/sessions/s/approve',null,{params:{revisionId:'r',expectedVersion:7}});
 });
 it('propagates 409 conflicts without fabricating a successful revision',async()=>{
  vi.spyOn(apiClient,'post').mockRejectedValue({response:{status:409}});
  await expect(requirementsService.approveSessionRequirements('s','stale',1)).rejects.toMatchObject({response:{status:409}});
 });
 it('uses canonical guidanceHint with code and exposes backend 422 for hint-only requests',async()=>{
  const post=vi.spyOn(apiClient,'post').mockResolvedValue({data:{diagnosticsResolved:false}});
  await testsService.submitManualRepair('s','src/A.java','class A {}','Check identifier');
  expect(post).toHaveBeenLastCalledWith('/sessions/s/manual-repair',expect.objectContaining({modifiedCode:'class A {}',guidanceHint:'Check identifier'}));
  post.mockRejectedValueOnce({response:{status:422}});
  await expect(testsService.submitManualRepair('s','src/A.java',undefined,'Hint')).rejects.toMatchObject({response:{status:422}});
 });
 it('preserves real zero metrics and the absence of an audit score',async()=>{
  const data={qualityGate:{status:'BLOCKED',score:null,canExport:false},metrics:{totalLinesOfCode:0}};
  vi.spyOn(apiClient,'get').mockResolvedValue({data});
  expect(await securityService.getAuditReport('s')).toEqual(data);
 });
});
