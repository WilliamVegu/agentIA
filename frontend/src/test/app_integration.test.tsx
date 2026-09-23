import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from '../App';
import { sessionService } from '../services/sessionService';
import { orchestratorService } from '../services/orchestratorService';
import { llmService } from '../services/llmService';
import { useStudio } from '../context/StudioContext';

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
        sessionId: 'sess-int-1',
        specId: 'spec-int-1',
        specName: 'customer-service',
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
      sessionId: 'sess-int-1',
      serviceName: 'customer-service',
      database: 'POSTGRESQL',
      totalStories: 3,
      totalEntities: 2,
      totalEndpoints: 4,
      testSuitesCount: 2,
      qualityGateStatus: 'PASS',
      qualityScore: 99,
      deploymentStatus: 'RUNNING',
      activePhase: 'COMPLETED',
      completionPercentage: 100,
    }),
    getLifecycle: vi.fn().mockResolvedValue({
      sessionId: 'sess-int-1',
      pipelineStatus: 'COMPLETED',
      completionPercentage: 100,
      phases: [],
    }),
  },
}));

const TabSwitcher: React.FC = () => {
  const { setActiveTab, activeTab } = useStudio();
  return (
    <div data-testid="tab-switcher">
      <span data-testid="active-tab-num">{activeTab}</span>
      {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((tabNum) => (
        <button
          key={tabNum}
          data-testid={`btn-switch-tab-${tabNum}`}
          onClick={() => setActiveTab(tabNum)}
        >
          Tab {tabNum}
        </button>
      ))}
    </div>
  );
};

describe('App End-to-End Integration & WorkspaceRouter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders LoginView when user is unauthenticated', () => {
    localStorage.setItem('agentia_user', 'null');

    render(<App />);

    expect(screen.getByText('Acceso Corporativo')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ingresar al Studio/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Acceso Rápido de Demostración/i })).toBeInTheDocument();
  });

  it('logs in and mounts AppLayout with Header, Sidebar, and WorkspaceRouter', async () => {
    render(<App />);

    // Initial state has default demo user, so it renders AppLayout directly
    await waitFor(() => {
      expect(screen.getByText('TCS Microservice Code Studio')).toBeInTheDocument();
      expect(screen.getByText('Nuevo Microservicio')).toBeInTheDocument();
      expect(screen.getByText('Rodrigo Mendoza')).toBeInTheDocument();
    });
  });

  it('navigates seamlessly across all 10 Workspace tabs', async () => {
    render(
      <App />
    );

    await waitFor(() => {
      expect(screen.getByText('TCS Microservice Code Studio')).toBeInTheDocument();
    });

    // Tab 1: Requisitos
    fireEvent.click(screen.getByTitle('1. Requisitos'));
    await waitFor(() => {
      expect(screen.getByText(/Fase 1: Transformación de Requerimientos a Historias BDD/i)).toBeInTheDocument();
    });

    // Tab 2: Arquitectura
    fireEvent.click(screen.getByTitle('2. Arquitectura'));
    await waitFor(() => {
      expect(screen.getByText(/Fase 2: Diseño Arquitectónico/i)).toBeInTheDocument();
    });

    // Tab 3: Modelos & SQL
    fireEvent.click(screen.getByTitle('3. Modelos & SQL'));
    await waitFor(() => {
      expect(screen.getByText(/Fase 3: Modelos de Dominio JPA/i)).toBeInTheDocument();
    });

    // Tab 4: Blueprints
    fireEvent.click(screen.getByTitle('4. Blueprints'));
    await waitFor(() => {
      expect(screen.getByText(/Fase 4: Ingesta y Validación Formal de Blueprints/i)).toBeInTheDocument();
    });

    // Tab 5: Monitor Live
    fireEvent.click(screen.getByTitle('5. Monitor Live'));
    await waitFor(() => {
      expect(screen.getByText(/Fase 5: Orquestación y Monitoreo en Vivo/i)).toBeInTheDocument();
    });

    // Tab 6: Código & Fix
    fireEvent.click(screen.getByTitle('6. Código & Fix'));
    await waitFor(() => {
      expect(screen.getByText(/Explorador de Fuentes Spring Boot 3/i)).toBeInTheDocument();
    });

    // Tab 7: Calidad SAST
    fireEvent.click(screen.getByTitle('7. Calidad SAST'));
    await waitFor(() => {
      expect(screen.getByText(/Auditoría SAST y Quality Gate/i)).toBeInTheDocument();
    });

    // Tab 8: DevOps & Demo
    fireEvent.click(screen.getByTitle('8. DevOps & Demo'));
    await waitFor(() => {
      expect(screen.getByText(/Fase 8: DevOps, Contenerización/i)).toBeInTheDocument();
    });

    // Tab 9: Entrega Git
    fireEvent.click(screen.getByTitle('9. Entrega Git'));
    await waitFor(() => {
      expect(screen.getByText(/Fase 9: Entrega Integral, Empaquetado ZIP/i)).toBeInTheDocument();
    });
  });

  it('toggles theme between light and dark from Header button', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('TCS Microservice Code Studio')).toBeInTheDocument();
    });

    const themeToggleBtn = screen.getByTitle(/Cambiar a Modo Oscuro|Cambiar a Modo Claro/i);
    fireEvent.click(themeToggleBtn);

    expect(localStorage.getItem('agentia_theme')).toBeTruthy();
  });

  it('logs out and returns to LoginView', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Rodrigo Mendoza')).toBeInTheDocument();
    });

    const logoutBtn = screen.getByTitle(/Cerrar sesión corporativa/i);
    fireEvent.click(logoutBtn);

    await waitFor(() => {
      expect(screen.getByText('Acceso Corporativo')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('usuario@tcs.com')).toBeInTheDocument();
    });
  });
});
