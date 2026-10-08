import React from 'react';
import {describe,it,expect,vi,beforeEach} from 'vitest';
import {render,screen,waitFor} from '@testing-library/react';
import {SecurityQualityView} from '../views/SecurityQualityView';
import {securityService} from '../services/securityService';
vi.mock('../context/StudioContext',()=>({useStudio:()=>({activeSessionId:'reliability-ui',reloadCurrentOverview:vi.fn(),setActiveTab:vi.fn()})}));
vi.mock('../services/securityService',()=>({securityService:{getAuditReport:vi.fn(),applySurgicalRemediation:vi.fn()}}));
vi.mock('../services/llmService',()=>({llmService:{checkHealth:vi.fn().mockResolvedValue({dockerEnabled:true})}}));
describe('real audit metrics',()=>{
 it('preserves zero counts and a null score',async()=>{
  vi.mocked(securityService.getAuditReport).mockResolvedValue({qualityGate:{status:'BLOCKED',score:null,canExport:false,canDeploy:false,summaryMessage:'No source code was audited.'},metrics:{totalLinesOfCode:0,totalMethodsAudited:0,testAssertionDensity:0},vulnerabilities:[],violations:[]} as any);
  render(<SecurityQualityView/>);
  await waitFor(()=>expect(screen.getByText('No source code was audited.')).toBeInTheDocument());
  expect(screen.queryByText('284')).not.toBeInTheDocument();
  expect(screen.queryByText('2.2 / test')).not.toBeInTheDocument();
  expect(screen.getAllByText(/Sin evaluar/).length).toBeGreaterThan(0);
 });
});
