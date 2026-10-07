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

  // Keyed, not positional: reordering the tab row cannot change which view renders.
  switch (activeTab) {
    case 'blueprints':
      return <SpecIngestionView />;
    case 'overview':
      return <StudioOverviewView />;
    case 'requirements':
      return <RequirementsView />;
    case 'architecture':
      return <ArchitectureView />;
    case 'models':
      return <DomainModelsView />;
    case 'code':
      return <CodeExplorerView />;
    case 'quality':
      return <SecurityQualityView />;
    case 'devops':
      return <DevOpsDeploymentView />;
    case 'delivery':
      return <ExportPublishView />;
    case 'monitor':
      return <GenerationMonitorView />;
    default:
      return <StudioOverviewView />;
  }
};