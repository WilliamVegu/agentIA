import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GenerationMonitorView } from '../views/GenerationMonitorView';

const state = vi.hoisted(() => ({ session: {} as any }));
vi.mock('../context/StudioContext', () => ({ useStudio: () => ({
  activeSessionId: 'monitor-proof', activeSession: state.session, lifecycle: null,
  isQueued: false, currentSpecId: null, selectSession: vi.fn(), refreshSessions: vi.fn(),
  reloadCurrentOverview: vi.fn(), setActiveTab: vi.fn(),
}) }));
vi.mock('../hooks/useSSE', () => ({ useSSE: () => ({
  logs: [], isConnected: true, clearLogs: vi.fn(), lastEvent: null,
}) }));

describe('completion requires execution evidence', () => {
  beforeEach(() => {
    state.session = { status: 'COMPLETED', executionMode: 'SOURCE_ONLY',
      verificationOutcome: 'SKIPPED_BY_CHOICE', repairAttempts: 0 };
  });

  it('does not invent five passing tests when delivering sources', () => {
    render(<GenerationMonitorView />);
    expect(screen.queryByText(/5\/5 Pasadas/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Verificado al 100/)).not.toBeInTheDocument();
    expect(screen.getAllByText(/pruebas generadas son artefactos/).length).toBeGreaterThan(0);
    expect(screen.getByText('SKIPPED_BY_CHOICE')).toBeInTheDocument();
    expect(screen.getByText('0 / 3 intentos')).toBeInTheDocument();
    expect(screen.getAllByText('Omitida por elección; no acredita ejecución.')).toHaveLength(3);
  });

  it('does not certify a completed operation without a verification verdict', () => {
    state.session = { status: 'COMPLETED', executionMode: 'DOCKER_VERIFIED', repairAttempts: 1 };
    render(<GenerationMonitorView />);
    expect(screen.getAllByText(/Verificación pendiente o sin evidencia/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/con pruebas de ejecución aprobadas/)).not.toBeInTheDocument();
  });

  it('shows a passing verdict only when the backend supplies it', () => {
    state.session = { status: 'COMPLETED', executionMode: 'DOCKER_VERIFIED',
      verificationOutcome: 'PASSED', repairAttempts: 0 };
    render(<GenerationMonitorView />);
    expect(screen.getByText('Microservicio generado con pruebas de ejecución aprobadas.')).toBeInTheDocument();
    expect(screen.queryByText(/5\/5 Pasadas/)).not.toBeInTheDocument();
  });
});
