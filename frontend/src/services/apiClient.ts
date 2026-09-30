import axios from 'axios';

// Ephemeral in-memory storage for LLM credentials (Constitution Principle VI)
let ephemeralApiKey: string = '';
let ephemeralProvider: string = 'mock';
let ephemeralModel: string = '';

export const setEphemeralLlmCredentials = (apiKey: string, provider: string, model?: string) => {
  ephemeralApiKey = apiKey || '';
  ephemeralProvider = provider || 'mock';
  ephemeralModel = model || '';
};

export const getEphemeralLlmCredentials = () => ({
  apiKey: ephemeralApiKey,
  provider: ephemeralProvider,
  model: ephemeralModel,
});

export const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000,
});

apiClient.interceptors.request.use((config) => {
  if (ephemeralApiKey) {
    config.headers['X-LLM-API-Key'] = ephemeralApiKey;
  }
  if (ephemeralProvider) {
    config.headers['X-LLM-Provider'] = ephemeralProvider;
  }
  if (ephemeralModel) {
    config.headers['X-LLM-Model'] = ephemeralModel;
  }
  return config;
});

export default apiClient;
