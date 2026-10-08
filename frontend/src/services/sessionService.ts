import apiClient from './apiClient';
export type ExecutionMode = 'SOURCE_ONLY' | 'DOCKER';

export interface QuickStartPayload {
  execution_mode?: ExecutionMode;
  auto_deploy?: boolean;
  service_name: string;
  prompt?: string;
  raw_text?: string;
  databaseEngine?: 'POSTGRESQL' | 'MYSQL' | 'H2';
  /** Compatibility alias; conflicting values are rejected by the API. */
  database?: 'POSTGRESQL' | 'MYSQL' | 'H2';
  auto_run?: boolean;
  llm_provider?: string;
  api_key?: string;
  input_interface?: any;
}

export interface SessionListItem {
  executionMode?: ExecutionMode;
  verificationOutcome?: string;
  sessionId: string;
  specId: string;
  specName: string;
  status: 'CREATED' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'BLOCKED' | 'PAUSED' | 'CANCELLED';
  phase?: string;
  currentLifecyclePhase: string;
  lifecycleMode: string;
  completionPercentage: number;
  repairAttempts?: number;
  failureReason?: string;
  errorMessage?: string;
  createdAt: string;
}

export interface SessionDetail {
  executionMode: ExecutionMode;
  verificationOutcome?: string;
  availableActions?: string[];
  id: string;
  specId: string;
  specName: string;
  status: string;
  phase: string;
  queuePosition?: number;
  repairAttempts: number;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  errorMessage?: string;
}

export const sessionService = {
  async listSessions(limit = 50): Promise<SessionListItem[]> {
    const response = await apiClient.get<SessionListItem[]>('/sessions', {
      params: { limit },
    });
    return response.data;
  },

  async getSession(sessionId: string): Promise<SessionDetail> {
    const response = await apiClient.get<SessionDetail>(`/sessions/${sessionId}`);
    return response.data;
  },

  async quickStart(payload: QuickStartPayload) {
    const { database, databaseEngine, ...rest } = payload;
    const response = await apiClient.post('/sessions/quick-start', { ...rest, databaseEngine: databaseEngine ?? database, ...(databaseEngine && database ? { database } : {}) });
    return response.data;
  },

  async cancelSession(sessionId: string) {
    await apiClient.delete(`/sessions/${sessionId}`);
  },

  async changeExecutionMode(sessionId: string, executionMode: ExecutionMode) {
    return (await apiClient.patch(`/sessions/${sessionId}/execution-mode`, { executionMode })).data;
  },

  async verify(sessionId: string) {
    return (await apiClient.post(`/sessions/${sessionId}/verify`)).data;
  },

  async unblockManualRepair(sessionId: string, filePath: string, modifiedCode?: string, promptHint?: string) {
    const response = await apiClient.post(`/sessions/${sessionId}/manual-repair`, {
      sessionId,
      filePath,
      modifiedCode,
      guidanceHint: promptHint,
    });
    return response.data;
  },
};
