import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from '../context/ThemeContext';
import { AuthProvider } from '../context/AuthContext';
import { LlmProvider } from '../context/LlmContext';
import { StudioProvider, useStudio } from '../context/StudioContext';
import { Header } from '../components/layout/Header';
import { Sidebar } from '../components/layout/Sidebar';
import { LifecycleStepper } from '../components/layout/LifecycleStepper';
import { ErrorBoundary } from '../components/common/ErrorBoundary';
import { sessionService } from '../services/sessionService';
import { llmService } from '../services/llmService';

vi.mock('../services/llmService', () => ({
  llmService: {
    checkHealth: vi.fn().mockResolvedValue({
      status: 'UP',
      timestamp: new Date().toISOString(),
      app: 'AgentIA API',
      version: '1.0.0',
    }),
    verifyConnection: vi.fn(),
  },
}));

vi.mock('../services/sessionService', () => ({
  sessionService: {
    listSessions: vi.fn().mockResolvedValue([
      {
        sessionId: 'sess-test-001',
        specId: 'spec-001',
        specName: 'payment-service',
        status: 'COMPLETED',
        currentLifecyclePhase: 'VERIFIED',
        lifecycleMode: 'AUTONOMOUS',
        completionPercentage: 100,
        createdAt: '2026-09-23T00:00:00Z',
      },
    ]),
    getSession: vi.fn(),
    quickStart: vi.fn(),
  },
}));

vi.mock('../services/orchestratorService', () => ({
  orchestratorService: {
    getOverview: vi.fn().mockResolvedValue({
      sessionId: 'sess-test-001',
      serviceName: 'payment-service',
      database: 'POSTGRESQL',
      totalStories: 4,
      totalEntities: 2,
      totalEndpoints: 5,
      testSuitesCount: 2,
      qualityGateStatus: 'PASS',
      qualityScore: 98,
      deploymentStatus: 'RUNNING',
      activePhase: 'COMPLETED',
      completionPercentage: 100,
    }),
    getLifecycle: vi.fn().mockResolvedValue({
      sessionId: 'sess-test-001',
      pipelineStatus: 'COMPLETED',
      completionPercentage: 100,
      phases: [],
    }),
  },
}));

const renderWithAllProviders = (ui: React.ReactNode) => {
  return render(
    <ThemeProvider>
      <AuthProvider>
        <LlmProvider>
          <StudioProvider>
            {ui}
          </StudioProvider>
        </LlmProvider>
      </AuthProvider>
    </ThemeProvider>
  );
};

describe('Layout Components & ErrorBoundary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders Header with branding, backend health status, and user profile', async () => {
    const handleOpenSettings = vi.fn();

    renderWithAllProviders(<Header onOpenSettings={handleOpenSettings} />);

    expect(screen.getByText('TCS Microservice Code Studio')).toBeInTheDocument();
    expect(screen.getByText('LangGraph Enterprise Orchestrator')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Rodrigo Mendoza')).toBeInTheDocument();
    });

    const settingsBtn = screen.getByTitle(/Configuración de Motor LLM/i);
    fireEvent.click(settingsBtn);
    expect(handleOpenSettings).toHaveBeenCalledTimes(1);
  });

  it('renders Sidebar with logo, New Microservice button, and session list item', async () => {
    renderWithAllProviders(<Sidebar />);

    expect(screen.getByText('Nuevo Microservicio')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('payment-service')).toBeInTheDocument();
      expect(screen.getByText('100%')).toBeInTheDocument();
    });
  });

  it('renders LifecycleStepper for the active session with phases', async () => {
    renderWithAllProviders(<LifecycleStepper />);

    await waitFor(() => {
      expect(screen.getByText('1. Requisitos')).toBeInTheDocument();
      expect(screen.getByText('3. Arquitectura')).toBeInTheDocument();
      expect(screen.getByText('4. Modelos & DDL')).toBeInTheDocument();
      expect(screen.getByText('5. Código & Tests')).toBeInTheDocument();
      expect(screen.getByText('6. Calidad SAST')).toBeInTheDocument();
      expect(screen.getByText('7. DevOps Local')).toBeInTheDocument();
    });
  });

  it('ErrorBoundary renders children when there is no error', () => {
    render(
      <ErrorBoundary fallbackTitle="Error al cargar">
        <div data-testid="child-content">Normal Content</div>
      </ErrorBoundary>
    );

    expect(screen.getByTestId('child-content')).toHaveTextContent('Normal Content');
  });

  it('ErrorBoundary catches rendering errors and displays fallback UI with retry button', () => {
    const BadComponent = () => {
      throw new Error('Test Crash Failure');
    };

    // Suppress console.error in this test to avoid noisy logs
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary fallbackTitle="Error crítico en el módulo">
        <BadComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText('Error crítico en el módulo')).toBeInTheDocument();
    expect(screen.getByText('Test Crash Failure')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reintentar/i })).toBeInTheDocument();

    consoleSpy.mockRestore();
  });
});
