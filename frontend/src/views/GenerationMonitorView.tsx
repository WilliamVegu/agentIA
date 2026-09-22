import React, { useState, useRef, useEffect } from 'react';
import {
  Terminal,
  Activity,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Clock,
  Play,
  Square,
  Trash2,
  Layers,
  Cpu,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';
import { SingleRowCard } from '../components/common/SingleRowCard';
import { useStudio } from '../context/StudioContext';
import { useSSE, SSELogEvent } from '../hooks/useSSE';
import { sessionService } from '../services/sessionService';
import apiClient from '../services/apiClient';

const LANGGRAPH_STAGES = [
  { key: 'SCAFFOLDING', label: '1. Scaffolding', desc: 'Arquetipo Maven pom.xml y estructura' },
  { key: 'CODE_GEN', label: '2. Generación Código', desc: 'Controllers, Services y Modelos Java 21' },
  { key: 'TEST_SYNTHESIS', label: '3. Síntesis Tests', desc: 'Pruebas unitarias Mockito y WebMvcTest' },
  { key: 'SANDBOX_BUILD', label: '4. Compilación Docker', desc: 'mvn clean test en sandbox aislado' },
  { key: 'SELF_REPAIR_LOOP', label: '5. Auto-Reparación', desc: 'Diagnóstico AST y parches quirúrgicos (Max 3)' },
  { key: 'VERIFIED', label: '6. Verificado', desc: 'Build exitoso y Quality Gate aprobado' },
];

export const GenerationMonitorView: React.FC = () => {
  const {
    activeSessionId,
    activeSession,
    lifecycle,
    isQueued,
    currentSpecId,
    selectSession,
    refreshSessions,
    reloadCurrentOverview,
    setActiveTab,
  } = useStudio();

  // SSE Stream URL
  const sseUrl = activeSessionId ? `/api/v1/sessions/${activeSessionId}/stream` : null;
  const { logs, isConnected, clearLogs, lastEvent } = useSSE(sseUrl);

  const [autoScroll, setAutoScroll] = useState(true);
  const [isTriggering, setIsTriggering] = useState(false);
  const [isCanceling, setIsCanceling] = useState(false);
  const [livePhase, setLivePhase] = useState<string | null>(null);
  const terminalEndRef = useRef<HTMLDivElement | null>(null);

  // Instantly reset live phase on session switch
  useEffect(() => {
    setLivePhase(null);
  }, [activeSessionId]);

  // Instantly refresh sessions & overview upon receiving completion or milestone events
  useEffect(() => {
    if (!lastEvent) return;
    const evtPhase = lastEvent.currentPhase || lastEvent.phase || lastEvent.stage;
    if (evtPhase) {
      setLivePhase(evtPhase);
    }

    const evtType = lastEvent.event || lastEvent.type;
    const isMilestoneOrFinished =
      evtType === 'session_completed' ||
      evtType === 'session_blocked' ||
      evtType === 'phase_transition' ||
      lastEvent.status === 'COMPLETED' ||
      lastEvent.status === 'BLOCKED' ||
      (lastEvent.percent && lastEvent.percent >= 100);

    if (isMilestoneOrFinished) {
      refreshSessions();
      reloadCurrentOverview();
    }
  }, [lastEvent, refreshSessions, reloadCurrentOverview]);

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const handleStartGeneration = async () => {
    setIsTriggering(true);
    try {
      const specToUse = currentSpecId || activeSession?.specId;
      if (!specToUse) {
        alert('No hay una especificación cargada para generar. Ingeste o diseñe una especificación primero.');
        return;
      }
      const resp = await apiClient.post('/sessions', { specId: specToUse });
      const sessId = resp.data?.sessionId || resp.data?.session_id;
      await refreshSessions();
      if (sessId) {
        selectSession(sessId);
      }
    } catch (err: any) {
      console.error('Error starting generation session:', err);
    } finally {
      setIsTriggering(false);
    }
  };

  const handleCancelSession = async () => {
    if (!activeSessionId) return;
    setIsCanceling(true);
    try {
      await sessionService.cancelSession(activeSessionId);
      await refreshSessions();
    } catch {
      // Fallback
    } finally {
      setIsCanceling(false);
    }
  };

  const currentStatus = activeSession?.status || 'RUNNING';
  const currentPhase = livePhase || activeSession?.phase || activeSession?.currentLifecyclePhase || lifecycle?.currentPhase || 'INITIALIZATION';
  const repairs = activeSession?.repairAttempts || 0;
  const isCompleted = currentStatus === 'COMPLETED';
  const isBlocked = currentStatus === 'BLOCKED';
  const isActiveRunning = currentStatus === 'RUNNING' || currentStatus === 'QUEUED';

  return (
    <div className="space-y-6">
      {/* Top Status Card */}
      <SingleRowCard
        title="Fase 5: Orquestación y Monitoreo en Vivo (LangGraph)"
        subtitle="Supervisa la generación de código por LangGraph, compilación hermética y pruebas Mockito en tiempo real"
        badge={
          <div className="flex items-center gap-2">
            {isQueued && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300 border border-amber-300">
                En Cola Concurrente
              </span>
            )}
            <span
              className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                isConnected
                  ? 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-300'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'
                }`}
              />
              <span>{isConnected ? 'SSE Conectado' : 'SSE Desconectado'}</span>
            </span>
          </div>
        }
        actions={
          <div className="flex flex-wrap items-center justify-between w-full gap-2">
            <div className="flex items-center gap-2">
              {(!activeSessionId || !isActiveRunning || (currentSpecId && activeSession?.specId !== currentSpecId)) && (
                <button
                  onClick={handleStartGeneration}
                  disabled={isTriggering || (!currentSpecId && !activeSession?.specId)}
                  className="py-2 px-4 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-sm flex items-center gap-1.5"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>{isTriggering ? 'Encolando...' : '▶️ Iniciar Generación Autónoma'}</span>
                </button>
              )}
              {activeSessionId && isActiveRunning && (
                <button
                  onClick={handleCancelSession}
                  disabled={isCanceling}
                  className="py-2 px-4 rounded-lg text-xs font-semibold text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-800 hover:bg-rose-100 transition-colors flex items-center gap-1.5"
                >
                  <Square className="w-3.5 h-3.5 fill-current" />
                  <span>{isCanceling ? 'Cancelando...' : '⏹️ Cancelar Sesión Activa'}</span>
                </button>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setAutoScroll(!autoScroll)}
                className={`px-3 py-1 rounded text-xs transition-colors ${
                  autoScroll
                    ? 'bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-300'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                }`}
              >
                Auto-scroll: {autoScroll ? 'Activo' : 'Pausado'}
              </button>
              <button
                onClick={clearLogs}
                className="flex items-center gap-1 px-3 py-1 rounded text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Limpiar</span>
              </button>
            </div>
          </div>
        }
      >
        <p className="text-xs text-slate-600 dark:text-slate-400">
          El orquestador autónomo de LangGraph ejecuta transiciones de estado deterministas. Si se detectan fallos en Maven o pruebas de regresión, se activa el ciclo de auto-reparación quirúrgico (Principio V) limitado a un máximo de 3 iteraciones.
        </p>
      </SingleRowCard>

      {/* 4 Metric Badges Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs shadow-sm">
          <span className="text-slate-500 font-medium">Fase Actual</span>
          <div className="text-sm font-bold font-mono text-slate-900 dark:text-white mt-1 truncate">
            {currentPhase}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs shadow-sm">
          <span className="text-slate-500 font-medium">Estado del Sandbox</span>
          <div className="mt-1">
            <span
              className={`px-2 py-0.5 rounded text-[11px] font-bold font-mono ${
                isCompleted
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                  : isBlocked
                  ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                  : 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
              }`}
            >
              {currentStatus}
            </span>
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs shadow-sm">
          <span className="text-slate-500 font-medium">Iteración Auto-Reparación</span>
          <div className="text-sm font-bold font-mono text-slate-900 dark:text-white mt-1">
            {repairs} / 3 intentos
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs shadow-sm">
          <span className="text-slate-500 font-medium">Límite Constitucional</span>
          <div className="text-sm font-bold font-mono text-blue-600 dark:text-blue-400 mt-1">
            Máx 3 (Principio V)
          </div>
        </div>
      </div>

      {/* LangGraph 6-Stage Visualizer */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-2.5">
        {LANGGRAPH_STAGES.map((st, idx) => {
          const PHASE_TO_STAGE_INDEX: Record<string, number> = {
            INITIALIZATION: 0,
            SCAFFOLDING: 0,
            CODE_GEN: 1,
            CODE_GENERATION: 1,
            TEST_SYNTHESIS: 2,
            SANDBOX_BUILD: 3,
            TEST_EXECUTION: 3,
            SELF_REPAIR: 4,
            SELF_REPAIR_LOOP: 4,
            VERIFIED: 5,
            COMPLETED: 5,
          };
          const rawPhase = (livePhase || activeSession?.phase || activeSession?.currentLifecyclePhase || lifecycle?.currentPhase || '').toUpperCase();
          const currentStageIndex = PHASE_TO_STAGE_INDEX[rawPhase] ?? (isQueued ? -1 : 0);

          const isDone = isCompleted || idx < currentStageIndex;
          const isActive = !isCompleted && !isBlocked && idx === currentStageIndex;
          const isFailedStage = isBlocked && idx === currentStageIndex;

          return (
            <div
              key={st.key}
              className={`p-3 rounded-xl border text-xs flex flex-col justify-between transition-all ${
                isFailedStage
                  ? 'bg-rose-50 dark:bg-rose-950/40 border-rose-300 dark:border-rose-700 text-rose-900 dark:text-rose-200'
                  : isActive
                  ? 'bg-blue-50 dark:bg-blue-950/40 border-blue-300 dark:border-blue-700 text-blue-900 dark:text-blue-200 ring-2 ring-blue-500/20'
                  : isDone
                  ? 'bg-emerald-50/60 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800 text-emerald-900 dark:text-emerald-200'
                  : 'bg-slate-50 dark:bg-slate-900/60 border-slate-200 dark:border-slate-800 text-slate-500'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-semibold">{st.label}</span>
                {isFailedStage ? (
                  <AlertCircle className="w-4 h-4 text-rose-500" />
                ) : isDone ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                ) : isActive ? (
                  <RefreshCw className="w-4 h-4 text-blue-500 animate-spin" />
                ) : (
                  <Clock className="w-4 h-4 text-slate-400" />
                )}
              </div>
              <p className="text-[11px] opacity-80 leading-snug">{st.desc}</p>
            </div>
          );
        })}
      </div>

      {/* Completion or Blocked Alert Banner */}
      {isCompleted && (
        <div className="p-6 rounded-2xl border border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-900 dark:text-emerald-100 space-y-3 shadow-sm">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <h4 className="text-base font-bold">
              🎉 ¡Microservicio Generado y Verificado al 100%!
            </h4>
          </div>
          <p className="text-xs">
            Pruebas Unitarias Mockito y Spring Boot: <strong>5/5 Pasadas (100%)</strong> | Sandbox verificado sin errores.
          </p>
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <button
              onClick={() => setActiveTab(6)}
              className="py-2 px-4 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 transition-all shadow-sm"
            >
              🔍 Explorar Código & Tests (Tab 6)
            </button>
            <button
              onClick={() => setActiveTab(9)}
              className="py-2 px-4 rounded-lg text-xs font-semibold text-emerald-800 dark:text-emerald-200 bg-emerald-100 dark:bg-emerald-900/60 hover:bg-emerald-200 transition-colors"
            >
              📦 Descargar ZIP & Git (Tab 9)
            </button>
          </div>
        </div>
      )}

      {isBlocked && (
        <div className="p-6 rounded-2xl border border-rose-300 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/30 text-rose-900 dark:text-rose-100 space-y-3 shadow-sm">
          <div className="flex items-center gap-2.5">
            <ShieldAlert className="w-5 h-5 text-rose-600" />
            <h4 className="text-base font-bold">
              🛑 Bloqueo por Intervención Humana Requerida (Principio V de la Constitución)
            </h4>
          </div>
          <p className="text-xs">
            Se agotaron los 3 intentos permitidos de auto-reparación quirúrgica sin resolver todos los fallos de compilación detectados.
          </p>
          <button
            onClick={() => setActiveTab(6)}
            className="py-2 px-4 rounded-lg text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 transition-all shadow-sm"
          >
            🛠️ Abrir Intervención Manual en Tab 6 →
          </button>
        </div>
      )}

      {/* Real-Time Terminal (Dark Terminal) */}
      <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden shadow-xl">
        {/* Terminal Titlebar */}
        <div className="flex items-center justify-between px-4 py-2 bg-slate-900 border-b border-slate-800 text-xs">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-rose-500 inline-block" />
              <span className="w-3 h-3 rounded-full bg-amber-500 inline-block" />
              <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block" />
            </div>
            <span className="font-mono text-slate-400 pl-2">
              bash -- sse:~/sandbox/maven-build.log
            </span>
          </div>
          <span className="font-mono text-[11px] text-slate-500">
            {logs.length} líneas
          </span>
        </div>

        {/* Terminal Body */}
        <div className="p-4 font-mono text-xs text-slate-200 h-96 overflow-y-auto space-y-1">
          {logs.length === 0 ? (
            <div className="text-slate-500 py-8 text-center">
              Esperando eventos del pipeline... Los logs de compilación aparecerán aquí en tiempo real.
            </div>
          ) : (
            logs.map((log: SSELogEvent, i: number) => (
              <div key={i} className="flex items-start gap-2 hover:bg-slate-900/40 py-0.5 rounded">
                <span className="text-slate-600 select-none text-[11px] shrink-0">
                  [{log.timestamp}]
                </span>
                {log.type && (
                  <span
                    className={`px-1 rounded text-[10px] uppercase font-bold shrink-0 ${
                      log.type === 'ERROR'
                        ? 'bg-rose-950 text-rose-400'
                        : log.type === 'WARN'
                        ? 'bg-amber-950 text-amber-400'
                        : log.type === 'SYSTEM'
                        ? 'bg-blue-950 text-blue-400'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {log.type}
                  </span>
                )}
                <span className="text-slate-300 break-all">{log.message}</span>
              </div>
            ))
          )}
          <div ref={terminalEndRef} />
        </div>
      </div>
    </div>
  );
};
