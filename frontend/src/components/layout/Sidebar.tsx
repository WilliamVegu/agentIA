import React from 'react';
import { PlusCircle, RefreshCw, Box, CheckCircle2, Clock, AlertTriangle, XCircle, ChevronRight, Pause } from 'lucide-react';
import { TcsLogo } from '../common/TcsLogo';
import { useStudio } from '../../context/StudioContext';

import { useQuarkus } from '../../context/QuarkusContext';

export const Sidebar: React.FC = () => {
  const {
    sessions,
    activeSessionId,
    selectSession,
    startNewService,
    refreshSessions,
  } = useStudio();

  const {
    currentOrder,
    ordersList,
    selectOrder,
    setActiveStep,
    refreshOrders: refreshQuarkusOrders
  } = useQuarkus();

  const handleNewQuarkusOrder = () => {
    setActiveStep(0);
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

  return (
    <aside className="w-64 lg:w-72 bg-white dark:bg-slate-950 border-r border-slate-200/90 dark:border-slate-800 flex flex-col shrink-0 z-40 transition-colors">
      {/* Header with TCS Logo */}
      <div className="h-16 px-5 border-b border-slate-200/90 dark:border-slate-800 flex items-center justify-between">
        <TcsLogo variant="nav" showSubtitle={true} />
      </div>

      {/* Action: New Quarkus Order */}
      <div className="p-4 border-b border-slate-200/80 dark:border-slate-800/80">
        <button
          onClick={handleNewQuarkusOrder}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-semibold text-white bg-red-600 hover:bg-red-700 active:bg-red-800 shadow-md transition-all focus:outline-none"
        >
          <PlusCircle className="w-4 h-4" />
          <span>+ Nuevo Pedido Quarkus</span>
        </button>
      </div>

      {/* Orders List Header */}
      <div className="px-5 py-3 flex items-center justify-between">
        <span className="text-xs font-semibold tracking-wider uppercase text-slate-500 dark:text-slate-400">
          Fábrica Quarkus ({ordersList.length})
        </span>
        <button
          onClick={() => refreshQuarkusOrders()}
          className="p-1 rounded text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title="Actualizar listado de pedidos"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Quarkus orders list */}
      <div className="flex-1 overflow-y-auto px-3 space-y-1 py-1">
        {ordersList.length === 0 ? (
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
                    ? 'bg-red-50 dark:bg-red-950/40 border border-red-300 dark:border-red-900/60 shadow-sm'
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
