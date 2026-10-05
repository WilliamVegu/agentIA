import React from 'react';
import {
  PlusCircle,
  RefreshCw,
  Box,
  CheckCircle2,
  Clock,
  AlertTriangle,
  XCircle,
  ChevronRight,
  Pause,
  ArrowLeftRight,
  Layers,
  Zap,
  LayoutGrid,
} from 'lucide-react';
import { TcsLogo } from '../common/TcsLogo';
import { useStudio } from '../../context/StudioContext';
import { useQuarkus } from '../../context/QuarkusContext';
import { useEcosystem } from '../../context/EcosystemContext';

export const Sidebar: React.FC = () => {
  const { activeEcosystem, goToLauncher, goToSpring, goToQuarkus } = useEcosystem();

  // Spring Boot Studio Context
  const {
    sessions,
    activeSessionId,
    selectSession,
    startNewService,
    refreshSessions,
  } = useStudio();

  // Quarkus Factory Context
  const {
    currentOrder,
    ordersList,
    selectOrder,
    setActiveStep,
    refreshOrders: refreshQuarkusOrders,
  } = useQuarkus();

  const isCreatingNewSpring = !activeSessionId;

  const handleNewSpringService = () => {
    startNewService();
  };

  const handleNewQuarkusOrder = () => {
    setActiveStep(0);
  };

  const getSpringStatusBadge = (status: string) => {
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

  const getQuarkusStatusIcon = (status: string) => {
    switch (status) {
      case 'Entregado':
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />;
      case 'Generando':
      case 'Probando':
        return <RefreshCw className="w-3.5 h-3.5 text-red-500 animate-spin shrink-0" />;
      case 'Contrato en revisión':
      case 'En revisión':
        return <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />;
      case 'Aprobado':
        return <CheckCircle2 className="w-3.5 h-3.5 text-blue-500 shrink-0" />;
      default:
        return <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />;
    }
  };

  const isQuarkus = activeEcosystem === 'quarkus';

  return (
    <aside className="w-64 lg:w-72 bg-white dark:bg-slate-950 border-r border-slate-200/90 dark:border-slate-800 flex flex-col shrink-0 z-40 transition-colors">
      {/* Header with TCS Logo */}
      <div className="h-16 px-4 border-b border-slate-200/90 dark:border-slate-800 flex items-center justify-between">
        <TcsLogo variant="nav" showSubtitle={true} />
      </div>

      {/* Active Ecosystem Indicator & Fast Switcher */}
      <div className="px-3 pt-3 pb-2 border-b border-slate-200/80 dark:border-slate-800/80">
        <div
          className={`flex items-center justify-between p-2 rounded-xl border text-xs ${
            isQuarkus
              ? 'bg-red-50/60 dark:bg-red-950/30 border-red-200 dark:border-red-900/50 text-red-800 dark:text-red-300'
              : 'bg-emerald-50/60 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-900/50 text-emerald-800 dark:text-emerald-300'
          }`}
        >
          <div className="flex items-center gap-2 font-semibold">
            {isQuarkus ? (
              <>
                <Zap className="w-3.5 h-3.5 text-red-600 dark:text-red-400" />
                <span className="truncate">Quarkus 3.x</span>
              </>
            ) : (
              <>
                <Layers className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                <span className="truncate">Spring Boot</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={isQuarkus ? goToSpring : goToQuarkus}
              title={isQuarkus ? "Cambiar a Spring Boot Studio" : "Cambiar a Fábrica Quarkus"}
              className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-lg bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 font-medium transition-colors"
            >
              <ArrowLeftRight className="w-3 h-3 text-slate-500" />
              <span>{isQuarkus ? 'Spring' : 'Quarkus'}</span>
            </button>
            <button
              onClick={goToLauncher}
              title="Volver al Hub Selector de Ecosistemas"
              className="p-1 rounded-lg bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 hover:text-slate-900 dark:hover:text-white transition-colors"
            >
              <LayoutGrid className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* Action Button */}
      <div className="p-3 border-b border-slate-200/80 dark:border-slate-800/80">
        {isQuarkus ? (
          <button
            onClick={handleNewQuarkusOrder}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-semibold text-white bg-red-600 hover:bg-red-700 active:bg-red-800 shadow-sm transition-all focus:outline-none"
          >
            <PlusCircle className="w-4 h-4" />
            <span>+ Nuevo Pedido Quarkus</span>
          </button>
        ) : (
          <button
            onClick={handleNewSpringService}
            className={`w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-semibold text-white transition-all focus:outline-none ${
              isCreatingNewSpring
                ? 'bg-emerald-700 ring-2 ring-emerald-400 dark:ring-emerald-500 shadow-md font-bold'
                : 'bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 shadow-sm'
            }`}
          >
            <PlusCircle className="w-4 h-4" />
            <span>Nuevo Microservicio</span>
          </button>
        )}
      </div>

      {/* List Header */}
      <div className="px-4 py-2.5 flex items-center justify-between">
        <span className="text-xs font-semibold tracking-wider uppercase text-slate-500 dark:text-slate-400">
          {isQuarkus ? `Pedidos Quarkus (${ordersList.length})` : `Microservicios (${sessions.length})`}
        </span>
        <button
          onClick={() => (isQuarkus ? refreshQuarkusOrders() : refreshSessions())}
          className="p-1 rounded text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title="Actualizar listado"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* List Content */}
      <div className="flex-1 overflow-y-auto px-3 space-y-1 py-1">
        {isQuarkus ? (
          /* Quarkus Orders List */
          ordersList.length === 0 ? (
            <div className="text-center py-8 px-4 text-xs text-slate-400">
              No hay pedidos activos. Pulsa el botón superior para ingresar uno.
            </div>
          ) : (
            ordersList.map((ord) => {
              const isSelected = ord.id === currentOrder?.id;
              return (
                <button
                  key={ord.id}
                  onClick={() => selectOrder(ord)}
                  className={`w-full text-left p-2.5 rounded-xl text-xs transition-all flex items-center justify-between group ${
                    isSelected
                      ? 'bg-red-50 dark:bg-red-950/40 border border-red-300 dark:border-red-900/60 shadow-xs'
                      : 'hover:bg-slate-100 dark:hover:bg-slate-900 border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate min-w-0">
                    {getQuarkusStatusIcon(ord.status)}
                    <div className="truncate">
                      <div
                        className={`font-semibold truncate ${
                          isSelected
                            ? 'text-red-700 dark:text-red-300'
                            : 'text-slate-800 dark:text-slate-200'
                        }`}
                      >
                        {ord.basic_data.service_name}
                      </div>
                      <div className="text-[10px] text-slate-500 dark:text-slate-400 flex items-center gap-1.5 mt-0.5">
                        <span>{ord.status}</span>
                        <span>·</span>
                        <span>{(ord.tokens_audit?.total_consumed || 0).toLocaleString()} tok</span>
                      </div>
                    </div>
                  </div>
                  <ChevronRight
                    className={`w-4 h-4 shrink-0 transition-transform ${
                      isSelected
                        ? 'text-red-600 dark:text-red-400 translate-x-0.5'
                        : 'text-slate-300 dark:text-slate-700 group-hover:text-slate-500'
                    }`}
                  />
                </button>
              );
            })
          )
        ) : (
          /* Spring Boot Sessions List */
          sessions.length === 0 ? (
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
                      ? 'bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-900/60 shadow-xs'
                      : 'hover:bg-slate-100 dark:hover:bg-slate-900 border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate min-w-0">
                    {getSpringStatusBadge(sess.status)}
                    <div className="truncate">
                      <div
                        className={`font-semibold truncate ${
                          isSelected
                            ? 'text-emerald-700 dark:text-emerald-300'
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
                        ? 'text-emerald-600 dark:text-emerald-400 translate-x-0.5'
                        : 'text-slate-300 dark:text-slate-700 group-hover:text-slate-500'
                    }`}
                  />
                </button>
              );
            })
          ))}
      </div>
    </aside>
  );
};
