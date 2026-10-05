import React from 'react';
import { useEcosystem } from '../context/EcosystemContext';
import { useStudio } from '../context/StudioContext';
import { UnifiedLauncherHeroView } from './launcher/UnifiedLauncherHeroView';
import { QuarkusFactoryStudioView } from './quarkus/QuarkusFactoryStudioView';
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
  const { activeEcosystem } = useEcosystem();
  const { activeTab } = useStudio();

  // 1. Initial Launchpad / Selector Screen
  if (activeEcosystem === 'launcher') {
    return <UnifiedLauncherHeroView />;
  }

  // 2. Quarkus 3.x Factory Studio Flow
  if (activeEcosystem === 'quarkus') {
    return <QuarkusFactoryStudioView />;
  }

  // 3. Spring Boot Microservice Studio Flow
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