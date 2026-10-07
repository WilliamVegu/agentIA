import apiClient from './apiClient';

/**
 * Mirrors the `/orchestrator/sessions/{id}/overview` payload field for field.
 *
 * It previously declared `serviceName`, `database`, `totalStories`, `totalEntities`,
 * `totalEndpoints`, `testSuitesCount`, `qualityGateStatus`, `qualityScore`,
 * `activePhase` and `completionPercentage` -- and the API returns **none of those**.
 * `deploymentStatus` was the only name that matched. Every card in the studio overview
 * therefore read `undefined` and rendered its fallback literal instead: "✅ Aprobado",
 * "Puntaje: 95/100", "RUNNING", "4 historias", "2 entidades". The numbers looked
 * measured; none of them were read from anywhere.
 *
 * Verified against a live response before changing it.
 */
export interface ProjectOverview {
  sessionId: string;
  specName?: string;
  databaseEngine?: string;
  framework?: string;
  userStoriesCount?: number;
  entitiesCount?: number;
  /** Whether the generated test suite passed. Present on the real payload. */
  testsPassed?: boolean;
  testsExecuted?: boolean;
  /** `PASS` / `BLOCKED` from the security audit. */
  securityAuditVerdict?: string;
  deploymentStatus?: string;
  deploymentUrl?: string;
  pipelineStatus?: string;
  lifecycle?: Record<string, unknown>;
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
