import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { StudioOverviewView } from '../views/StudioOverviewView';
import { DevOpsDeploymentView } from '../views/DevOpsDeploymentView';

const mocks = vi.hoisted(() => ({
  studio: { activeSessionId: null as string | null, activeSession: null as any, projectOverview: null as any, lifecycle: null, refreshSessions: vi.fn().mockResolvedValue(undefined), selectSession: vi.fn(), startNewService: vi.fn(), setActiveTab: vi.fn(), reloadCurrentOverview: vi.fn().mockResolvedValue(undefined), isQueued: false },
  quickStart: vi.fn().mockResolvedValue({ sessionId: 'created' }),
  changeMode: vi.fn().mockResolvedValue({}), verify: vi.fn().mockResolvedValue({ status: 'COMPLETED' }),
  status: vi.fn(), logs: vi.fn().mockResolvedValue([]), deploy: vi.fn(), diagnostics: vi.fn(),
  subscribe: vi.fn(), unsubscribe: vi.fn(), proxy: vi.fn(), stop: vi.fn(), smoke: vi.fn(),
  restart: vi.fn(), cleanup: vi.fn(), cleanupPreview: vi.fn(), cancel: vi.fn(),
  configuration: vi.fn(), generate: vi.fn(),
}));
vi.mock('../context/StudioContext', () => ({ useStudio: () => mocks.studio }));
vi.mock('../context/LlmContext', () => ({ useLlm: () => ({ provider: 'mock', apiKey: '' }) }));
vi.mock('../services/sessionService', () => ({ sessionService: { quickStart: mocks.quickStart, changeExecutionMode: mocks.changeMode, verify: mocks.verify } }));
vi.mock('../services/devopsService', () => ({ devopsService: { getConfiguration: mocks.configuration, generateManifests: mocks.generate, getDeploymentStatus: mocks.status, getLogs: mocks.logs, deployLocal: mocks.deploy, getDiagnostics: mocks.diagnostics, proxyPlayground: mocks.proxy, stopContainers: mocks.stop, runSmokeTest: mocks.smoke, restartLocal: mocks.restart, cleanupLocal: mocks.cleanup, cleanupPreview: mocks.cleanupPreview, cancelLocal: mocks.cancel, getPlaygroundResources: vi.fn().mockResolvedValue({ resources: [] }) } }));
vi.mock('../services/exportService', () => ({ exportService: { getArtifactContent: vi.fn().mockRejectedValue(new Error('not generated')) } }));
vi.mock('../services/deploymentLogStream', () => ({ subscribeDeploymentLogs: mocks.subscribe }));

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(window,'confirm').mockReturnValue(true);
  mocks.cleanupPreview.mockResolvedValue({ sessionId: 'own', confirmationToken: 'preview-identity', resources: { container: ['own-container'], volume: ['own-volume'] } });
  mocks.configuration.mockResolvedValue(null);
  mocks.subscribe.mockImplementation((_id, logs) => { logs([]); return mocks.unsubscribe; });
  mocks.studio.activeSessionId = null;
  mocks.studio.activeSession = null;
  mocks.studio.projectOverview = null;
});

describe('Elección de ejecución local', () => {
  it('conserva la configuración guardada pese a un estado inicial con defaults', async () => {
    mocks.studio.activeSessionId = 'saved';
    mocks.studio.activeSession = { executionMode: 'SOURCE_ONLY' };
    mocks.studio.projectOverview = { databaseEngine: 'POSTGRESQL' };
    mocks.configuration.mockResolvedValue({ hostPort: 18081, databaseEngine: 'H2', buildTool: 'maven', buildDirectory: '.' });
    mocks.status.mockResolvedValue({ sessionId: 'saved', status: 'SKIPPED_BY_CHOICE', hostPort: 8080 });
    mocks.generate.mockResolvedValue({ kubernetesManifests: {} });
    render(<DevOpsDeploymentView />);
    await waitFor(() => expect(screen.getByLabelText('Puerto local')).toHaveValue(18081));
    fireEvent.click(screen.getByRole('button', { name: /Generar Manifiestos DevOps/ }));
    await waitFor(() => expect(mocks.generate).toHaveBeenCalledWith('saved', 'H2', undefined));
    expect(screen.getByLabelText('Puerto local')).toHaveValue(18081);
    expect(mocks.deploy).not.toHaveBeenCalled();
  });

  it('una configuración tardía no pisa un puerto editado', async () => {
    let resolve!: (value: any) => void;
    mocks.configuration.mockReturnValue(new Promise(done => { resolve = done; }));
    mocks.studio.activeSessionId = 'edited';
    mocks.studio.activeSession = { executionMode: 'SOURCE_ONLY' };
    mocks.status.mockResolvedValue({ sessionId: 'edited', status: 'SKIPPED_BY_CHOICE', hostPort: 8080 });
    render(<DevOpsDeploymentView />);
    fireEvent.change(screen.getByLabelText('Puerto local'), { target: { value: '18082' } });
    await act(async () => resolve({ hostPort: 18081, databaseEngine: 'H2' }));
    await waitFor(() => expect(mocks.configuration).toHaveBeenCalled());
    expect(screen.getByLabelText('Puerto local')).toHaveValue(18082);
  });

  it('descarta la configuración tardía de otra sesión', async () => {
    let resolve!: (value: any) => void;
    mocks.configuration.mockReturnValueOnce(new Promise(done => { resolve = done; }))
      .mockResolvedValue({ hostPort: 18090, databaseEngine: 'H2' });
    mocks.studio.activeSessionId = 'previous';
    mocks.studio.activeSession = { executionMode: 'SOURCE_ONLY' };
    mocks.status.mockResolvedValue({ status: 'SKIPPED_BY_CHOICE', hostPort: 8080 });
    const view = render(<DevOpsDeploymentView />);
    mocks.studio.activeSessionId = 'current';
    view.rerender(<DevOpsDeploymentView />);
    await waitFor(() => expect(screen.getByLabelText('Puerto local')).toHaveValue(18090));
    await act(async () => resolve({ hostPort: 18081, databaseEngine: 'MYSQL' }));
    expect(screen.getByLabelText('Puerto local')).toHaveValue(18090);
  });

  it('mantiene el puerto efectivo del contenedor ante configuración tardía', async () => {
    let resolve!: (value: any) => void;
    mocks.configuration.mockReturnValue(new Promise(done => { resolve = done; }));
    mocks.studio.activeSessionId = 'running';
    mocks.studio.activeSession = { executionMode: 'DOCKER' };
    mocks.status.mockResolvedValue({ sessionId: 'running', status: 'HEALTHY', containerId: 'own', hostPort: 28080 });
    render(<DevOpsDeploymentView />);
    await waitFor(() => expect(screen.getByLabelText('Puerto local')).toHaveValue(28080));
    await act(async () => resolve({ hostPort: 18081, databaseEngine: 'H2' }));
    expect(screen.getByLabelText('Puerto local')).toHaveValue(28080);
    expect(screen.getByLabelText('Puerto local')).toBeDisabled();
  });
  it('solicita cancelar la operación exacta sin afirmar que BuildKit terminó', async () => {
    mocks.studio.activeSessionId = 'cancel';
    mocks.studio.activeSession = { executionMode: 'DOCKER' };
    const pending = { sessionId: 'cancel', status: 'BUILDING', hostPort: 8181,
      operationId: 'operation-1', operationKind: 'DEPLOY', operationPhase: 'BUILD' };
    mocks.status.mockResolvedValue(pending);
    mocks.cancel.mockResolvedValue({ ...pending, cancelRequested: true, message: 'Cancelación solicitada; espere el estado final.' });
    render(<DevOpsDeploymentView />);
    fireEvent.click(await screen.findByRole('button', { name: 'Cancelar operación local' }));
    await waitFor(() => expect(mocks.cancel).toHaveBeenCalledWith('cancel', 'operation-1'));
    expect(await screen.findByRole('button', { name: 'Cancelación solicitada' })).toBeDisabled();
    expect(screen.getByText(/no confirma que las tareas de Docker hayan terminado/)).toBeInTheDocument();
    expect(mocks.stop).not.toHaveBeenCalled();
  });
  it('reinicia sin reconstruir y bloquea otras acciones durante BUILDING', async () => {
    mocks.studio.activeSessionId = 'restart';
    mocks.studio.activeSession = { executionMode: 'DOCKER' };
    mocks.status.mockResolvedValue({ sessionId: 'restart', status: 'STOPPED', containerId: 'own', hostPort: 8181 });
    mocks.restart.mockResolvedValue({ sessionId: 'restart', status: 'BUILDING', hostPort: 8181, message: 'Reinicio sin reconstrucción; datos conservados.' });
    render(<DevOpsDeploymentView />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Reiniciar conservando datos' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Reiniciar conservando datos' }));
    expect((await screen.findAllByText('Reinicio sin reconstrucción; datos conservados.')).length).toBeGreaterThan(0);
    expect(mocks.restart).toHaveBeenCalledWith('restart');
    expect(mocks.deploy).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /Desplegar Localmente/ })).toBeDisabled();
  });

  it('limpieza necesita confirmación por sesión y la borra al cambiarla', async () => {
    mocks.studio.activeSessionId = 'cleanup';
    mocks.studio.activeSession = { executionMode: 'DOCKER' };
    mocks.status.mockResolvedValue({ sessionId: 'cleanup', status: 'STOPPED', hostPort: 8181 });
    mocks.cleanup.mockResolvedValue({ sessionId: 'cleanup', status: 'STOPPED', hostPort: 8181, message: 'Datos propios eliminados.' });
    const view = render(<DevOpsDeploymentView />);
    const button = screen.getByRole('button', { name: 'Eliminar datos y recursos de esta sesión' });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox', { name: /Confirmo eliminar los datos/ }));
    fireEvent.click(button);
    expect((await screen.findAllByText('Datos propios eliminados.')).length).toBeGreaterThan(0);
    expect(mocks.cleanup).toHaveBeenCalledWith('cleanup', true, 'preview-identity');
    expect(screen.getByRole('checkbox', { name: /Confirmo eliminar los datos/ })).not.toBeChecked();
    fireEvent.click(screen.getByRole('checkbox', { name: /Confirmo eliminar los datos/ }));
    mocks.studio.activeSessionId = 'other'; view.rerender(<DevOpsDeploymentView />);
    expect(screen.getByRole('checkbox', { name: /Confirmo eliminar los datos/ })).not.toBeChecked();
  });
  it('bloquea acciones incompatibles durante BUILDING y conserva su causa', async () => {
    mocks.studio.activeSessionId = 'busy';
    mocks.studio.activeSession = { executionMode: 'DOCKER', verificationOutcome: 'ENVIRONMENT_UNAVAILABLE' };
    mocks.status.mockResolvedValue({ sessionId: 'busy', status: 'BUILDING', hostPort: 8181, message: 'Preparando imágenes' });
    render(<DevOpsDeploymentView />);
    expect(await screen.findByText('Preparando imágenes')).toBeInTheDocument();
    for (const name of [/Generar Manifiestos/, /Desplegar Localmente/, /Ejecutar Smoke/, /Detener/, /^Enviar$/]) {
      expect(screen.getByRole('button', { name })).toBeDisabled();
    }
    expect(screen.getByText(/aún no aprobada/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument();
  });

  it('permite detener/probar un servicio degradado y muestra la BD inspeccionada', async () => {
    mocks.studio.activeSessionId = 'degraded';
    mocks.studio.activeSession = { executionMode: 'DOCKER' };
    mocks.studio.projectOverview = { databaseEngine: 'POSTGRESQL' };
    mocks.status.mockResolvedValue({ sessionId: 'degraded', status: 'DEGRADED', containerId: 'own', hostPort: 8181, dbEngine: 'H2', errorMessage: 'Salud DOWN' });
    render(<DevOpsDeploymentView />);
    expect(await screen.findByText('Salud DOWN')).toBeInTheDocument();
    expect(screen.getByText('H2')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Detener/ })).toBeEnabled();
    expect(screen.getByRole('button', { name: /Ejecutar Smoke/ })).toBeEnabled();
  });

  it('descarta respuestas REST tardías al cambiar sesión y limpia su consola', async () => {
    let resolveOld: (value: any) => void = () => undefined;
    mocks.proxy.mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }));
    mocks.studio.activeSessionId = 'old';
    mocks.studio.activeSession = { executionMode: 'DOCKER' };
    mocks.status.mockImplementation(id => Promise.resolve({ sessionId: id, status: 'RUNNING', containerId: id, hostPort: 8181 }));
    const view = render(<DevOpsDeploymentView />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Enviar' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));
    expect(screen.getByRole('button', { name: /Generar Manifiestos/ })).toBeDisabled();
    mocks.studio.activeSessionId = 'new';
    mocks.studio.activeSession = { executionMode: 'SOURCE_ONLY' };
    view.rerender(<DevOpsDeploymentView />);
    resolveOld({ statusCode: 200, body: 'OLD_SESSION_BODY', error: null });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled());
    expect(screen.queryByText('OLD_SESSION_BODY')).not.toBeInTheDocument();
  });

  it('no verifica la sesión anterior si cambia durante la elección de modo', async () => {
    let resolveMode: (value: any) => void = () => undefined;
    mocks.changeMode.mockImplementationOnce(() => new Promise(resolve => { resolveMode = resolve; }));
    mocks.studio.activeSessionId = 'old';
    mocks.studio.activeSession = { executionMode: 'SOURCE_ONLY' };
    mocks.status.mockResolvedValue({ sessionId: 'old', status: 'SKIPPED_BY_CHOICE', hostPort: 8080 });
    const view = render(<DevOpsDeploymentView />);
    fireEvent.click(screen.getByRole('button', { name: 'Activar Docker y verificar' }));
    mocks.studio.activeSessionId = 'new';
    view.rerender(<DevOpsDeploymentView />);
    resolveMode({});
    await waitFor(() => expect(screen.getByRole('button', { name: 'Activar Docker y verificar' })).toBeEnabled());
    expect(mocks.verify).not.toHaveBeenCalled();
  });

  it('renueva estado después del smoke test y deja detener sin resultado antiguo', async () => {
    mocks.studio.activeSessionId = 'runtime';
    mocks.studio.activeSession = { executionMode: 'DOCKER' };
    mocks.status.mockResolvedValue({ sessionId: 'runtime', status: 'RUNNING', containerId: 'own', hostPort: 8181 });
    mocks.smoke.mockResolvedValue({ passed: true, details: 'SMOKE_CONFIRMED', testUrl: 'http://localhost:8181/actuator/health' });
    mocks.stop.mockResolvedValue({ sessionId: 'runtime', status: 'STOPPED', hostPort: 8181 });
    render(<DevOpsDeploymentView />);
    await waitFor(() => expect(screen.getByRole('button', { name: /Ejecutar Smoke/ })).toBeEnabled());
    const before = mocks.status.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: /Ejecutar Smoke/ }));
    expect(await screen.findByText('SMOKE_CONFIRMED')).toBeInTheDocument();
    expect(mocks.status.mock.calls.length).toBeGreaterThan(before);
    await waitFor(() => expect(screen.getByRole('button', { name: /Detener/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /Detener/ }));
    expect(await screen.findByText('STOPPED')).toBeInTheDocument();
    expect(screen.queryByText('SMOKE_CONFIRMED')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled();
  });
  it('cancela logs al cambiar sesión e impide que un estado anterior la reemplace', async () => {
    let resolveOld: (value: any) => void = () => undefined;
    mocks.studio.activeSessionId = 'old';
    mocks.status.mockImplementation((id) => id === 'old' ? new Promise(resolve => { resolveOld = resolve; }) :
      Promise.resolve({ sessionId: 'new', status: 'NOT_DEPLOYED', hostPort: 8181 }));
    const view = render(<DevOpsDeploymentView />);
    mocks.studio.activeSessionId = 'new';
    view.rerender(<DevOpsDeploymentView />);
    expect(mocks.unsubscribe).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(mocks.subscribe).toHaveBeenLastCalledWith('new', expect.any(Function), expect.any(Function)));
    resolveOld({ sessionId: 'old', status: 'RUNNING', hostPort: 9999 });
    await waitFor(() => expect(screen.getByText('8181:8080')).toBeInTheDocument());
    expect(screen.queryByText('9999:8080')).not.toBeInTheDocument();
    view.unmount();
    expect(mocks.unsubscribe).toHaveBeenCalledTimes(2);
  });
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
