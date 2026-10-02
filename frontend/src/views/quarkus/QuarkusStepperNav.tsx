import React from 'react';
import {
  FileText,
  ShieldAlert,
  Layers,
  Cpu,
  BookOpen,
  CheckCircle2,
  GitPullRequest
} from 'lucide-react';
import { useQuarkus } from '../../context/QuarkusContext';

export const STEPS_CONFIG = [
  { id: 0, label: '1. Requisitos & Arquetipo', short: 'Pedido', icon: FileText },
  { id: 1, label: '2. Contrato OpenAPI', short: 'Contrato', icon: ShieldAlert, isGate: true },
  { id: 2, label: '3. Arquitectura & Extensiones', short: 'Arquitectura', icon: Layers },
  { id: 3, label: '4. Construcción & QA', short: 'Construcción', icon: Cpu },
  { id: 4, label: '5. Documentación', short: 'Docs', icon: BookOpen },
  { id: 5, label: '6. Control 2: Revisión', short: 'Control 2', icon: CheckCircle2, isGate: true },
  { id: 6, label: '7. Entrega DevOps & ZIP', short: 'DevOps', icon: GitPullRequest },
];

export const QuarkusStepperNav: React.FC = () => {
  const { currentOrder, activeStep, setActiveStep, resetCurrentOrder } = useQuarkus();

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 shadow-sm mb-4">
      {/* Header bar con ID del pedido y estado */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 mb-3 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-red-600/10 dark:bg-red-500/20 text-red-600 dark:text-red-400 flex items-center justify-center font-bold text-sm">
            Q
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                Fábrica Quarkus · {currentOrder?.basic_data?.service_name || 'Nuevo Pedido'}
              </h2>
              {currentOrder && (
                <span className="text-xs px-2 py-0.5 rounded-full font-mono bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                  {currentOrder.id}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Contract-First · Java 21 · {currentOrder?.technical?.database || 'SQLite/SQL Server'}
            </p>
          </div>
        </div>

        {/* Estado y Agentes Activos */}
        <div className="flex items-center gap-3">
          {currentOrder && (
            <button
              type="button"
              onClick={resetCurrentOrder}
              className="px-2.5 py-1 text-xs font-semibold rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-all shadow-sm"
              title="Iniciar un nuevo pedido desde cero"
            >
              ➕ Nuevo Pedido
            </button>
          )}

          {currentOrder && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-900 text-xs">
              <span className="font-semibold text-purple-700 dark:text-purple-300">🤖 8 Agentes:</span>
              <span className="px-1.5 py-0.5 rounded font-bold bg-purple-600 text-white text-[10px]">
                {currentOrder.specialized_agents?.filter(a => a.status === 'Completado').length || 0}/8 Listos
              </span>
            </div>
          )}

          {currentOrder && (
            <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 text-xs">
              <span className="font-semibold text-blue-700 dark:text-blue-300">Estado:</span>
              <span className="px-2 py-0.5 rounded-md font-medium bg-blue-600 text-white text-[11px]">
                {currentOrder.status}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Stepper de 7 Pasos */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
        {STEPS_CONFIG.map((step) => {
          const Icon = step.icon;
          const isActive = activeStep === step.id;
          const isCompleted = activeStep > step.id;

          let btnClass = 'bg-slate-50 dark:bg-slate-800/50 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800';
          if (isActive) {
            btnClass = step.isGate
              ? 'bg-amber-500 text-white border-amber-600 shadow-md ring-2 ring-amber-300 dark:ring-amber-800'
              : 'bg-red-600 text-white border-red-700 shadow-md ring-2 ring-red-300 dark:ring-red-900';
          } else if (isCompleted) {
            btnClass = 'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800';
          }

          return (
            <button
              key={step.id}
              onClick={() => setActiveStep(step.id)}
              className={`flex items-center gap-2 px-2.5 py-2 rounded-lg border text-xs font-medium transition-all text-left relative overflow-hidden ${btnClass}`}
              title={step.label}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <div className="truncate">
                <span className="block truncate font-semibold">{step.short}</span>
                {step.isGate && (
                  <span className="text-[9px] uppercase tracking-wider opacity-85 block font-bold">
                    Control Humano
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

