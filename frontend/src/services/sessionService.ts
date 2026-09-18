import apiClient from './apiClient';

export interface QuickStartPayload {
  service_name: string;
  prompt?: string;
  raw_text?: string;
  database?: 'POSTGRESQL' | 'MYSQL' | 'H2';
  auto_run?: boolean;
  llm_provider?: string;
  api_key?: string;
}

export interface SessionListItem {
  sessionId: string;
  specId: string;
  specName: string;
  status: 'CREATED' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'BLOCKED';
  currentLifecyclePhase: string;
  lifecycleMode: string;
  completionPercentage: number;
  repairAttempts?: number;
  createdAt: string;
}

export interface SessionDetail {
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
    const response = await apiClient.post('/sessions/quick-start', payload);
    return response.data;
  },

  async cancelSession(sessionId: string) {
    await apiClient.delete(`/sessions/${sessionId}`);
  },

  async unblockManualRepair(sessionId: string, filePath: string, modifiedCode?: string, promptHint?: string) {
    const response = await apiClient.post(`/sessions/${sessionId}/manual-repair`, {
      sessionId,
      filePath,
      modifiedCode,
      promptHint,
    });
    return response.data;
  },
};
