import React from 'react';
import {
  LayoutDashboard,
  FileText,
  Layers,
  Database,
  FileInput,
  Activity,
  Code,
  ShieldCheck,
  Server,
  Share2,
} from 'lucide-react';
import { useStudio } from '../../context/StudioContext';

export interface TabItem {
  id: number;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

export const WORKSPACE_TABS: TabItem[] = [
  { id: 0, label: '0. Resumen', icon: LayoutDashboard },
  { id: 1, label: '1. Requisitos', icon: FileText },
  { id: 2, label: '2. Arquitectura', icon: Layers },
  { id: 3, label: '3. Modelos & SQL', icon: Database },
  { id: 4, label: '4. Blueprints', icon: FileInput },
  { id: 5, label: '5. Monitor Live', icon: Activity },
  { id: 6, label: '6. Código & Fix', icon: Code },
  { id: 7, label: '7. Calidad SAST', icon: ShieldCheck },
  { id: 8, label: '8. DevOps & Demo', icon: Server },
  { id: 9, label: '9. Entrega Git', icon: Share2 },
];

export const ResponsiveTabGrid: React.FC = () => {
  const { activeTab, setActiveTab, isQueued } = useStudio();

  return (
    <nav aria-label="Navegación de pestañas del workspace" className="w-full bg-slate-200/70 dark:bg-slate-900/80 p-2 rounded-xl border border-slate-300/80 dark:border-slate-800 shadow-sm">
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        {WORKSPACE_TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold transition-all select-none text-center whitespace-nowrap ${
                isActive
                  ? 'bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-sm border border-blue-200/80 dark:border-blue-900/60 ring-1 ring-blue-500/20'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-white/60 dark:hover:bg-slate-800/60 border border-transparent'
              }`}
              title={tab.label}
            >
              <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-blue-600 dark:text-blue-400' : 'text-slate-500 dark:text-slate-400'}`} />
              <span className="whitespace-nowrap">{tab.label}</span>
              {tab.id === 5 && isQueued && (
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping shrink-0" title="En cola de procesamiento" />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
};
