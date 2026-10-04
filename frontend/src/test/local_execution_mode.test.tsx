import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { StudioOverviewView } from '../views/StudioOverviewView';
import { DevOpsDeploymentView } from '../views/DevOpsDeploymentView';

const mocks = vi.hoisted(() => ({
  studio: { activeSessionId: null as string | null, activeSession: null as any, projectOverview: null as any, lifecycle: null, refreshSessions: vi.fn().mockResolvedValue(undefined), selectSession: vi.fn(), startNewService: vi.fn(), setActiveTab: vi.fn(), reloadCurrentOverview: vi.fn().mockResolvedValue(undefined), isQueued: false },
  quickStart: vi.fn().mockResolvedValue({ sessionId: 'created' }),
  changeMode: vi.fn().mockResolvedValue({}), verify: vi.fn().mockResolvedValue({ status: 'COMPLETED' }),
  status: vi.fn(), logs: vi.fn().mockResolvedValue([]), deploy: vi.fn(), diagnostics: vi.fn(),
}));
vi.mock('../context/StudioContext', () => ({ useStudio: () => mocks.studio }));
vi.mock('../context/LlmContext', () => ({ useLlm: () => ({ provider: 'mock', apiKey: '' }) }));
vi.mock('../services/sessionService', () => ({ sessionService: { quickStart: mocks.quickStart, changeExecutionMode: mocks.changeMode, verify: mocks.verify } }));
vi.mock('../services/devopsService', () => ({ devopsService: { getDeploymentStatus: mocks.status, getLogs: mocks.logs, deployLocal: mocks.deploy, getDiagnostics: mocks.diagnostics, getPlaygroundResources: vi.fn().mockResolvedValue({ resources: [] }) } }));
vi.mock('../services/exportService', () => ({ exportService: { getArtifactContent: vi.fn().mockRejectedValue(new Error('not generated')) } }));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.studio.activeSessionId = null;
  mocks.studio.activeSession = null;
  mocks.studio.projectOverview = null;
});

describe('Elección de ejecución local', () => {
  it('consulta diagnóstico solo por petición explícita y no lo confunde con verificación', async () => {
    mocks.studio.activeSessionId = 'diag-session';
    mocks.studio.activeSession = { executionMode: 'DOCKER' };
    mocks.status.mockResolvedValue({ sessionId: 'diag-session', status: 'DOCKER_UNAVAILABLE', hostPort: 8080 });
    mocks.diagnostics.mockResolvedValue({ sessionId: 'diag-session', offlineVerified: false, checks: [{ name: 'engine', status: 'UNAVAILABLE', detail: 'Motor inaccesible: named pipe ausente.' }] });
    render(<DevOpsDeploymentView />);
    expect(mocks.diagnostics).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Diagnosticar Docker' }));
    expect(await screen.findByText('• Motor inaccesible: named pipe ausente.')).toBeInTheDocument();
    expect(screen.getByText(/no sustituye la compilación/)).toBeInTheDocument();
    expect(mocks.deploy).not.toHaveBeenCalled();
  });
  it('crea fuentes sin Docker por defecto y conserva la elección por sesión', async () => {
    render(<StudioOverviewView />);
    expect(screen.getByLabelText('Ejecución de este microservicio')).toHaveValue('SOURCE_ONLY');
    fireEvent.change(screen.getByPlaceholderText(/ej\. order-fulfillment-service/), { target: { value: 'lab-service' } });
    fireEvent.change(screen.getByPlaceholderText(/Describa el objetivo de negocio/), { target: { value: 'Gestionar productos e inventario de una tienda' } });
    fireEvent.click(screen.getByRole('button', { name: /Crear e Iniciar Modo Asistido/ }));
    await waitFor(() => expect(mocks.quickStart).toHaveBeenCalled());
    expect(mocks.quickStart.mock.calls[0][0]).toMatchObject({ execution_mode: 'SOURCE_ONLY', auto_deploy: false });
    expect(mocks.deploy).not.toHaveBeenCalled();
  });

  it('permite elegir Docker y despliegue automático explícitamente', async () => {
    render(<StudioOverviewView />);
    fireEvent.change(screen.getByLabelText('Ejecución de este microservicio'), { target: { value: 'DOCKER' } });
    fireEvent.click(screen.getByRole('checkbox', { name: /Desplegar automáticamente/ }));
    fireEvent.change(screen.getByPlaceholderText(/ej\. order-fulfillment-service/), { target: { value: 'docker-service' } });
    fireEvent.change(screen.getByPlaceholderText(/Describa el objetivo de negocio/), { target: { value: 'Gestionar productos e inventario de una tienda' } });
    fireEvent.click(screen.getByRole('button', { name: /Crear y Ejecutar Auto-Pilot Completo/ }));
    await waitFor(() => expect(mocks.quickStart).toHaveBeenCalled());
    expect(mocks.quickStart.mock.calls[0][0]).toMatchObject({ execution_mode: 'DOCKER', auto_deploy: true });
  });

  it('ofrece reintentar y continuar sin Docker cuando la infraestructura falta', async () => {
    mocks.studio.activeSessionId = 'lab-session';
    mocks.studio.activeSession = { executionMode: 'DOCKER', verificationOutcome: 'ENVIRONMENT_UNAVAILABLE' };
    mocks.status.mockResolvedValue({ sessionId: 'lab-session', status: 'DOCKER_UNAVAILABLE', hostPort: 8080 });
    render(<DevOpsDeploymentView />);
    expect(await screen.findByRole('button', { name: 'Reintentar' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'Continuar sin Docker' }));
    await waitFor(() => expect(mocks.changeMode).toHaveBeenCalledWith('lab-session', 'SOURCE_ONLY'));
    expect(mocks.verify).toHaveBeenCalledWith('lab-session');
    expect(mocks.deploy).not.toHaveBeenCalled();
  });

  it('una sesión sin Docker puede generar manifiestos y no despliega contenedores', async () => {
    mocks.studio.activeSessionId = 'source-session';
    mocks.studio.activeSession = { executionMode: 'SOURCE_ONLY' };
    mocks.status.mockResolvedValue({ sessionId: 'source-session', status: 'SKIPPED_BY_CHOICE', hostPort: 8080 });
    render(<DevOpsDeploymentView />);
    expect(screen.getByRole('button', { name: /Generar Manifiestos DevOps/ })).toBeEnabled();
    expect(screen.getByRole('button', { name: /Desplegar Localmente/ })).toBeDisabled();
    expect(mocks.deploy).not.toHaveBeenCalled();
  });
});
