import React, { useState } from 'react';
import { Key, Cpu, ShieldCheck, Check, AlertCircle, RefreshCw } from 'lucide-react';
import { SlideOverDrawer } from '../common/SlideOverDrawer';
import { useLlm, RECOMMENDED_MODELS } from '../../context/LlmContext';
import { LlmProviderType } from '../../types';

interface SettingsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsDrawer: React.FC<SettingsDrawerProps> = ({ isOpen, onClose }) => {
  const {
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
  } = useLlm();

  const [localKey, setLocalKey] = useState(apiKey);
  const [showKey, setShowKey] = useState(false);

  const handleProviderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setProvider(e.target.value as LlmProviderType);
  };

  const handleSaveAndVerify = async () => {
    setApiKey(localKey);
    await verifyConnection();
  };

  return (
    <SlideOverDrawer
      isOpen={isOpen}
      onClose={onClose}
      title="Configuración del Motor LLM"
      subtitle="Credenciales efímeras en memoria (Constitución Principio VI)"
    >
      <div className="space-y-6">
        {/* Banner informativo de seguridad */}
        <div className="p-3.5 rounded-xl bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900/60 flex items-start gap-3 text-xs text-blue-900 dark:text-blue-200">
          <ShieldCheck className="w-5 h-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold block mb-0.5">Seguridad Empresarial TCS</span>
            Las claves de API se mantienen exclusivamente en la memoria de la sesión actual y nunca se escriben en disco, logs ni base de datos.
          </div>
        </div>

        {/* Proveedor */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2">
            Proveedor de Inteligencia Artificial
          </label>
          <select
            value={provider}
            onChange={handleProviderChange}
            className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
          >
            <option value="mock">Modo Offline (Mock Engine - Sin Costo)</option>
            <option value="gemini">Google Gemini (Gemini 3.6 Flash / 3.5 Lite)</option>
            <option value="groq">Groq Cloud (Qwen 3.8 27B / GPT-OSS)</option>
            <option value="openai">OpenAI (GPT-4o-mini / GPT-4o)</option>
          </select>
        </div>

        {/* Clave API */}
        {provider !== 'mock' && (
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2">
              Clave de API ({provider.toUpperCase()})
            </label>
            <div className="relative">
              <input
                type={showKey ? 'text' : 'password'}
                value={localKey}
                onChange={(e) => setLocalKey(e.target.value)}
                placeholder={provider === 'gemini' ? 'AQ... o AIzaSy...' : provider === 'groq' ? 'gsk_...' : 'sk-...'}
                className="w-full px-3 py-2 pr-16 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-2 top-2 text-[11px] text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 px-1"
              >
                {showKey ? 'Ocultar' : 'Ver'}
              </button>
            </div>
          </div>
        )}

        {/* Modelo */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Modelo Designado
          </label>
          <input
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="ej. gemini-3.6-flash o qwen/qwen3.8-27b"
            className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />

          {/* Quick-pick recommended model pills */}
          {RECOMMENDED_MODELS[provider] && RECOMMENDED_MODELS[provider].length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {RECOMMENDED_MODELS[provider].map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setModel(opt.id)}
                  className={`text-[10px] px-2 py-1 rounded-md border font-mono transition-colors ${
                    model === opt.id
                      ? 'bg-blue-50 dark:bg-blue-900/40 border-blue-400 text-blue-700 dark:text-blue-300 font-semibold shadow-xs'
                      : 'bg-slate-50 dark:bg-slate-800/80 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-slate-300 hover:text-slate-800 dark:hover:text-slate-200'
                  }`}
                >
                  {opt.label} {opt.badge && <span className="opacity-75 text-[9px]">({opt.badge})</span>}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Estado y Latencia */}
        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs">
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              Estado de la Conexión
            </span>
            <span
              className={`inline-flex items-center gap-1 font-semibold ${
                isVerified
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : 'text-amber-600 dark:text-amber-400'
              }`}
            >
              {isVerified ? (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>CONECTADO ({latencyMs}ms)</span>
                </>
              ) : (
                <>
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>NO VERIFICADO</span>
                </>
              )}
            </span>
          </div>
          <p className="text-slate-500 dark:text-slate-400 text-[11px]">
            {statusMessage}
          </p>
        </div>

        {/* Botón de acción */}
        <div className="pt-2 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            Cerrar
          </button>
          <button
            type="button"
            onClick={handleSaveAndVerify}
            disabled={isVerifying}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {isVerifying ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Verificando...</span>
              </>
            ) : (
              <>
                <Key className="w-3.5 h-3.5" />
                <span>Guardar y Probar Conexión</span>
              </>
            )}
          </button>
        </div>
      </div>
    </SlideOverDrawer>
  );
};
