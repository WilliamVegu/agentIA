import apiClient from './apiClient';

export interface ArchitectureDesignPayload {
  draft: any;
  apiKey?: string;
  provider?: string;
}

export interface ArchitectureRefinePayload {
  currentDesign: any;
  feedbackPrompt: string;
  targetComponent?: string;
  apiKey?: string;
  provider?: string;
}

export const architectureService = {
  async design(payload: ArchitectureDesignPayload) {
    const response = await apiClient.post('/architecture/design', payload);
    return response.data;
  },

  async refine(payload: ArchitectureRefinePayload) {
    const response = await apiClient.post('/architecture/refine', payload);
    return response.data;
  },
};
