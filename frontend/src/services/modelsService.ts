import apiClient from './apiClient';

export interface ModelSqlGeneratePayload {
  draft: any;
  apiKey?: string;
  provider?: string;
}

export interface ModelSqlRefinePayload {
  currentResponse: any;
  feedbackPrompt: string;
  targetEntity?: string;
  apiKey?: string;
  provider?: string;
  modelName?: string;
}

export const modelsService = {
  async generate(payload: ModelSqlGeneratePayload) {
    const response = await apiClient.post('/models/generate', payload);
    return response.data;
  },

  async refine(payload: ModelSqlRefinePayload) {
    const response = await apiClient.post('/models/refine', payload);
    return response.data;
  },
};
