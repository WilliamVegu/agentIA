import axios from 'axios';

// Ephemeral in-memory storage for LLM credentials (Constitution Principle VI)
let ephemeralApiKey: string = '';
let ephemeralProvider: string = 'mock';

export const setEphemeralLlmCredentials = (apiKey: string, provider: string) => {
  ephemeralApiKey = apiKey || '';
  ephemeralProvider = provider || 'mock';
};

export const getEphemeralLlmCredentials = () => ({
  apiKey: ephemeralApiKey,
  provider: ephemeralProvider,
});

export const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  // LLM-backed endpoints (requirements transform, architecture design, model
  // synthesis, code generation) can legitimately exceed 60s — DeepSeek is given a
  // 120s window server-side. A 60s client cap cut those calls off with "timeout of
  // 60000ms exceeded" before the server could answer. 300s gives generation headroom
  // while still bounding a genuinely hung request.
  timeout: 300000,
});

apiClient.interceptors.request.use((config) => {
  if (ephemeralApiKey) {
    config.headers['X-LLM-API-Key'] = ephemeralApiKey;
  }
  if (ephemeralProvider) {
    config.headers['X-LLM-Provider'] = ephemeralProvider;
  }
  return config;
});

export default apiClient;
