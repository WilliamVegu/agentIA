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
  timeout: 60000,
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
