import React from 'react';
import {describe,it,expect,vi} from 'vitest';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {RequirementsView} from '../views/RequirementsView';
import {requirementsService} from '../services/requirementsService';
vi.mock('../context/StudioContext',()=>({useStudio:()=>({activeSessionId:'revision-ui',activeSession:{specName:'ledger-service'},currentDraft:null,setCurrentDraft:vi.fn(),reloadCurrentOverview:vi.fn(),setActiveTab:vi.fn()})}));
vi.mock('../context/LlmContext',()=>({useLlm:()=>({provider:'mock',apiKey:'',model:'offline'})}));
vi.mock('../services/requirementsService',()=>({requirementsService:{getSessionRequirements:vi.fn().mockResolvedValue({revisionId:'revision-2',configurationVersion:2,hasDraft:false}),prepareRegeneration:vi.fn().mockResolvedValue({backup:'before-regeneration.zip'})}}));
describe('explicit revision regeneration',()=>{
 it('requires confirmation and reports the actual backup',async()=>{
  render(<RequirementsView/>);
  const button=await screen.findByRole('button',{name:'Preparar regeneración con respaldo'});
  expect(button).toBeDisabled();
  expect(requirementsService.prepareRegeneration).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('checkbox',{name:/Confirmo la regeneración/}));
  fireEvent.click(button);
  await waitFor(()=>expect(requirementsService.prepareRegeneration).toHaveBeenCalledWith('revision-ui','revision-2'));
  expect(await screen.findByText(/Respaldo creado: before-regeneration.zip/)).toBeInTheDocument();
  expect(button).toBeDisabled();
 });
});
