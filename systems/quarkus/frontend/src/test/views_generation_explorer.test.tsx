import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from '../context/ThemeContext';
import { AuthProvider } from '../context/AuthContext';
import { LlmProvider } from '../context/LlmContext';
import { StudioProvider } from '../context/StudioContext';
import { GenerationMonitorView } from '../views/GenerationMonitorView';
import { CodeExplorerView } from '../views/CodeExplorerView';
import { exportService } from '../services/exportService';
import { testsService } from '../services/testsService';
import { sessionService } from '../services/sessionService';

vi.mock('../services/sessionService', () => ({
  sessionService: {
    listSessions: vi.fn().mockResolvedValue([
      {
        sessionId: 'sess-gen-001',
        specId: 'spec-gen-1',
        specName: 'shipping-service',
        status: 'RUNNING',
        currentLifecyclePhase: 'CODE_GEN',
        lifecycleMode: 'AUTONOMOUS',
        completionPercentage: 50,
        createdAt: '2026-09-23T00:00:00Z',
      },
    ]),
    quickStart: vi.fn(),
    getSession: vi.fn(),
    cancelSession: vi.fn(),
  },
}));

vi.mock('../services/orchestratorService', () => ({
  orchestratorService: {
    getOverview: vi.fn().mockResolvedValue({
      sessionId: 'sess-gen-001',
      serviceName: 'shipping-service',
      database: 'POSTGRESQL',
      totalStories: 3,
      totalEntities: 2,
      totalEndpoints: 4,
      testSuitesCount: 2,
      qualityGateStatus: 'PASS',
      qualityScore: 92,
      deploymentStatus: 'BUILDING',
      activePhase: 'CODE_GEN',
      completionPercentage: 50,
    }),
    getLifecycle: vi.fn().mockResolvedValue({
      sessionId: 'sess-gen-001',
      pipelineStatus: 'RUNNING',
      completionPercentage: 50,
      phases: [],
    }),
    runPipeline: vi.fn(),
    pausePipeline: vi.fn(),
    cancelPipeline: vi.fn(),
  },
}));

vi.mock('../services/exportService', () => ({
  exportService: {
    listArtifacts: vi.fn(),
    getArtifactContent: vi.fn(),
    getDownloadZipUrl: vi.fn().mockReturnValue('/api/v1/sessions/sess-gen-001/export'),
  },
}));

vi.mock('../services/testsService', () => ({
  testsService: {
    getRepairHistory: vi.fn().mockResolvedValue({
      sessionId: 'sess-gen-001',
      totalIterations: 0,
      maxAllowed: 3,
      exhausted: false,
      history: [],
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

describe('Views: GenerationMonitorView & CodeExplorerView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe('GenerationMonitorView', () => {
    it('renders the 6 LangGraph stages with their descriptions', async () => {
      renderWithProviders(<GenerationMonitorView />);

      await waitFor(() => {
        expect(screen.getByText('1. Scaffolding')).toBeInTheDocument();
        expect(screen.getByText('2. Generación Código')).toBeInTheDocument();
        expect(screen.getByText('3. Síntesis Tests')).toBeInTheDocument();
        expect(screen.getByText('4. Compilación Docker')).toBeInTheDocument();
        expect(screen.getByText('5. Auto-Reparación')).toBeInTheDocument();
        expect(screen.getByText('6. Verificado')).toBeInTheDocument();
      });
    });

    it('renders terminal controls (Auto-Scroll, Limpiar Terminal)', async () => {
      renderWithProviders(<GenerationMonitorView />);

      await waitFor(() => {
        expect(screen.getByText(/Auto-scroll/i)).toBeInTheDocument();
        expect(screen.getByText(/Limpiar/i)).toBeInTheDocument();
      });
    });
  });

  describe('CodeExplorerView', () => {
    it('renders empty state when there are no generated artifacts', async () => {
      vi.mocked(exportService.listArtifacts).mockResolvedValueOnce([]);

      renderWithProviders(<CodeExplorerView />);

      await waitFor(() => {
        expect(
          screen.getByText(/No hay artefactos de código generados aún/i)
        ).toBeInTheDocument();
      });
    });

    it('renders file tree and displays code content when an artifact is selected', async () => {
      vi.mocked(exportService.listArtifacts).mockResolvedValue([
        {
          id: 'art-1',
          sessionId: 'sess-gen-001',
          relativePath: 'pom.xml',
          fileType: 'xml',
          sizeBytes: 2048,
        },
        {
          id: 'art-2',
          sessionId: 'sess-gen-001',
          relativePath: 'src/main/java/com/corp/ShippingController.java',
          fileType: 'java',
          sizeBytes: 1500,
        },
      ]);

      vi.mocked(exportService.getArtifactContent).mockResolvedValue(
        '<project xmlns="http://maven.apache.org/POM/4.0.0">\n  <modelVersion>4.0.0</modelVersion>\n</project>'
      );

      renderWithProviders(<CodeExplorerView />);

      await waitFor(() => {
        expect(screen.getByTitle('pom.xml')).toBeInTheDocument();
        expect(screen.getByText('ShippingController.java')).toBeInTheDocument();
      });

      // Click on ShippingController.java
      fireEvent.click(screen.getByText('ShippingController.java'));

      await waitFor(() => {
        expect(exportService.getArtifactContent).toHaveBeenCalledWith(
          'sess-gen-001',
          'src/main/java/com/corp/ShippingController.java'
        );
      });
    });

    it('allows toggling between exploration subtabs (Artifacts, Tests, Self-Repair, Manual)', async () => {
      vi.mocked(exportService.listArtifacts).mockResolvedValueOnce([]);

      renderWithProviders(<CodeExplorerView />);

      await waitFor(() => {
        expect(screen.getByText(/📂 Artefactos del Microservicio/i)).toBeInTheDocument();
      });

      // Switch to Tests tab
      fireEvent.click(screen.getByText(/🧪 Suites de Pruebas & Cobertura/i));
      expect(
        screen.getByText(/Arquitectura Híbrida de Pruebas Herméticas/i)
      ).toBeInTheDocument();

      // Switch to Manual Intervention tab
      fireEvent.click(screen.getByText(/🛠️ Intervención Manual/i));
      expect(
        screen.getByText(/Intervención Manual y Desbloqueo/i)
      ).toBeInTheDocument();
    });
  });
});
