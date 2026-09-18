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
  verifyConnection: () => Promise<boolean>;
}

export interface ModelOption {
  id: string;
  label: string;
  badge?: string;
  isDefault?: boolean;
}

export const RECOMMENDED_MODELS: Record<LlmProviderType, ModelOption[]> = {
  gemini: [
    { id: 'gemini-3.6-flash', label: 'Gemini 3.6 Flash', badge: 'Recomendado', isDefault: true },
    { id: 'gemini-3.5-flash-lite', label: 'Gemini 3.5 Flash Lite', badge: 'Rápido' },
    { id: 'gemini-3.8-flash', label: 'Gemini 3.8 Flash', badge: 'Avanzado' },
  ],
  groq: [
    { id: 'qwen/qwen3.8-27b', label: 'Qwen 3.8 27B', badge: 'Recomendado', isDefault: true },
    { id: 'openai/gpt-oss-120b', label: 'GPT-OSS 120B', badge: 'Potente' },
    { id: 'openai/gpt-oss-20b', label: 'GPT-OSS 20B', badge: 'Ligero' },
    { id: 'groq/compound', label: 'Groq Compound', badge: 'Compuesto' },
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
  gemini: 'gemini-3.6-flash',
  groq: 'qwen/qwen3.8-27b',
  openai: 'gpt-4o-mini',
  mock: 'offline-mock',
};

const LlmContext = createContext<LlmContextType | undefined>(undefined);

export const LlmProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [provider, setProviderState] = useState<LlmProviderType>('mock');
  const [apiKey, setApiKeyState] = useState<string>('');
  const [model, setModelState] = useState<string>(DEFAULT_MODELS.mock);
  const [isVerified, setIsVerified] = useState<boolean>(true);
  const [latencyMs, setLatencyMs] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>(
    'Modo offline (Mock Engine) activo. Generación sintética local sin consumo de red.'
  );
  const [isVerifying, setIsVerifying] = useState<boolean>(false);

  useEffect(() => {
    setEphemeralLlmCredentials(apiKey, provider);
  }, [apiKey, provider]);

  const setProvider = (p: LlmProviderType) => {
    setProviderState(p);
    setModelState(DEFAULT_MODELS[p] || 'default');
    if (p === 'mock') {
      setIsVerified(true);
      setLatencyMs(0);
      setStatusMessage('Modo offline (Mock Engine) activo.');
    } else {
      setIsVerified(false);
      setStatusMessage(`Proveedor ${p.toUpperCase()} seleccionado. Ingrese la API Key y verifique.`);
    }
  };

  const setApiKey = (k: string) => {
    setApiKeyState(k);
    setIsVerified(false);
  };

  const setModel = (m: string) => {
    setModelState(m);
  };

  const verifyConnection = async (): Promise<boolean> => {
    setIsVerifying(true);
    try {
      const res = await llmService.verifyConnection({
        apiKey,
        provider,
        model,
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
