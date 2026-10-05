import React from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EcosystemProvider, useEcosystem } from '../context/EcosystemContext';
import { UnifiedLauncherHeroView } from '../views/launcher/UnifiedLauncherHeroView';
import { Header } from '../components/layout/Header';
import { ThemeProvider } from '../context/ThemeContext';
import { AuthProvider } from '../context/AuthContext';
import { LlmProvider } from '../context/LlmContext';

const TestApp: React.FC = () => {
  const { activeEcosystem, goToLauncher } = useEcosystem();

  return (
    <div>
      <Header />
      <div data-testid="current-ecosystem">{activeEcosystem}</div>
      {activeEcosystem === 'launcher' && <UnifiedLauncherHeroView />}
      {activeEcosystem === 'spring' && (
        <div data-testid="spring-workspace">
          <h1>Spring Boot Workspace Content</h1>
          <button onClick={goToLauncher}>Volver al Launcher</button>
        </div>
      )}
      {activeEcosystem === 'quarkus' && (
        <div data-testid="quarkus-workspace">
          <h1>Quarkus Factory Workspace Content</h1>
          <button onClick={goToLauncher}>Volver al Launcher</button>
        </div>
      )}
    </div>
  );
};

const renderWithProviders = () => {
  return render(
    <ThemeProvider>
      <AuthProvider>
        <LlmProvider>
          <EcosystemProvider>
            <TestApp />
          </EcosystemProvider>
        </LlmProvider>
      </AuthProvider>
    </ThemeProvider>
  );
};

describe('Unified Platform Launcher & Ecosystem Switcher', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders launcher view with cards for Spring Boot and Quarkus', () => {
    renderWithProviders();

    expect(screen.getByText(/Elige tu Ecosistema de Desarrollo/i)).toBeInTheDocument();
    expect(screen.getByText(/Spring Boot Studio/i)).toBeInTheDocument();
    expect(screen.getByText(/Fábrica Quarkus 3.x/i)).toBeInTheDocument();
    expect(screen.getByText(/Entrar al Estudio Spring Boot/i)).toBeInTheDocument();
    expect(screen.getByText(/Entrar a la Fábrica Quarkus/i)).toBeInTheDocument();
  });

  it('navigates to Spring Boot workspace when clicking Spring Boot button', () => {
    renderWithProviders();

    const springBtn = screen.getByText(/Entrar al Estudio Spring Boot/i);
    fireEvent.click(springBtn);

    expect(screen.getByTestId('spring-workspace')).toBeInTheDocument();
    expect(screen.getByTestId('current-ecosystem')).toHaveTextContent('spring');
  });

  it('navigates to Quarkus workspace when clicking Quarkus button', () => {
    renderWithProviders();

    const quarkusBtn = screen.getByText(/Entrar a la Fábrica Quarkus/i);
    fireEvent.click(quarkusBtn);

    expect(screen.getByTestId('quarkus-workspace')).toBeInTheDocument();
    expect(screen.getByTestId('current-ecosystem')).toHaveTextContent('quarkus');
  });

  it('allows returning to launcher from header switcher button', () => {
    renderWithProviders();

    // 1. Enter Quarkus
    const quarkusBtn = screen.getByText(/Entrar a la Fábrica Quarkus/i);
    fireEvent.click(quarkusBtn);
    expect(screen.getByTestId('quarkus-workspace')).toBeInTheDocument();

    // 2. Click Header Switcher ("Cambiar")
    const switchBtns = screen.getAllByRole('button', { name: /Cambiar/i });
    fireEvent.click(switchBtns[0]);

    // 3. Should be back in launcher
    expect(screen.getByTestId('current-ecosystem')).toHaveTextContent('launcher');
    expect(screen.getByText(/Elige tu Ecosistema de Desarrollo/i)).toBeInTheDocument();
  });
});
