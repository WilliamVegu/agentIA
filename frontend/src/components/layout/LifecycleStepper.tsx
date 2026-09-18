import React, { useState } from 'react';
import {
  CheckCircle2,
  Clock,
  Play,
  Pause,
  Square,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  Info,
} from 'lucide-react';
import { useStudio } from '../../context/StudioContext';
import { orchestratorService } from '../../services/orchestratorService';

const CANONICAL_PHASES = [
  { key: 'REQUIREMENTS', label: '1. Requisitos', tab: 1 },
  { key: 'STORIES', label: '2. Historias BDD', tab: 1 },
  { key: 'ARCHITECTURE', label: '3. Arquitectura', tab: 2 },
  { key: 'DATA_MODEL', label: '4. Modelos & DDL', tab: 3 },
  { key: 'CODE_TESTS', label: '5. Código & Tests', tab: 6 },
  { key: 'SECURITY_AUDIT', label: '6. Calidad SAST', tab: 7 },
  { key: 'DEVOPS_DEPLOY', label: '7. DevOps Local', tab: 8 },
];

export const LifecycleStepper: React.FC = () => {
  const {
    activeSessionId,
    activeSession,
    lifecycle,
    reloadCurrentOverview,
    refreshSessions,
    setActiveTab,
    isQueued,
  } = useStudio();

  const [isActing, setIsActing] = useState(false);

  if (!activeSessionId) return null;

  const completionPct =
    lifecycle?.completionPercentage ||
    lifecycle?.completion_percentage ||
    activeSession?.completionPercentage ||
    0;
  const pipeStatus =
    lifecycle?.pipelineStatus ||
    lifecycle?.pipeline_status ||
    activeSession?.status ||
    'IDLE';
  const isPaused = pipeStatus === 'PAUSED';
  const isRunning = pipeStatus === 'RUNNING' || pipeStatus === 'QUEUED';
  const isCancelled = pipeStatus === 'CANCELLED';
  const isCompleted = pipeStatus === 'COMPLETED' || completionPct >= 100;
  const hasOutdated = lifecycle?.isOutdated || lifecycle?.is_outdated || false;

  const phaseMap = React.useMemo(() => {
    const map: Record<string, any> = {};
    if (Array.isArray(lifecycle?.phases)) {
      lifecycle.phases.forEach((p: any) => {
        map[p.phase] = p;
      });
    }
    return map;
  }, [lifecycle?.phases]);

  const handlePause = async () => {
    setIsActing(true);
    try {
      await orchestratorService.pausePipeline(activeSessionId);
      await Promise.all([reloadCurrentOverview(), refreshSessions()]);
    } catch (err) {
      console.error('Error pausing pipeline:', err);
    } finally {
      setIsActing(false);
    }
  };

  const handleResume = async () => {
    setIsActing(true);
    try {
      await orchestratorService.resumePipeline(activeSessionId);
      await Promise.all([reloadCurrentOverview(), refreshSessions()]);
    } catch (err) {
      console.error('Error resuming pipeline:', err);
    } finally {
      setIsActing(false);
    }
  };

  const handleCancel = async () => {
    if (!window.confirm('¿Desea cancelar la ejecución del pipeline para este microservicio?')) return;
    setIsActing(true);
    try {
      await orchestratorService.cancelPipeline(activeSessionId);
      await Promise.all([reloadCurrentOverview(), refreshSessions()]);
    } catch (err) {
      console.error('Error cancelling pipeline:', err);
    } finally {
      setIsActing(false);
    }
  };

  const handleResyncOutdated = async () => {
    setIsActing(true);
    try {
      await orchestratorService.transitionPhase(activeSessionId, {
        target_phase: 'DEVOPS_DEPLOY',
        force: true,
      });
      await Promise.all([reloadCurrentOverview(), refreshSessions()]);
    } catch {
      // Handled
    } finally {
      setIsActing(false);
    }
  };

  return (
    <div className="w-full bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-xl p-4 shadow-sm mb-4 transition-colors">
      {/* Top row: Summary + Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-3">
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              <span>Pipeline de Ciclo de Vida LangGraph</span>
              {/* Informative Queue Badge (Feedback #1) */}
              {isQueued && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
                  <Clock className="w-3 h-3" />
                  <span>En Cola Concurrente (Docker Max: 2)</span>
                </span>
              )}
            </span>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              Microservicio: <strong className="text-slate-700 dark:text-slate-200">{activeSession?.specName || activeSessionId}</strong> · Avance Global: {Math.round(completionPct)}%
            </span>
          </div>
        </div>

        {/* Hot Pipeline Controls */}
        <div className="flex items-center gap-2">
          {/* Pausar / Reanudar button */}
          {isPaused ? (
            <button
              onClick={handleResume}
              disabled={isActing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all disabled:opacity-50"
              title="Reanudar pipeline en Auto-Pilot"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Reanudar</span>
            </button>
          ) : isRunning ? (
            <button
              onClick={handlePause}
              disabled={isActing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-50 hover:bg-amber-100 dark:bg-amber-950/40 dark:hover:bg-amber-900/60 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-800 transition-all disabled:opacity-50 shadow-sm"
              title="Pausar pipeline y cambiar a modo asistido"
            >
              <Pause className="w-3.5 h-3.5" />
              <span>Pausar</span>
            </button>
          ) : isCancelled ? (
            <button
              onClick={handleResume}
              disabled={isActing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-700 transition-all disabled:opacity-50"
              title="Reiniciar Auto-Pilot"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Reiniciar</span>
            </button>
          ) : !isCompleted ? (
            <button
              onClick={handleResume}
              disabled={isActing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-all disabled:opacity-50"
              title="Iniciar Auto-Pilot"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Iniciar Auto-Pilot</span>
            </button>
          ) : null}

          {/* Cancelar button */}
          {!isCompleted && !isCancelled && (
            <button
              onClick={handleCancel}
              disabled={isActing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-rose-50 dark:bg-rose-950/40 hover:bg-rose-100 dark:hover:bg-rose-900/60 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-900 transition-all disabled:opacity-50 shadow-sm"
              title="Cancelar ejecución del pipeline"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              <span>Cancelar</span>
            </button>
          )}

          {isCancelled && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border border-rose-300 dark:border-rose-800">
              <Square className="w-3 h-3 fill-current" />
              <span>Cancelado</span>
            </span>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden mb-3">
        <div
          className="bg-blue-600 h-full rounded-full transition-all duration-500 ease-out"
          style={{ width: `${Math.min(100, Math.max(0, completionPct))}%` }}
        />
      </div>

      {/* Outdated Upstream Banner */}
      {hasOutdated && (
        <div className="mb-3 p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/80 flex items-center justify-between text-xs text-amber-800 dark:text-amber-200">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              Se detectaron modificaciones upstream. Las fases posteriores están marcadas como <strong>OUTDATED</strong>.
            </span>
          </div>
          <button
            onClick={handleResyncOutdated}
            disabled={isActing}
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-amber-600 hover:bg-amber-700 text-white font-semibold transition-colors shrink-0"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Re-sincronizar</span>
          </button>
        </div>
      )}

      {/* 7 Canonical Stages Horizontal Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 pt-1">
        {CANONICAL_PHASES.map((phase, idx) => {
          const stageData = phaseMap[phase.key];
          const isDone = stageData?.status === 'COMPLETED';
          const isCurrent = (lifecycle?.currentPhase || lifecycle?.current_phase) === phase.key;
          const isOutdated = stageData?.status === 'OUTDATED';

          return (
            <button
              key={phase.key}
              onClick={() => setActiveTab(phase.tab)}
              className={`p-2 rounded-lg text-left text-xs transition-all border flex flex-col justify-between ${
                isDone
                  ? 'bg-emerald-50/60 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800/50 text-emerald-800 dark:text-emerald-300'
                  : isOutdated
                  ? 'bg-amber-50/60 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800/50 text-amber-800 dark:text-amber-300'
                  : isCurrent
                  ? 'bg-blue-50 dark:bg-blue-950/40 border-blue-300 dark:border-blue-700 text-blue-800 dark:text-blue-300 font-semibold ring-1 ring-blue-500/30'
                  : 'bg-slate-50 dark:bg-slate-900/50 border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400'
              }`}
            >
              <div className="flex items-center justify-between gap-1 mb-1">
                <span className="font-semibold whitespace-nowrap">{phase.label}</span>
                {isDone ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                ) : isOutdated ? (
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                ) : (
                  <span className="text-[10px] text-slate-400 shrink-0">#{idx + 1}</span>
                )}
              </div>
              <div className="text-[10px] opacity-80">
                {isDone ? 'Verificado' : isOutdated ? 'Requiere sync' : isCurrent ? 'En curso' : 'Pendiente'}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
