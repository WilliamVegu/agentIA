import apiClient from './apiClient';

export interface TransformRequirementsPayload {
  naturalLanguageText: string;
  serviceName?: string;
  apiKey?: string;
  provider?: string;
  modelName?: string;
  model?: string;
}

export interface RefineRequirementsPayload {
  specificationDraft: any;
  refinementPrompt: string;
  apiKey?: string;
  provider?: string;
  modelName?: string;
  model?: string;
}

export const requirementsService = {
  async transform(payload: TransformRequirementsPayload) {
    const response = await apiClient.post('/requirements/transform', {
      rawText: payload.naturalLanguageText,
      serviceName: payload.serviceName,
      apiKey: payload.apiKey,
      provider: payload.provider,
      modelName: payload.modelName || payload.model,
    });
    return response.data;
  },

  async refine(payload: RefineRequirementsPayload) {
    const response = await apiClient.post('/requirements/refine', {
      currentDraft: payload.specificationDraft,
      feedbackPrompt: payload.refinementPrompt,
      apiKey: payload.apiKey,
      provider: payload.provider,
      modelName: payload.modelName || payload.model,
    });
    return response.data;
  },

  async getSessionRequirements(sessionId: string) {
    const response = await apiClient.get(`/requirements/sessions/${sessionId}`);
    return response.data;
  },

  async saveSessionRequirements(sessionId: string, draft: any, expectedRevisionId?: string | null, expectedVersion?: number) {
    const response = await apiClient.post(`/requirements/sessions/${sessionId}/save`, draft, { params: { expectedRevisionId: expectedRevisionId ?? undefined, expectedVersion } });
    return response.data;
  },

  async approveSessionRequirements(sessionId: string, revisionId: string, expectedVersion?: number) {
    const response = await apiClient.post(`/requirements/sessions/${sessionId}/approve`, null, { params: { revisionId, expectedVersion } });
    return response.data;
  },

  async prepareRegeneration(sessionId: string, revisionId: string) {
    const response = await apiClient.post(`/requirements/sessions/${sessionId}/regenerate`, null,
      { params: { revisionId, confirmBackup: true } });
    return response.data;
  },

  async exportSpecMarkdown(draft: any) {
    const response = await apiClient.post('/requirements/export-spec', draft);
    return response.data;
  },
};
