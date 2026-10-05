import React from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LlmProvider } from './context/LlmContext';
import { StudioProvider } from './context/StudioContext';
import { QuarkusProvider } from './context/QuarkusContext';
import { EcosystemProvider } from './context/EcosystemContext';
import { LoginView } from './views/LoginView';
import { AppLayout } from './components/layout/AppLayout';
import { WorkspaceRouter } from './views/WorkspaceRouter';
import { ErrorBoundary } from './components/common/ErrorBoundary';

const AppContent: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center text-slate-500 font-medium" role="status">Iniciando plataforma unificada…</div>;
  }

  if (!isAuthenticated) {
    return <LoginView />;
  }

  return (
    <EcosystemProvider>
      <StudioProvider>
        <QuarkusProvider>
          <AppLayout>
            <ErrorBoundary fallbackTitle="Error al renderizar el módulo del Workspace">
              <WorkspaceRouter />
            </ErrorBoundary>
          </AppLayout>
        </QuarkusProvider>
      </StudioProvider>
    </EcosystemProvider>
  );
};

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <LlmProvider>
          <AppContent />
        </LlmProvider>
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
