import React from 'react';
import { useStudio } from '../context/StudioContext';
import { StudioOverviewView } from './StudioOverviewView';
import { RequirementsView } from './RequirementsView';
import { ArchitectureView } from './ArchitectureView';
import { DomainModelsView } from './DomainModelsView';
import { SpecIngestionView } from './SpecIngestionView';
import { GenerationMonitorView } from './GenerationMonitorView';
import { CodeExplorerView } from './CodeExplorerView';
import { SecurityQualityView } from './SecurityQualityView';
import { DevOpsDeploymentView } from './DevOpsDeploymentView';
import { ExportPublishView } from './ExportPublishView';

export const WorkspaceRouter: React.FC = () => {
  const { activeTab } = useStudio();

  return (
    <>
      <div className={activeTab === 0 ? 'block' : 'hidden'}>
        <StudioOverviewView />
      </div>
      <div className={activeTab === 1 ? 'block' : 'hidden'}>
        <RequirementsView />
      </div>
      <div className={activeTab === 2 ? 'block' : 'hidden'}>
        <ArchitectureView />
      </div>
      <div className={activeTab === 3 ? 'block' : 'hidden'}>
        <DomainModelsView />
      </div>
      <div className={activeTab === 4 ? 'block' : 'hidden'}>
        <SpecIngestionView />
      </div>
      <div className={activeTab === 5 ? 'block' : 'hidden'}>
        <GenerationMonitorView />
      </div>
      <div className={activeTab === 6 ? 'block' : 'hidden'}>
        <CodeExplorerView />
      </div>
      <div className={activeTab === 7 ? 'block' : 'hidden'}>
        <SecurityQualityView />
      </div>
      <div className={activeTab === 8 ? 'block' : 'hidden'}>
        <DevOpsDeploymentView />
      </div>
      <div className={activeTab === 9 ? 'block' : 'hidden'}>
        <ExportPublishView />
      </div>
    </>
  );
};
