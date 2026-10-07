import React from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LlmProvider } from './context/LlmContext';
import { StudioProvider } from './context/StudioContext';
import { LoginView } from './views/LoginView';
import { AppLayout } from './components/layout/AppLayout';
import { WorkspaceRouter } from './views/WorkspaceRouter';
import { ErrorBoundary } from './components/common/ErrorBoundary';

const AppContent: React.FC = () => {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginView />;
  }

  return (
    <StudioProvider>
      <AppLayout>
        <ErrorBoundary fallbackTitle="Error al renderizar el módulo del Workspace">
          <WorkspaceRouter />
        </ErrorBoundary>
      </AppLayout>
    </StudioProvider>
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
