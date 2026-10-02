import axios from 'axios';

// Ephemeral in-memory storage for LLM credentials (Constitution Principle VI)
let ephemeralApiKey: string = localStorage.getItem('quarkus_llm_api_key') || '';
let ephemeralProvider: string = localStorage.getItem('quarkus_llm_provider') || 'mock';
let ephemeralModel: string = localStorage.getItem('quarkus_llm_model') || '';

export const setEphemeralLlmCredentials = (apiKey: string, provider: string, model?: string) => {
  ephemeralApiKey = apiKey || '';
  ephemeralProvider = provider || 'mock';
  ephemeralModel = model || '';
  if (apiKey) localStorage.setItem('quarkus_llm_api_key', apiKey);
  if (provider) localStorage.setItem('quarkus_llm_provider', provider);
  if (model) localStorage.setItem('quarkus_llm_model', model);
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
  timeout: 120000,
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
