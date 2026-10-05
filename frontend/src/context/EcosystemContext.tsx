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
    // 1. Explicit target set by login or MVP buttons
    const pending = sessionStorage.getItem('agentia_target_ecosystem');
    if (pending === 'spring' || pending === 'quarkus' || pending === 'launcher') {
      sessionStorage.removeItem('agentia_target_ecosystem');
      localStorage.setItem(STORAGE_KEY, pending);
      return pending;
    }

    // 2. Saved preference in localStorage
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'spring' || saved === 'quarkus' || saved === 'launcher') {
      return saved;
    }

    // 3. By default always show the launcher/hub to allow choosing
    return 'launcher';
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, activeEcosystem);
  }, [activeEcosystem]);

  useEffect(() => {
    const handleReset = () => {
      localStorage.setItem(STORAGE_KEY, 'launcher');
      sessionStorage.removeItem('agentia_target_ecosystem');
      setActiveEcosystemState('launcher');
    };

    window.addEventListener('agentia:logout', handleReset);
    window.addEventListener('agentia:reset_ecosystem', handleReset);
    return () => {
      window.removeEventListener('agentia:logout', handleReset);
      window.removeEventListener('agentia:reset_ecosystem', handleReset);
    };
  }, []);

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
