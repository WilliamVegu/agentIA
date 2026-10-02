import React from 'react';
import { useQuarkus } from '../../context/QuarkusContext';
import { QuarkusStepperNav } from './QuarkusStepperNav';
import { Step1OrderInput } from './Step1OrderInput';
import { Step3ContractControl1 } from './Step3ContractControl1';
import { Step4ArchitectureArchetype } from './Step4ArchitectureArchetype';
import { Step5ConstructionTracking } from './Step5ConstructionTracking';
import { Step6Documentation } from './Step6Documentation';
import { Step7RevisionControl2 } from './Step7RevisionControl2';
import { Step8DevOpsDelivery } from './Step8DevOpsDelivery';

export const QuarkusFactoryStudioView: React.FC = () => {
  const { activeStep } = useQuarkus();

  const renderActiveStep = () => {
    switch (activeStep) {
      case 0:
        return <Step1OrderInput />;
      case 1:
        return <Step3ContractControl1 />;
      case 2:
        return <Step4ArchitectureArchetype />;
      case 3:
        return <Step5ConstructionTracking />;
      case 4:
        return <Step6Documentation />;
      case 5:
        return <Step7RevisionControl2 />;
      case 6:
        return <Step8DevOpsDelivery />;
      default:
        return <Step1OrderInput />;
    }
  };

  return (
    <div className="space-y-4">
      {/* Barra de progreso de los pasos limpios, estado y tokens */}
      <QuarkusStepperNav />

      {/* Contenido dinámico del paso activo */}
      <div className="pb-10">
        {renderActiveStep()}
      </div>
    </div>
  );
};
