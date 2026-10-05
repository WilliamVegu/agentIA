import React, { createContext, useContext, useState, useEffect } from 'react';

export type EcosystemType = 'launcher' | 'spring' | 'quarkus';

interface EcosystemContextType {
  activeEcosystem: EcosystemType;
  setEcosystem: (eco: EcosystemType) => void;
  goToLauncher: () => void;
  goToSpring: () => void;
  goToQuarkus: () => void;
}

const STORAGE_KEY = 'agentia_active_ecosystem';

const EcosystemContext = createContext<EcosystemContextType | undefined>(undefined);

export const EcosystemProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeEcosystem, setActiveEcosystemState] = useState<EcosystemType>(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'spring' || saved === 'quarkus' || saved === 'launcher') {
      return saved;
    }
    return 'launcher';
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, activeEcosystem);
  }, [activeEcosystem]);

  const setEcosystem = (eco: EcosystemType) => {
    setActiveEcosystemState(eco);
  };

  const goToLauncher = () => {
    setActiveEcosystemState('launcher');
  };

  const goToSpring = () => {
    setActiveEcosystemState('spring');
  };

  const goToQuarkus = () => {
    setActiveEcosystemState('quarkus');
  };

  return (
    <EcosystemContext.Provider
      value={{
        activeEcosystem,
        setEcosystem,
        goToLauncher,
        goToSpring,
        goToQuarkus,
      }}
    >
      {children}
    </EcosystemContext.Provider>
  );
};

export const useEcosystem = (): EcosystemContextType => {
  const context = useContext(EcosystemContext);
  if (!context) {
    throw new Error('useEcosystem must be used within an EcosystemProvider');
  }
  return context;
};
