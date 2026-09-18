import axios from 'axios';
import apiClient from './apiClient';

export interface VerifyLlmPayload {
  apiKey?: string;
  provider?: string;
  model?: string;
}

export interface VerifyLlmResponse {
  provider: string;
  model: string;
  status: 'CONNECTED' | 'READY' | 'ERROR';
  message: string;
  latencyMs: number;
}

export interface HealthCheckResponse {
  status: string;
  timestamp: string;
  app: string;
  version: string;
}

export const llmService = {
  async verifyConnection(payload: VerifyLlmPayload): Promise<VerifyLlmResponse> {
    const response = await apiClient.post<VerifyLlmResponse>('/llm/verify', payload);
    return response.data;
  },

  async checkHealth(): Promise<HealthCheckResponse> {
    const response = await axios.get<HealthCheckResponse>('/healthz');
    return response.data;
  },
};
