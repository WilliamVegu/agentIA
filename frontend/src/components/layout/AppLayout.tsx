import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { LifecycleStepper } from './LifecycleStepper';
import { ResponsiveTabGrid } from '../common/ResponsiveTabGrid';
import { SettingsDrawer } from './SettingsDrawer';
import { useStudio } from '../../context/StudioContext';
import { useEcosystem } from '../../context/EcosystemContext';

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const { activeSessionId } = useStudio();
  const { activeEcosystem } = useEcosystem();

  const isLauncher = activeEcosystem === 'launcher';
  const isSpring = activeEcosystem === 'spring';

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 dark:bg-slate-950 transition-colors">
      {/* Sidebar: shown only when inside a studio workspace */}
      {!isLauncher && <Sidebar />}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header (z-30) */}
        <Header onOpenSettings={() => setIsSettingsOpen(true)} />

        {/* Workspace Canvas */}
        <main className={`flex-1 overflow-y-auto ${isLauncher ? 'p-4 sm:p-8' : 'p-4 sm:p-6 space-y-4'}`}>
          {/* Persistent Lifecycle Stepper when in Spring Boot and active session is selected */}
          {isSpring && activeSessionId && <LifecycleStepper />}

          {/* Zero-Scroll Horizontal 10-Tab Navigation Grid (Spring Boot only) */}
          {isSpring && <ResponsiveTabGrid />}

          {/* Tab View Canvas */}
          <div className={isSpring ? 'pt-2' : ''}>
            {children}
          </div>
        </main>
      </div>

      {/* Slide-over Settings Drawer (z-[100]) */}
      <SettingsDrawer
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
};
