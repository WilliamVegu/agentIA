import React from 'react';
import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { VerificationStatus } from '../components/common/VerificationStatus';
import { GenerationMonitorView } from '../views/GenerationMonitorView';
import { ExportPublishView } from '../views/ExportPublishView';

const mocks = vi.hoisted(() => ({ studio: { activeSessionId: 'source', activeSession: {} as any,
  lifecycle: null, isQueued: false, refreshSessions: vi.fn(), reloadCurrentOverview: vi.fn(), setActiveTab: vi.fn() } }));
vi.mock('../context/StudioContext', () => ({ useStudio: () => mocks.studio }));
vi.mock('../hooks/useSSE', () => ({ useSSE: () => ({ logs: [], isConnected: false, lastEvent: null, clearLogs: vi.fn() }) }));
beforeEach(() => { mocks.studio.activeSession = { status: 'COMPLETED', executionMode: 'SOURCE_ONLY', verificationOutcome: 'SKIPPED_BY_CHOICE' }; });

it.each([
  [{ executionMode: 'DOCKER', verificationOutcome: 'INTERRUPTED' }, /Verificación interrumpida/],
  [{ executionMode: 'DOCKER', verificationOutcome: 'OUTDATED' }, /Evidencia obsoleta/],
  [{ executionMode: 'SOURCE_ONLY', verificationOutcome: 'OUTDATED' }, /Evidencia obsoleta/],
  [{ executionMode: 'SOURCE_ONLY', verificationOutcome: 'FAILED' }, /Pruebas fallidas/],
  [{ executionMode: 'SOURCE_ONLY', verificationOutcome: 'SKIPPED_BY_CHOICE' }, /artefactos, no pruebas ejecutadas/],
  [{ executionMode: 'DOCKER', verificationOutcome: 'PASSED' }, /aprobadas según la evidencia/],
  [{ executionMode: 'SOURCE_ONLY', verificationOutcome: 'PASSED' }, /No hay nueva ejecución/],
  [{ executionMode: 'DOCKER', verificationOutcome: 'ENVIRONMENT_UNAVAILABLE' }, /reintente o continúe sin Docker/],
  [{ executionMode: 'DOCKER' }, /sin evidencia/],
])('comunica el resultado explícito sin confundir omisión/aprobación: %o', (session, message) => {
  render(<VerificationStatus session={session} />);
  expect(screen.getByText(message)).toBeInTheDocument();
});

it('COMPLETED en fuentes no declara sandbox ni ejecución aprobados en monitor', () => {
  render(<GenerationMonitorView />);
  expect(screen.getAllByText(/Omitida por elección; no acredita ejecución/)).toHaveLength(3);
  expect(screen.getByText(/Generación completada; consulte/)).toBeInTheDocument();
  expect(screen.queryByText(/Verificado al 100%/)).not.toBeInTheDocument();
  expect(screen.queryByText('Sandbox verificado sin errores.')).not.toBeInTheDocument();
});

it('exportación en fuentes conserva acceso al ZIP sin prometer release verificado', () => {
  render(<ExportPublishView />);
  expect(screen.getByRole('button', { name: /Descargar Código Fuente/ })).toBeEnabled();
  expect(screen.getByText('Entrega de fuentes')).toBeInTheDocument();
  expect(screen.queryByText('Release Ready')).not.toBeInTheDocument();
  expect(screen.getByText(/generar pruebas o exportar fuentes no acredita/)).toBeInTheDocument();
});
