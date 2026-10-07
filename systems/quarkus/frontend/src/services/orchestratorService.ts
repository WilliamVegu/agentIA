import apiClient from './apiClient';

export interface ProjectOverview {
  sessionId: string;
  serviceName: string;
  database: string;
  totalStories: number;
  totalEntities: number;
  totalEndpoints: number;
  testSuitesCount: number;
  qualityGateStatus: string;
  qualityScore: number;
  deploymentStatus: string;
  activePhase: string;
  completionPercentage: number;
}

export interface PhaseTransitionPayload {
  target_phase: string;
  force?: boolean;
}

export interface PipelineRunPayload {
  session_id: string;
  target_phase?: string;
  stop_on_gate?: boolean;
  auto_deploy?: boolean;
  api_key?: string;
  provider?: string;
  model?: string;
  force?: boolean;
}

export const orchestratorService = {
  async getOverview(sessionId: string): Promise<ProjectOverview> {
    const response = await apiClient.get(`/orchestrator/sessions/${sessionId}/overview`);
    return response.data;
  },

  async getLifecycle(sessionId: string) {
    const response = await apiClient.get(`/orchestrator/sessions/${sessionId}/lifecycle`);
    return response.data;
  },

  async transitionPhase(sessionId: string, payload: PhaseTransitionPayload) {
    const response = await apiClient.post(`/orchestrator/sessions/${sessionId}/transition`, payload);
    return response.data;
  },

  async invalidateDownstream(sessionId: string, modifiedPhase: string) {
    const response = await apiClient.post(`/orchestrator/sessions/${sessionId}/invalidate`, {
      modifiedPhase,
    });
    return response.data;
  },

  async runPipeline(payload: PipelineRunPayload) {
    const response = await apiClient.post('/orchestrator/pipeline/run', payload);
    return response.data;
  },

  async pausePipeline(sessionId: string) {
    const response = await apiClient.post(`/orchestrator/pipeline/${sessionId}/pause`);
    return response.data;
  },

  async resumePipeline(sessionId: string) {
    const response = await apiClient.post(`/orchestrator/pipeline/${sessionId}/resume`);
    return response.data;
  },

  async cancelPipeline(sessionId: string) {
    const response = await apiClient.post(`/orchestrator/pipeline/${sessionId}/cancel`);
    return response.data;
  },

  getExportBundleUrl(sessionId: string) {
    return `/api/v1/orchestrator/sessions/${sessionId}/export-bundle`;
  },
};
