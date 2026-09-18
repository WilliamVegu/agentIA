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

  switch (activeTab) {
    case 0:
      return <StudioOverviewView />;
    case 1:
      return <RequirementsView />;
    case 2:
      return <ArchitectureView />;
    case 3:
      return <DomainModelsView />;
    case 4:
      return <SpecIngestionView />;
    case 5:
      return <GenerationMonitorView />;
    case 6:
      return <CodeExplorerView />;
    case 7:
      return <SecurityQualityView />;
    case 8:
      return <DevOpsDeploymentView />;
    case 9:
      return <ExportPublishView />;
    default:
      return <StudioOverviewView />;
  }
};
