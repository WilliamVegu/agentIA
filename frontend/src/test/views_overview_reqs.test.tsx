import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from '../context/ThemeContext';
import { AuthProvider } from '../context/AuthContext';
import { LlmProvider } from '../context/LlmContext';
import { StudioProvider } from '../context/StudioContext';
import { StudioOverviewView } from '../views/StudioOverviewView';
import { SpecIngestionView } from '../views/SpecIngestionView';
import { RequirementsView } from '../views/RequirementsView';
import { sessionService } from '../services/sessionService';
import { specService } from '../services/specService';
import { requirementsService } from '../services/requirementsService';

vi.mock('../services/sessionService', () => ({
  sessionService: {
    listSessions: vi.fn().mockResolvedValue([
      {
        sessionId: 'sess-1',
        specId: 'spec-1',
        specName: 'order-service',
        status: 'COMPLETED',
        currentLifecyclePhase: 'VERIFIED',
        lifecycleMode: 'AUTONOMOUS',
        completionPercentage: 100,
        createdAt: '2026-09-23T00:00:00Z',
      },
    ]),
    quickStart: vi.fn(),
    getSession: vi.fn(),
  },
}));

vi.mock('../services/specService', () => ({
  specService: {
    submitJson: vi.fn(),
    uploadFile: vi.fn(),
  },
}));

vi.mock('../services/requirementsService', () => ({
  requirementsService: {
    transform: vi.fn(),
    refine: vi.fn(),
    getSessionRequirements: vi.fn().mockResolvedValue({
      specificationDraft: {
        entities: [],
        userStories: [],
      },
    }),
    saveSessionRequirements: vi.fn(),
    exportSpecMarkdown: vi.fn(),
  },
}));

vi.mock('../services/orchestratorService', () => ({
  orchestratorService: {
    getOverview: vi.fn().mockResolvedValue({
      sessionId: 'sess-1',
      serviceName: 'order-service',
      database: 'POSTGRESQL',
      totalStories: 3,
      totalEntities: 2,
      totalEndpoints: 4,
      testSuitesCount: 2,
      qualityGateStatus: 'PASS',
      qualityScore: 95,
      deploymentStatus: 'RUNNING',
      activePhase: 'COMPLETED',
      completionPercentage: 100,
    }),
    getLifecycle: vi.fn().mockResolvedValue({
      sessionId: 'sess-1',
      pipelineStatus: 'COMPLETED',
      completionPercentage: 100,
      phases: [],
    }),
    runPipeline: vi.fn(),
    transitionPhase: vi.fn(),
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

describe('Views: StudioOverview, SpecIngestion, Requirements', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe('StudioOverviewView', () => {
    it('disables Autonomous Generation button when service name and prompt are empty', () => {
      renderWithProviders(<StudioOverviewView />);

      const autoBtn = screen.getByRole('button', { name: /Crear y Ejecutar Auto-Pilot Completo/i });
      expect(autoBtn).toBeDisabled();
    });

    it('enables generation button when inputs are provided and triggers quickStart', async () => {
      vi.mocked(sessionService.quickStart).mockResolvedValueOnce({
        sessionId: 'new-sess-123',
        status: 'QUEUED',
      });

      renderWithProviders(<StudioOverviewView />);

      const nameInput = screen.getByPlaceholderText(/ej\. order-fulfillment-service/i);
      const promptInput = screen.getByPlaceholderText(/Describa el objetivo de negocio, entidades principales/i);
      const autoBtn = screen.getByRole('button', { name: /Crear y Ejecutar Auto-Pilot Completo/i });

      fireEvent.change(nameInput, { target: { value: 'billing-service' } });
      fireEvent.change(promptInput, { target: { value: 'Manage invoices and customer payments' } });

      expect(autoBtn).not.toBeDisabled();
      fireEvent.click(autoBtn);

      await waitFor(() => {
        expect(sessionService.quickStart).toHaveBeenCalledWith(
          expect.objectContaining({
            service_name: 'billing-service',
            prompt: 'Manage invoices and customer payments',
            auto_run: true,
          })
        );
      });
    });
  });

  describe('SpecIngestionView', () => {
    it('allows toggling between File Upload and JSON Editor tabs', () => {
      renderWithProviders(<SpecIngestionView />);

      expect(screen.getByText(/Seleccione o arrastre un archivo spec\.md/i)).toBeInTheDocument();

      const jsonTabBtn = screen.getByRole('button', { name: /Pegar Blueprint JSON/i });
      fireEvent.click(jsonTabBtn);

      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    it('submits valid JSON blueprint and shows success feedback', async () => {
      vi.mocked(specService.submitJson).mockResolvedValueOnce({
        specId: 'spec-json-1',
        serviceName: 'inventory-service',
        entitiesCount: 2,
        storiesCount: 3,
        endpointsCount: 4,
      });

      renderWithProviders(<SpecIngestionView />);

      // Switch to JSON tab
      fireEvent.click(screen.getByRole('button', { name: /Pegar Blueprint JSON/i }));

      const textarea = screen.getByRole('textbox');
      const submitBtn = screen.getByRole('button', { name: /Validar e Ingestar JSON Blueprint/i });

      fireEvent.change(textarea, {
        target: { value: JSON.stringify({ serviceName: 'inventory-service', entities: [] }) },
      });

      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(specService.submitJson).toHaveBeenCalled();
        expect(
          screen.getByText(/Blueprint JSON "inventory-service" validado/i)
        ).toBeInTheDocument();
      });
    });
  });

  describe('RequirementsView', () => {
    it('shows empty state card when there are no user stories in the session', async () => {
      renderWithProviders(<RequirementsView />);

      await waitFor(() => {
        expect(
          screen.getByText(/No hay historias de usuario en esta sesión/i)
        ).toBeInTheDocument();
      });
    });

    it('allows manually adding a user story using Crear Manualmente button', async () => {
      renderWithProviders(<RequirementsView />);

      await waitFor(() => {
        expect(screen.getByText(/No hay historias de usuario en esta sesión/i)).toBeInTheDocument();
      });

      const createManualBtn = screen.getByRole('button', { name: /Crear Manualmente/i });
      fireEvent.click(createManualBtn);

      await waitFor(() => {
        expect(screen.getByText(/Catálogo de Historias de Usuario BDD \(1\)/i)).toBeInTheDocument();
        expect(screen.getByText(/Nueva Funcionalidad de Negocio/i)).toBeInTheDocument();
      });
    });

    it('transforms prompt with AI to generate a minimum of 3 user stories', async () => {
      vi.mocked(requirementsService.transform).mockResolvedValueOnce({
        entities: ['Order', 'Customer', 'Product'],
        userStories: [
          {
            id: 'US-001',
            title: 'Crear nueva orden',
            role: 'Cliente',
            feature: 'Registrar compra',
            benefit: 'Adquirir productos',
            scenarios: [{ given: 'Carrito con items', when: 'Confirma orden', then: 'Orden creada 201' }],
          },
          {
            id: 'US-002',
            title: 'Consultar estado',
            role: 'Cliente',
            feature: 'Rastrear envío',
            benefit: 'Conocer fecha',
            scenarios: [{ given: 'Orden existente', when: 'Consulta ID', then: 'Retorna estado 200' }],
          },
          {
            id: 'US-003',
            title: 'Cancelar orden',
            role: 'Administrador',
            feature: 'Anular orden no despachada',
            benefit: 'Reintegrar stock',
            scenarios: [{ given: 'Orden pendiente', when: 'Cancela orden', then: 'Stock repuesto 200' }],
          },
        ],
      });

      renderWithProviders(<RequirementsView />);

      const promptArea = screen.getByPlaceholderText(
        /Describa el comportamiento deseado, entidades de negocio/i
      );
      fireEvent.change(promptArea, {
        target: { value: 'Sistema de compras y cancelaciones de pedidos' },
      });

      const decomposeBtn = screen.getByRole('button', {
        name: /Descomponer con IA \(Mínimo 3 Historias\)/i,
      });
      fireEvent.click(decomposeBtn);

      await waitFor(() => {
        expect(requirementsService.transform).toHaveBeenCalled();
        expect(screen.getByText(/Catálogo de Historias de Usuario BDD \(3\)/i)).toBeInTheDocument();
        expect(screen.getByText(/Crear nueva orden/i)).toBeInTheDocument();
        expect(screen.getByText(/Consultar estado/i)).toBeInTheDocument();
        expect(screen.getByText(/Cancelar orden/i)).toBeInTheDocument();
      });
    });
  });
});
