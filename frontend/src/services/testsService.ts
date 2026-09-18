import apiClient from './apiClient';

export interface RepairIterationRecord {
  iteration: number;
  timestamp: string;
  sourceFile: string;
  testFile: string;
  compilerDiagnostic: string;
  diff: string;
  outcome: string;
  explanation: string;
}

export interface RepairHistoryResponse {
  sessionId: string;
  totalIterations: number;
  finalState: string;
  iterations: RepairIterationRecord[];
  canRetryManually: boolean;
  currentBlockedDiagnostic?: string;
}

export const testsService = {
  async getRepairHistory(sessionId: string): Promise<RepairHistoryResponse> {
    const response = await apiClient.get<RepairHistoryResponse>(`/sessions/${sessionId}/repairs`);
    return response.data;
  },

  async submitManualRepair(sessionId: string, filePath: string, modifiedCode?: string, promptHint?: string) {
    const response = await apiClient.post(`/sessions/${sessionId}/manual-repair`, {
      sessionId,
      filePath,
      modifiedCode,
      promptHint,
    });
    return response.data;
  },

  async synthesizeTests(specId: string) {
    const response = await apiClient.post('/tests/synthesize', { specId });
    return response.data;
  },
};
