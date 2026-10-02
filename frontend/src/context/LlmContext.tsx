import React, { createContext, useContext, useState, useEffect } from 'react';
import { LlmProviderType } from '../types';
import { setEphemeralLlmCredentials } from '../services/apiClient';
import { llmService } from '../services/llmService';

interface LlmContextType {
  provider: LlmProviderType;
  apiKey: string;
  model: string;
  isVerified: boolean;
  latencyMs: number;
  statusMessage: string;
  isVerifying: boolean;
  setProvider: (p: LlmProviderType) => void;
  setApiKey: (k: string) => void;
  setModel: (m: string) => void;
  verifyConnection: (overrideKey?: string, overrideProvider?: LlmProviderType, overrideModel?: string) => Promise<boolean>;
}

export interface ModelOption {
  id: string;
  label: string;
  badge?: string;
  isDefault?: boolean;
}

export const RECOMMENDED_MODELS: Record<LlmProviderType, ModelOption[]> = {
  deepseek: [
    { id: 'deepseek-chat', label: 'DeepSeek-V3 (Chat)', badge: 'Recomendado', isDefault: true },
    { id: 'deepseek-reasoner', label: 'DeepSeek-R1 (Reasoner)', badge: 'Razonamiento' },
  ],
  gemini: [
    { id: 'gemini-3.5-flash-lite', label: 'Gemini 3.5 Flash Lite', badge: 'Ultra-Rápido', isDefault: true },
    { id: 'gemini-3.5-flash', label: 'Gemini 3.5 Flash', badge: 'Recomendado' },
    { id: 'gemini-3.8-flash', label: 'Gemini 3.8 Flash', badge: 'Estándar' },
  ],
  groq: [
    { id: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B', badge: 'Recomendado', isDefault: true },
    { id: 'llama-3.1-8b-instant', label: 'Llama 3.1 8B', badge: 'Rápido' },
    { id: 'mixtral-8x7b-32768', label: 'Mixtral 8x7B', badge: 'Potente' },
  ],
  openai: [
    { id: 'gpt-4o-mini', label: 'GPT-4o Mini', badge: 'Recomendado', isDefault: true },
    { id: 'gpt-4o', label: 'GPT-4o', badge: 'Avanzado' },
  ],
  mock: [
    { id: 'offline-mock', label: 'Mock Engine', badge: 'Offline', isDefault: true },
  ],
};

export const DEFAULT_MODELS: Record<LlmProviderType, string> = {
  deepseek: 'deepseek-chat',
  gemini: 'gemini-3.5-flash-lite',
  groq: 'llama-3.3-70b-versatile',
  openai: 'gpt-4o-mini',
  mock: 'offline-mock',
};

const LlmContext = createContext<LlmContextType | undefined>(undefined);

export const LlmProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const initialProvider = (localStorage.getItem('quarkus_llm_provider') as LlmProviderType) || 'mock';
  const initialApiKey = localStorage.getItem('quarkus_llm_api_key') || '';
  const savedModel = localStorage.getItem('quarkus_llm_model');
  const initialModel = (savedModel === 'gemini-1.5-flash' || !savedModel ? DEFAULT_MODELS[initialProvider] : savedModel) || DEFAULT_MODELS.mock;

  const [provider, setProviderState] = useState<LlmProviderType>(initialProvider);
  const [apiKey, setApiKeyState] = useState<string>(initialApiKey);
  const [model, setModelState] = useState<string>(initialModel);
  const [isVerified, setIsVerified] = useState<boolean>(initialProvider === 'mock' || !!initialApiKey);
  const [latencyMs, setLatencyMs] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>(
    initialProvider === 'mock'
      ? 'Modo offline (Mock Engine) activo. Generación sintética local sin consumo de red.'
      : `Proveedor ${initialProvider.toUpperCase()} activo (${initialModel}).`
  );
  const [isVerifying, setIsVerifying] = useState<boolean>(false);

  useEffect(() => {
    setEphemeralLlmCredentials(apiKey, provider, model);
  }, [apiKey, provider, model]);

  const setProvider = (p: LlmProviderType) => {
    setProviderState(p);
    localStorage.setItem('quarkus_llm_provider', p);
    const defModel = DEFAULT_MODELS[p] || 'default';
    setModelState(defModel);
    localStorage.setItem('quarkus_llm_model', defModel);
    if (p === 'mock') {
      setIsVerified(true);
      setLatencyMs(0);
      setStatusMessage('Modo offline (Mock Engine) activo.');
    } else {
      setIsVerified(!!apiKey);
      setStatusMessage(`Proveedor ${p.toUpperCase()} seleccionado. Ingrese la API Key y verifique.`);
    }
  };

  const setApiKey = (k: string) => {
    setApiKeyState(k);
    localStorage.setItem('quarkus_llm_api_key', k);
    setIsVerified(false);
  };

  const setModel = (m: string) => {
    setModelState(m);
    localStorage.setItem('quarkus_llm_model', m);
  };

  const verifyConnection = async (
    overrideKey?: string,
    overrideProvider?: LlmProviderType,
    overrideModel?: string
  ): Promise<boolean> => {
    const keyToUse = overrideKey !== undefined ? overrideKey : apiKey;
    const providerToUse = overrideProvider !== undefined ? overrideProvider : provider;
    const modelToUse = overrideModel !== undefined ? overrideModel : model;

    setIsVerifying(true);
    try {
      const res = await llmService.verifyConnection({
        apiKey: keyToUse,
        provider: providerToUse,
        model: modelToUse,
      });
      setIsVerified(res.status === 'CONNECTED' || res.status === 'READY');
      setLatencyMs(res.latencyMs || 0);
      setStatusMessage(res.message);
      return res.status === 'CONNECTED' || res.status === 'READY';
    } catch (err: any) {
      setIsVerified(false);
      setStatusMessage(err.response?.data?.message || err.message || 'Error validando conexión con LLM');
      return false;
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <LlmContext.Provider
      value={{
        provider,
        apiKey,
        model,
        isVerified,
        latencyMs,
        statusMessage,
        isVerifying,
        setProvider,
        setApiKey,
        setModel,
        verifyConnection,
      }}
    >
      {children}
    </LlmContext.Provider>
  );
};

export const useLlm = () => {
  const context = useContext(LlmContext);
  if (!context) {
    throw new Error('useLlm must be used within an LlmProvider');
  }
  return context;
};
