import apiClient from './apiClient';

export interface TransformRequirementsPayload {
  naturalLanguageText: string;
  serviceName?: string;
  apiKey?: string;
  provider?: string;
}

export interface RefineRequirementsPayload {
  specificationDraft: any;
  refinementPrompt: string;
  apiKey?: string;
  provider?: string;
}

export const requirementsService = {
  async transform(payload: TransformRequirementsPayload) {
    const response = await apiClient.post('/requirements/transform', {
      rawText: payload.naturalLanguageText,
      serviceName: payload.serviceName,
      apiKey: payload.apiKey,
      provider: payload.provider,
    });
    return response.data;
  },

  async refine(payload: RefineRequirementsPayload) {
    const response = await apiClient.post('/requirements/refine', {
      currentDraft: payload.specificationDraft,
      feedbackPrompt: payload.refinementPrompt,
      apiKey: payload.apiKey,
      provider: payload.provider,
    });
    return response.data;
  },

  async getSessionRequirements(sessionId: string) {
    const response = await apiClient.get(`/requirements/sessions/${sessionId}`);
    return response.data;
  },

  async saveSessionRequirements(sessionId: string, draft: any) {
    const response = await apiClient.post(`/requirements/sessions/${sessionId}/save`, draft);
    return response.data;
  },

  async exportSpecMarkdown(draft: any) {
    const response = await apiClient.post('/requirements/export-spec', draft);
    return response.data;
  },
};
