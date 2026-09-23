import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from '../context/ThemeContext';
import { AuthProvider } from '../context/AuthContext';
import { LlmProvider } from '../context/LlmContext';
import { StudioProvider, useStudio } from '../context/StudioContext';
import { ArchitectureView } from '../views/ArchitectureView';
import { DomainModelsView } from '../views/DomainModelsView';
import { architectureService } from '../services/architectureService';
import { modelsService } from '../services/modelsService';
import { requirementsService } from '../services/requirementsService';
import { sessionService } from '../services/sessionService';

vi.mock('../services/sessionService', () => ({
  sessionService: {
    listSessions: vi.fn().mockResolvedValue([
      {
        sessionId: 'sess-arch-1',
        specId: 'spec-1',
        specName: 'payment-service',
        status: 'RUNNING',
        currentLifecyclePhase: 'ARCHITECTURE',
        lifecycleMode: 'AUTONOMOUS',
        completionPercentage: 40,
        createdAt: '2026-09-23T00:00:00Z',
      },
    ]),
    quickStart: vi.fn(),
    getSession: vi.fn(),
  },
}));

vi.mock('../services/requirementsService', () => ({
  requirementsService: {
    getSessionRequirements: vi.fn().mockResolvedValue({
      hasDraft: true,
      draft: {
        serviceName: 'payment-service',
        packageName: 'com.tcs.payment',
        basePort: 8080,
        entities: [{ name: 'Payment', tableName: 'payments' }],
        userStories: [{ id: 'US-001', title: 'Process card payment' }],
      },
    }),
  },
}));

vi.mock('../services/architectureService', () => ({
  architectureService: {
    design: vi.fn(),
    refine: vi.fn(),
  },
}));

vi.mock('../services/modelsService', () => ({
  modelsService: {
    generate: vi.fn(),
    refine: vi.fn(),
  },
}));

vi.mock('../services/orchestratorService', () => ({
  orchestratorService: {
    getOverview: vi.fn().mockResolvedValue({
      sessionId: 'sess-arch-1',
      serviceName: 'payment-service',
      database: 'POSTGRESQL',
      totalStories: 2,
      totalEntities: 1,
      totalEndpoints: 3,
      testSuitesCount: 1,
      qualityGateStatus: 'PASS',
      qualityScore: 90,
      deploymentStatus: 'STOPPED',
      activePhase: 'ARCHITECTURE',
      completionPercentage: 40,
    }),
    getLifecycle: vi.fn().mockResolvedValue({
      sessionId: 'sess-arch-1',
      pipelineStatus: 'RUNNING',
      completionPercentage: 40,
      phases: [],
    }),
  },
}));

const renderWithProviders = (ui: React.ReactNode) => {
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

describe('Views: ArchitectureView & DomainModelsView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe('ArchitectureView', () => {
    it('renders empty state when architecture has not been synthesized', async () => {
      renderWithProviders(<ArchitectureView />);

      await waitFor(() => {
        expect(
          screen.getByText(/Arquitectura no sintetizada para este microservicio/i)
        ).toBeInTheDocument();
      });
    });

    it('synthesizes 4-layer architecture with IA button click', async () => {
      vi.mocked(architectureService.design).mockResolvedValueOnce({
        serviceName: 'payment-service',
        mermaidDiagram: 'graph TD\n  Client --> Controller\n  Controller --> Service\n  Service --> Repository',
        components: [
          { name: 'PaymentController', layer: 'controller', stereotype: '@RestController', description: 'REST Endpoints' },
          { name: 'PaymentService', layer: 'service', stereotype: '@Service', description: 'Business Logic' },
          { name: 'PaymentRepository', layer: 'repository', stereotype: '@Repository', description: 'JPA Data' },
          { name: 'Payment', layer: 'model', stereotype: '@Entity', description: 'JPA Entity' },
        ],
      });

      renderWithProviders(<ArchitectureView />);

      await waitFor(() => {
        expect(
          screen.getByText(/Arquitectura no sintetizada para este microservicio/i)
        ).toBeInTheDocument();
      });

      const synthBtn = screen.getByRole('button', { name: /Sintetizar Arquitectura con IA/i });
      fireEvent.click(synthBtn);

      await waitFor(() => {
        expect(architectureService.design).toHaveBeenCalled();
        expect(screen.getByText(/Capa Controlador \(REST \/ HTTP\)/i)).toBeInTheDocument();
        expect(screen.getByText(/Capa Servicio \(Lógica de Negocio\)/i)).toBeInTheDocument();
        expect(screen.getByText(/Capa Repositorio \(Persistencia Spring Data JPA\)/i)).toBeInTheDocument();
        expect(screen.getByText(/Capa Dominio & Modelos/i)).toBeInTheDocument();
      });
    });

    it('opens refine drawer when Refinar con IA is clicked on active design', async () => {
      const StatePreloader = () => {
        const { setArchitectureDesign } = useStudio();
        React.useEffect(() => {
          setArchitectureDesign({
            serviceName: 'payment-service',
            mermaidDiagram: 'graph TD\n  A-->B',
            components: [
              { name: 'PaymentController', layer: 'controller', stereotype: '@RestController', description: 'REST' },
            ],
          });
        }, [setArchitectureDesign]);
        return <ArchitectureView />;
      };

      renderWithProviders(<StatePreloader />);

      await waitFor(() => {
        expect(screen.getByText(/Capa Controlador \(REST \/ HTTP\)/i)).toBeInTheDocument();
      });

      const refineBtn = screen.getByRole('button', { name: /Refinar con IA/i });
      fireEvent.click(refineBtn);

      await waitFor(() => {
        expect(screen.getByText(/Asistente de Refinamiento Arquitectónico con IA/i)).toBeInTheDocument();
      });
    });
  });

  describe('DomainModelsView', () => {
    it('renders empty state when models have not been synthesized', async () => {
      renderWithProviders(<DomainModelsView />);

      await waitFor(() => {
        expect(
          screen.getByText(/Modelos de dominio y SQL relacional no sintetizados/i)
        ).toBeInTheDocument();
      });
    });

    it('synthesizes models and SQL with IA and displays ERD, JPA entities, and DDL', async () => {
      vi.mocked(modelsService.generate).mockResolvedValueOnce({
        mermaidErDiagram: 'erDiagram\n  PAYMENT ||--o{ REFUND : has',
        sqlSchema: {
          schemaDdl: 'CREATE TABLE payments (id BIGSERIAL PRIMARY KEY, amount NUMERIC(12,2) NOT NULL);',
          seedDml: "INSERT INTO payments (amount) VALUES (150.00);",
        },
        entities: [
          {
            name: 'Payment',
            tableName: 'payments',
            attributes: [
              { name: 'id', type: 'Long', isPrimaryKey: true, nullable: false },
              { name: 'amount', type: 'BigDecimal', nullable: false },
            ],
          },
        ],
        javaEntityClasses: {
          Payment: '@Entity public class Payment { private Long id; private BigDecimal amount; }',
        },
      });

      renderWithProviders(<DomainModelsView />);

      await waitFor(() => {
        expect(
          screen.getByText(/Modelos de dominio y SQL relacional no sintetizados/i)
        ).toBeInTheDocument();
      });

      const synthBtn = screen.getByRole('button', { name: /Sintetizar Modelos & SQL con IA/i });
      fireEvent.click(synthBtn);

      await waitFor(() => {
        expect(modelsService.generate).toHaveBeenCalled();
        expect(
          screen.getByText(/1\. Diagrama Entidad-Relación Visual \(Mermaid erDiagram\)/i)
        ).toBeInTheDocument();
        expect(
          screen.getByText(/2\. Entidades de Dominio JPA & Atributos Tipados/i)
        ).toBeInTheDocument();
        expect(
          screen.getByText(/3\. Scripts SQL Relacionales Sincronizados/i)
        ).toBeInTheDocument();
      });
    });
  });
});

