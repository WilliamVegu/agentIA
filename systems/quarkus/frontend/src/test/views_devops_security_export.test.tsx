import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from '../context/ThemeContext';
import { AuthProvider } from '../context/AuthContext';
import { LlmProvider } from '../context/LlmContext';
import { StudioProvider } from '../context/StudioContext';
import { SecurityQualityView } from '../views/SecurityQualityView';
import { DevOpsDeploymentView } from '../views/DevOpsDeploymentView';
import { ExportPublishView } from '../views/ExportPublishView';
import { securityService } from '../services/securityService';
import { devopsService } from '../services/devopsService';
import { exportService } from '../services/exportService';
import { sessionService } from '../services/sessionService';

vi.mock('../services/sessionService', () => ({
  sessionService: {
    listSessions: vi.fn().mockResolvedValue([
      {
        sessionId: 'sess-ops-001',
        specId: 'spec-ops-1',
        specName: 'notification-service',
        status: 'COMPLETED',
        currentLifecyclePhase: 'DEVOPS_DEPLOY',
        lifecycleMode: 'AUTONOMOUS',
        completionPercentage: 100,
        createdAt: '2026-09-23T00:00:00Z',
      },
    ]),
    quickStart: vi.fn(),
    getSession: vi.fn(),
  },
}));

vi.mock('../services/orchestratorService', () => ({
  orchestratorService: {
    getOverview: vi.fn().mockResolvedValue({
      sessionId: 'sess-ops-001',
      serviceName: 'notification-service',
      database: 'POSTGRESQL',
      totalStories: 3,
      totalEntities: 2,
      totalEndpoints: 4,
      testSuitesCount: 2,
      qualityGateStatus: 'PASS',
      qualityScore: 98,
      deploymentStatus: 'STOPPED',
      activePhase: 'DEVOPS_DEPLOY',
      completionPercentage: 100,
    }),
    getLifecycle: vi.fn().mockResolvedValue({
      sessionId: 'sess-ops-001',
      pipelineStatus: 'COMPLETED',
      completionPercentage: 100,
      phases: [],
    }),
    invalidateDownstream: vi.fn(),
  },
}));

vi.mock('../services/securityService', () => ({
  securityService: {
    getAuditReport: vi.fn(),
    applySurgicalRemediation: vi.fn(),
  },
}));

vi.mock('../services/devopsService', () => ({
  devopsService: {
    getDeploymentStatus: vi.fn().mockResolvedValue({
      sessionId: 'sess-ops-001',
      serviceName: 'notification-service',
      status: 'STOPPED',
      hostPort: 8080,
      dbEngine: 'POSTGRESQL',
      healthStatus: 'UNKNOWN',
      message: 'Contenedor detenido',
    }),
    deployLocal: vi.fn(),
    stopContainers: vi.fn(),
    runSmokeTest: vi.fn(),
    getLogs: vi.fn().mockResolvedValue(['[LOG] Container ready']),
    generateManifests: vi.fn(),
  },
}));

vi.mock('../services/exportService', () => ({
  exportService: {
    getDownloadZipUrl: vi.fn().mockReturnValue('/api/v1/sessions/sess-ops-001/export'),
    publishToGit: vi.fn(),
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

describe('Views: SecurityQuality, DevOpsDeployment, ExportPublish', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe('SecurityQualityView', () => {
    it('renders empty state when audit report is not yet loaded', async () => {
      vi.mocked(securityService.getAuditReport).mockResolvedValueOnce(null as any);

      renderWithProviders(<SecurityQualityView />);

      await waitFor(() => {
        expect(
          screen.getByText(/Auditoría SAST y Quality Gate no disponibles/i)
        ).toBeInTheDocument();
      });
    });

    it('loads and displays audit report metrics and quality gate verdict', async () => {
      vi.mocked(securityService.getAuditReport).mockResolvedValue({
        sessionId: 'sess-ops-001',
        serviceName: 'notification-service',
        qualityGate: {
          verdict: 'PASS',
          canExport: true,
          canDeploy: true,
          score: 96,
          summaryMessage: 'Quality Gate Aprobado sin vulnerabilidades críticas',
          criticalCount: 0,
          highCount: 0,
          mediumCount: 1,
          lowCount: 2,
        },
        metrics: {
          linesOfCode: 850,
          testCoverageEstimate: 92,
          cyclomaticComplexityAverage: 2.1,
          maintainabilityIndex: 88,
        },
        vulnerabilities: [
          {
            id: 'VULN-001',
            rule_id: 'CWE-89',
            severity: 'MEDIUM',
            category: 'SQL Injection Guard',
            file: 'NotificationRepository.java',
            line: 42,
            message: 'Parámetro validado por JPA Criteria',
          },
        ],
        violations: [],
      });

      renderWithProviders(<SecurityQualityView />);

      await waitFor(() => {
        expect(screen.getByText('Rating de Seguridad')).toBeInTheDocument();
        expect(screen.getByText(/96.*100 Puntos/i)).toBeInTheDocument();
        expect(screen.getByText(/NotificationRepository\.java/i)).toBeInTheDocument();
      });
    });
  });

  describe('DevOpsDeploymentView', () => {
    it('renders deployment dashboard with port configuration and Stopped status', async () => {
      renderWithProviders(<DevOpsDeploymentView />);

      await waitFor(() => {
        expect(screen.getByText(/Fase 8: DevOps, Contenerización & Despliegue Multi-Stage/i)).toBeInTheDocument();
        expect(screen.getByText('STOPPED')).toBeInTheDocument();
      });
    });

    it('triggers deployLocal and updates deployment status', async () => {
      vi.mocked(devopsService.deployLocal).mockResolvedValueOnce({
        sessionId: 'sess-ops-001',
        serviceName: 'notification-service',
        status: 'RUNNING',
        hostPort: 8080,
        containerId: 'docker-container-abc123',
        dbEngine: 'POSTGRESQL',
        healthStatus: 'UP',
        message: 'Contenedor Spring Boot 3 desplegado y saludable en el puerto 8080',
      });

      renderWithProviders(<DevOpsDeploymentView />);

      await waitFor(() => {
        expect(screen.getByText(/Fase 8: DevOps/i)).toBeInTheDocument();
      });

      const deployBtn = screen.getByRole('button', { name: /Desplegar Localmente/i });
      fireEvent.click(deployBtn);

      await waitFor(() => {
        expect(devopsService.deployLocal).toHaveBeenCalledWith('sess-ops-001', 8080, true);
      });
    });
  });

  describe('ExportPublishView', () => {
    it('calls window.open with the zip download URL when download button is clicked', async () => {
      const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);

      renderWithProviders(<ExportPublishView />);

      const downloadBtn = screen.getByRole('button', {
        name: /Descargar Código Fuente Completo \(ZIP\)/i,
      });

      await waitFor(() => {
        expect(downloadBtn).not.toBeDisabled();
      });

      fireEvent.click(downloadBtn);

      expect(exportService.getDownloadZipUrl).toHaveBeenCalledWith('sess-ops-001');
      expect(openSpy).toHaveBeenCalledWith('/api/v1/sessions/sess-ops-001/export', '_blank');

      openSpy.mockRestore();
    });

    it('submits git form and triggers publishToGit', async () => {
      vi.mocked(exportService.publishToGit).mockResolvedValueOnce({
        branchUrl: 'https://github.com/tcs-enterprise/notification-service/tree/feature/001-notification-service',
        commitHash: 'a1b2c3d4e5f6',
        branchName: 'feature/001-notification-service',
      });

      renderWithProviders(<ExportPublishView />);

      const repoInput = screen.getByPlaceholderText(/https:\/\/github\.com\/org\/repo\.git/i);
      const submitBtn = screen.getByRole('button', { name: /Publicar Rama a Git/i });

      await waitFor(() => {
        expect(submitBtn).not.toBeDisabled();
      });

      fireEvent.change(repoInput, {
        target: { value: 'https://github.com/tcs-enterprise/notification-service.git' },
      });

      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(exportService.publishToGit).toHaveBeenCalledWith(
          'sess-ops-001',
          expect.objectContaining({
            repositoryUrl: 'https://github.com/tcs-enterprise/notification-service.git',
          })
        );
        expect(screen.getByText(/Publicación a Git exitosa/i)).toBeInTheDocument();
      });
    });
  });
});
