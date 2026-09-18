import React, { useState } from 'react';
import {
  Rocket,
  Download,
  Database,
  Layers,
  FileCode,
  ShieldCheck,
  CheckCircle2,
  Clock,
  ArrowRight,
  Activity,
  Server,
  Play,
  Pause,
  Square,
  RefreshCw,
  AlertTriangle,
  PlusCircle,
} from 'lucide-react';
import { SingleRowCard } from '../components/common/SingleRowCard';
import { AssistedScrollBtn } from '../components/common/AssistedScrollBtn';
import { useStudio } from '../context/StudioContext';
import { useLlm } from '../context/LlmContext';
import { sessionService } from '../services/sessionService';
import { orchestratorService } from '../services/orchestratorService';

export const StudioOverviewView: React.FC = () => {
  const {
    activeSessionId,
    activeSession,
    projectOverview,
    lifecycle,
    refreshSessions,
    selectSession,
    startNewService,
    setActiveTab,
    reloadCurrentOverview,
    isQueued,
  } = useStudio();
  const { provider, apiKey } = useLlm();

  // Quick Start Form state
  const [serviceName, setServiceName] = useState('order-fulfillment-service');
  const [database, setDatabase] = useState<'POSTGRESQL' | 'MYSQL' | 'H2'>('POSTGRESQL');
  const [prompt, setPrompt] = useState(
    'Microservicio para procesamiento de órdenes de compra con persistencia en PostgreSQL, validación de inventario, auditoría de estados y endpoints REST con Java Records.'
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isPipelineWorking, setIsPipelineWorking] = useState(false);

  const handleCreateQuickStart = async (isAuto: boolean) => {
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const res = await sessionService.quickStart({
        service_name: serviceName.trim() || 'order-service',
        prompt: prompt.trim(),
        database: database,
        auto_run: isAuto,
        llm_provider: provider,
        api_key: apiKey,
      });

      await refreshSessions();
      if (res?.sessionId) {
        selectSession(res.sessionId);
        if (isAuto) {
          setActiveTab(5); // Switch to Monitor tab
        } else {
          setActiveTab(1); // Switch to Requirements tab
        }
      }
    } catch (err: any) {
      setSubmitError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          'Error al crear la sesión de microservicio'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDownloadBundle = () => {
    if (!activeSessionId) return;
    const url = orchestratorService.getExportBundleUrl(activeSessionId);
    window.open(url, '_blank');
  };

  const handlePausePipeline = async () => {
    if (!activeSessionId) return;
    setIsPipelineWorking(true);
    try {
      await orchestratorService.pausePipeline(activeSessionId);
      await Promise.all([reloadCurrentOverview(), refreshSessions()]);
    } catch {
      // Fallback
    } finally {
      setIsPipelineWorking(false);
    }
  };

  const handleResumePipeline = async () => {
    if (!activeSessionId) return;
    setIsPipelineWorking(true);
    try {
      await orchestratorService.resumePipeline(activeSessionId);
      await Promise.all([reloadCurrentOverview(), refreshSessions()]);
    } catch {
      // Fallback
    } finally {
      setIsPipelineWorking(false);
    }
  };

  const handleCancelPipeline = async () => {
    if (!activeSessionId) return;
    setIsPipelineWorking(true);
    try {
      await orchestratorService.cancelPipeline(activeSessionId);
      await Promise.all([reloadCurrentOverview(), refreshSessions()]);
    } catch {
      // Fallback
    } finally {
      setIsPipelineWorking(false);
    }
  };

  const handleStartAutopilot = async () => {
    if (!activeSessionId) return;
    setIsPipelineWorking(true);
    try {
      await orchestratorService.runPipeline({
        session_id: activeSessionId,
        api_key: apiKey,
        provider: provider,
        force: true,
      });
      await Promise.all([reloadCurrentOverview(), refreshSessions()]);
      setActiveTab(5);
    } catch {
      setActiveTab(5);
    } finally {
      setIsPipelineWorking(false);
    }
  };

  const handleContinueAssisted = () => {
    const nextTarget = lifecycle?.nextTargetPhase || 'SPECIFICATION';
    const tabMap: Record<string, number> = {
      SPECIFICATION: 1,
      STORIES: 1,
      ARCHITECTURE: 2,
      DATA_MODEL: 3,
      CODE_GENERATION: 5,
      SECURITY_AUDIT: 7,
      DEPLOYMENT: 8,
      VERIFIED: 9,
    };
    setActiveTab(tabMap[nextTarget] || 1);
  };

  const pipelineStatus =
    lifecycle?.pipelineStatus ||
    lifecycle?.pipeline_status ||
    activeSession?.status ||
    'IDLE';
  const isOutdated = lifecycle?.isOutdated || lifecycle?.is_outdated || false;
  const isCompleted =
    pipelineStatus === 'COMPLETED' ||
    (lifecycle?.completionPercentage && lifecycle.completionPercentage >= 100);

  return (
    <div className="space-y-6">
      {/* If No Active Session: Hero Quick Start Form */}
      {!activeSessionId ? (
        <div className="bg-gradient-to-r from-blue-900 via-slate-900 to-slate-950 rounded-2xl p-6 sm:p-8 text-white border border-blue-800/40 shadow-xl relative overflow-hidden">
          <div className="max-w-3xl space-y-4 relative z-10">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-400/30">
                <Rocket className="w-3.5 h-3.5" />
                <span>⚡ Nuevo Microservicio (Inicio Rápido 1-Click)</span>
              </span>
            </div>

            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Generación Autónoma de Microservicio Spring Boot 3
            </h2>

            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
              Crea un proyecto de microservicio completo con especificación, arquitectura en 4 capas, entidades JPA, código Spring Boot 3 y suites de prueba Mockito con un solo clic.
            </p>

            <div className="space-y-4 pt-2">
              {submitError && (
                <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-xs text-rose-200">
                  {submitError}
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Nombre del Microservicio
                  </label>
                  <input
                    type="text"
                    value={serviceName}
                    onChange={(e) => setServiceName(e.target.value)}
                    required
                    className="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-white text-xs font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Motor de Base de Datos
                  </label>
                  <select
                    value={database}
                    onChange={(e) => setDatabase(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-white text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  >
                    <option value="POSTGRESQL">PostgreSQL (Producción)</option>
                    <option value="MYSQL">MySQL 8.0</option>
                    <option value="H2">H2 In-Memory (Test)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Descripción de Requisitos / Prompt del Negocio
                </label>
                <textarea
                  rows={3}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  required
                  className="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-white text-xs leading-relaxed focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                <button
                  type="button"
                  onClick={() => handleCreateQuickStart(true)}
                  disabled={isSubmitting}
                  className="flex items-center justify-center gap-2 py-2.5 px-5 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 active:bg-blue-700 shadow-md transition-all disabled:opacity-50"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>⚡ Crear y Ejecutar Auto-Pilot Completo</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleCreateQuickStart(false)}
                  disabled={isSubmitting}
                  className="flex items-center justify-center gap-2 py-2.5 px-5 rounded-lg text-xs font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-all disabled:opacity-50"
                >
                  <span>👣 Crear e Iniciar Modo Asistido</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* When a Session is Active */
        <div className="space-y-6">
          {/* Active Microservice Header Card */}
          <div className="bg-gradient-to-r from-blue-900 via-slate-900 to-slate-950 rounded-2xl p-6 text-white border border-blue-800/40 shadow-xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-blue-400">
                  Microservicio Activo
                </span>
                <h2 className="text-2xl font-bold tracking-tight text-white mt-0.5">
                  ⚡ {activeSession?.specName || projectOverview?.serviceName || 'order-service'}
                </h2>
                <p className="text-xs text-slate-300 mt-1">
                  Java 21 LTS &nbsp;|&nbsp; Spring Boot 3.x &nbsp;|&nbsp; Base de Datos:{' '}
                  <strong>{projectOverview?.database || 'POSTGRESQL'}</strong> &nbsp;|&nbsp; Sesión:{' '}
                  <code className="text-blue-300 font-mono">{activeSessionId}</code>
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={startNewService}
                  className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg text-slate-200 bg-slate-800/90 hover:bg-slate-700 border border-slate-700 transition-colors shadow-sm"
                  title="Crear un nuevo microservicio desde cero"
                >
                  <PlusCircle className="w-3.5 h-3.5 text-blue-400" />
                  <span>Nuevo Microservicio</span>
                </button>
                <button
                  onClick={handleDownloadBundle}
                  className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg text-white bg-blue-600 hover:bg-blue-500 transition-colors shadow-sm"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Descargar Bundle Completo (ZIP)</span>
                </button>
              </div>
            </div>
          </div>

          {/* In-Flight Pipeline Alerts & Controls */}
          {pipelineStatus === 'RUNNING' && (
            <div className="p-4 rounded-xl bg-blue-50 dark:bg-blue-950/40 border border-blue-300 dark:border-blue-900 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-blue-900 dark:text-blue-100">
              <div className="flex items-center gap-2.5">
                <RefreshCw className="w-4 h-4 text-blue-600 animate-spin" />
                <span>
                  ⚡ <strong>Pipeline Auto-Pilot en ejecución</strong>: Las etapas se están generando de manera autónoma en segundo plano.
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handlePausePipeline}
                  disabled={isPipelineWorking}
                  className="py-1.5 px-3 rounded-lg bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700 text-xs font-semibold flex items-center gap-1 hover:bg-slate-50 transition-colors"
                >
                  <Pause className="w-3.5 h-3.5" />
                  <span>Pausar Pipeline</span>
                </button>
                <button
                  onClick={handleCancelPipeline}
                  disabled={isPipelineWorking}
                  className="py-1.5 px-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 border border-rose-300 dark:border-rose-900 text-xs font-semibold flex items-center gap-1 hover:bg-rose-100 transition-colors"
                >
                  <Square className="w-3.5 h-3.5" />
                  <span>Cancelar Pipeline</span>
                </button>
              </div>
            </div>
          )}

          {pipelineStatus === 'PAUSED' && (
            <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-900 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-amber-900 dark:text-amber-100">
              <div className="flex items-center gap-2.5">
                <Pause className="w-4 h-4 text-amber-600" />
                <span>
                  ⏸️ <strong>Pipeline Auto-Pilot en Pausa</strong>: La ejecución está suspendida temporalmente.
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleResumePipeline}
                  disabled={isPipelineWorking}
                  className="py-1.5 px-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-1 transition-colors"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Reanudar Pipeline</span>
                </button>
                <button
                  onClick={handleCancelPipeline}
                  disabled={isPipelineWorking}
                  className="py-1.5 px-3 rounded-lg bg-rose-50 text-rose-700 border border-rose-300 text-xs font-semibold flex items-center gap-1"
                >
                  <Square className="w-3.5 h-3.5" />
                  <span>Cancelar</span>
                </button>
              </div>
            </div>
          )}

          {isOutdated && (
            <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-900 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-amber-900 dark:text-amber-100">
              <div className="flex items-center gap-2.5">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <span>
                  ⚠️ Se detectaron cambios en etapas anteriores. Algunas etapas downstream están desactualizadas.
                </span>
              </div>
              <button
                onClick={handleStartAutopilot}
                disabled={isPipelineWorking}
                className="py-1.5 px-4 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold transition-colors"
              >
                🔄 Re-sincronizar y Regenerar Fases
              </button>
            </div>
          )}

          {/* Completed State Hero Container */}
          {isCompleted ? (
            <div className="p-6 rounded-2xl border border-emerald-300 dark:border-emerald-800 bg-emerald-50/70 dark:bg-emerald-950/30 space-y-4 shadow-sm">
              <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300 font-bold text-base">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                <span>🎉 ¡Microservicio completamente sintetizado y verificado con éxito!</span>
              </div>
              <p className="text-xs text-slate-700 dark:text-slate-300">
                Todos los artefactos para <strong>`{activeSession?.specName || 'order-service'}`</strong> están listos y validados: historias de usuario BDD, arquitectura en 4 capas, esquema SQL relacional, código Java 21 / Spring Boot 3, pruebas unitarias Mockito, auditoría SAST con Quality Gate APROBADO y manifiestos Docker / Kubernetes.
              </p>
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <button
                  onClick={() => setActiveTab(6)}
                  className="py-2 px-4 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 transition-all shadow-sm"
                >
                  🔍 Explorar Código Fuente (Tab 6)
                </button>
                <button
                  onClick={() => setActiveTab(7)}
                  className="py-2 px-4 rounded-lg text-xs font-semibold text-slate-800 dark:text-slate-200 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 transition-colors shadow-sm"
                >
                  🛡️ Ver Quality Gate & SAST (Tab 7)
                </button>
                <button
                  onClick={() => setActiveTab(9)}
                  className="py-2 px-4 rounded-lg text-xs font-semibold text-slate-800 dark:text-slate-200 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 transition-colors shadow-sm"
                >
                  📦 Descarga & Publicación Git (Tab 9)
                </button>
                <button
                  onClick={handleStartAutopilot}
                  disabled={isPipelineWorking}
                  className="py-2 px-4 rounded-lg text-xs font-semibold text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-950/40 border border-purple-300 dark:border-purple-800 hover:bg-purple-100 transition-colors ml-auto"
                >
                  🚀 Re-ejecutar Auto-Pilot Completo
                </button>
              </div>
            </div>
          ) : (
            /* Mode Selection Section when not completed */
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-6 rounded-2xl border-2 border-blue-500 dark:border-blue-700 bg-white dark:bg-slate-900 space-y-3 shadow-sm flex flex-col justify-between">
                <div>
                  <h4 className="text-sm font-bold text-blue-900 dark:text-blue-300">
                    🚀 Ejecutar Flujo Completo (Auto-Pilot)
                  </h4>
                  <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                    Genera el microservicio de principio a fin de forma 100% desatendida. Sintetiza historias, arquitectura, persistencia SQL, código Java, pruebas Mockito, auditoría SAST y contenedores Docker.
                  </p>
                </div>
                <button
                  onClick={handleStartAutopilot}
                  disabled={isPipelineWorking || pipelineStatus === 'RUNNING'}
                  className="w-full py-2.5 px-4 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-sm flex items-center justify-center gap-1.5"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Iniciar Auto-Pilot Ahora</span>
                </button>
              </div>

              <div className="p-6 rounded-2xl border-2 border-emerald-500 dark:border-emerald-700 bg-white dark:bg-slate-900 space-y-3 shadow-sm flex flex-col justify-between">
                <div>
                  <h4 className="text-sm font-bold text-emerald-900 dark:text-emerald-300">
                    👣 Modo Paso a Paso (Asistido)
                  </h4>
                  <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                    Avanza etapa por etapa revisando y aprobando cada artefacto de diseño antes de continuar. Ideal si deseas ajustar historias de usuario, diagramas de arquitectura o esquemas relacionales.
                  </p>
                </div>
                <button
                  onClick={handleContinueAssisted}
                  className="w-full py-2.5 px-4 rounded-lg text-xs font-semibold text-emerald-800 dark:text-emerald-200 bg-emerald-100 dark:bg-emerald-900/60 hover:bg-emerald-200 transition-colors shadow-sm flex items-center justify-center gap-1.5"
                >
                  <span>Continuar en Modo Asistido →</span>
                </button>
              </div>
            </div>
          )}

          {/* 5 Milestone Metrics Grid */}
          <div className="space-y-3">
            <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight">
              📊 Métricas Clave del Microservicio
            </h3>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs shadow-sm">
                <span className="text-slate-500 font-medium">Historias BDD</span>
                <div className="text-2xl font-bold font-mono text-slate-900 dark:text-white mt-1">
                  {projectOverview?.totalStories || 4}
                </div>
                <span className="text-[11px] text-slate-500">Criterios G/W/T</span>
              </div>

              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs shadow-sm">
                <span className="text-slate-500 font-medium">Entidades SQL</span>
                <div className="text-2xl font-bold font-mono text-slate-900 dark:text-white mt-1">
                  {projectOverview?.totalEntities || 2}
                </div>
                <span className="text-[11px] text-slate-500">Tablas relacionales</span>
              </div>

              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs shadow-sm">
                <span className="text-slate-500 font-medium">Suites de Tests</span>
                <div className="text-base font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-2">
                  ✅ Aprobadas
                </div>
                <span className="text-[11px] text-slate-500">Mockito & WebMvc</span>
              </div>

              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs shadow-sm">
                <span className="text-slate-500 font-medium">Quality Gate</span>
                <div className="text-base font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-2">
                  ✅ APROBADO
                </div>
                <span className="text-[11px] text-slate-500">Puntaje: {projectOverview?.qualityScore || 95}/100</span>
              </div>

              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs shadow-sm">
                <span className="text-slate-500 font-medium">Despliegue</span>
                <div className="text-base font-bold font-mono text-blue-600 dark:text-blue-400 mt-2 truncate">
                  {projectOverview?.deploymentStatus || 'RUNNING'}
                </div>
                <span className="text-[11px] text-slate-500">Puerto :8080</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
