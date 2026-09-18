import React from 'react';
import { PlusCircle, RefreshCw, Box, CheckCircle2, Clock, AlertTriangle, XCircle, ChevronRight, Pause } from 'lucide-react';
import { TcsLogo } from '../common/TcsLogo';
import { useStudio } from '../../context/StudioContext';

export const Sidebar: React.FC = () => {
  const {
    sessions,
    activeSessionId,
    selectSession,
    startNewService,
    refreshSessions,
  } = useStudio();

  const isCreatingNew = !activeSessionId;

  const handleNewService = () => {
    startNewService();
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />;
      case 'RUNNING':
        return <RefreshCw className="w-3.5 h-3.5 text-blue-500 animate-spin shrink-0" />;
      case 'PAUSED':
        return <Pause className="w-3.5 h-3.5 text-amber-500 shrink-0" />;
      case 'CANCELLED':
        return <XCircle className="w-3.5 h-3.5 text-rose-500 shrink-0" />;
      case 'QUEUED':
        return <Clock className="w-3.5 h-3.5 text-amber-500 shrink-0" />;
      case 'BLOCKED':
        return <AlertTriangle className="w-3.5 h-3.5 text-rose-500 shrink-0" />;
      default:
        return <Box className="w-3.5 h-3.5 text-slate-400 shrink-0" />;
    }
  };

  return (
    <aside className="w-64 lg:w-72 bg-white dark:bg-slate-950 border-r border-slate-200/90 dark:border-slate-800 flex flex-col shrink-0 z-40 transition-colors">
      {/* Header with TCS Logo */}
      <div className="h-16 px-5 border-b border-slate-200/90 dark:border-slate-800 flex items-center justify-between">
        <TcsLogo variant="nav" showSubtitle={true} />
      </div>

      {/* Action: New Microservice */}
      <div className="p-4 border-b border-slate-200/80 dark:border-slate-800/80">
        <button
          onClick={handleNewService}
          className={`w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-semibold text-white transition-all focus:outline-none ${
            isCreatingNew
              ? 'bg-blue-700 ring-2 ring-blue-400 dark:ring-blue-500 shadow-md font-bold'
              : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800 shadow-sm'
          }`}
        >
          <PlusCircle className="w-4 h-4" />
          <span>Nuevo Microservicio</span>
        </button>
      </div>

      {/* Sessions List Header */}
      <div className="px-5 py-3 flex items-center justify-between">
        <span className="text-xs font-semibold tracking-wider uppercase text-slate-500 dark:text-slate-400">
          Microservicios ({sessions.length})
        </span>
        <button
          onClick={() => refreshSessions()}
          className="p-1 rounded text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title="Actualizar listado de sesiones"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Session items list */}
      <div className="flex-1 overflow-y-auto px-3 space-y-1 py-1">
        {/* Quick Option: New Microservice (Streamlit Parity) */}
        <button
          onClick={handleNewService}
          className={`w-full text-left p-2.5 rounded-xl text-xs transition-all flex items-center justify-between group mb-1 ${
            isCreatingNew
              ? 'bg-blue-50 dark:bg-blue-950/40 border border-blue-300 dark:border-blue-800 shadow-sm font-semibold text-blue-700 dark:text-blue-300'
              : 'hover:bg-slate-100 dark:hover:bg-slate-900 border border-dashed border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-400'
          }`}
        >
          <div className="flex items-center gap-2.5 truncate min-w-0">
            <PlusCircle className={`w-3.5 h-3.5 shrink-0 ${isCreatingNew ? 'text-blue-600' : 'text-slate-400'}`} />
            <div className="truncate">
              <div>✨ + Crear Nuevo Microservicio</div>
              <div className="text-[10px] opacity-75">Inicio rápido 1-click</div>
            </div>
          </div>
          <ChevronRight className={`w-3.5 h-3.5 shrink-0 ${isCreatingNew ? 'text-blue-600' : 'text-slate-300'}`} />
        </button>
        {sessions.length === 0 ? (
          <div className="text-center py-8 px-4 text-xs text-slate-400">
            No hay sesiones registradas. Inicie una con el botón superior.
          </div>
        ) : (
          sessions.map((sess) => {
            const isSelected = sess.sessionId === activeSessionId;
            return (
              <button
                key={sess.sessionId}
                onClick={() => selectSession(sess.sessionId)}
                className={`w-full text-left p-2.5 rounded-xl text-xs transition-all flex items-center justify-between group ${
                  isSelected
                    ? 'bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900/60 shadow-sm'
                    : 'hover:bg-slate-100 dark:hover:bg-slate-900 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-2.5 truncate min-w-0">
                  {getStatusBadge(sess.status)}
                  <div className="truncate">
                    <div
                      className={`font-semibold truncate ${
                        isSelected
                          ? 'text-blue-700 dark:text-blue-300'
                          : 'text-slate-800 dark:text-slate-200'
                      }`}
                    >
                      {sess.specName || 'app-service'}
                    </div>
                    <div className="text-[10px] text-slate-500 dark:text-slate-400 flex items-center gap-1.5 mt-0.5">
                      <span>{sess.currentLifecyclePhase || 'INICIO'}</span>
                      <span>·</span>
                      <span>{Math.round(sess.completionPercentage || 0)}%</span>
                    </div>
                  </div>
                </div>

                <ChevronRight
                  className={`w-4 h-4 shrink-0 transition-transform ${
                    isSelected
                      ? 'text-blue-600 dark:text-blue-400 translate-x-0.5'
                      : 'text-slate-300 dark:text-slate-700 group-hover:text-slate-500'
                  }`}
                />
              </button>
            );
          })
        )}
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-200/90 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 text-[11px] text-slate-500 dark:text-slate-400">
        <div className="flex items-center justify-between">
          <span>Sprint 1 · v1.0.0</span>
          <span className="font-mono text-emerald-600 dark:text-emerald-400 font-semibold">TCS Global</span>
        </div>
      </div>
    </aside>
  );
};
