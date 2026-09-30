import React from 'react';
import { useStudio } from '../../context/StudioContext';
import { MONITOR_TAB, WORKSPACE_TABS, tabLabel, type TabItem } from '../../config/workspaceTabs';

/**
 * The workspace navigation: the workflow chain, then the monitor as its own surface.
 *
 * Tabs are keyed, not numbered (see `config/workspaceTabs.ts`). The order below is the
 * only thing that decides position, so moving a tab is a one-line change and cannot
 * desynchronise the 20-odd places that navigate programmatically.
 */
export const ResponsiveTabGrid: React.FC = () => {
  const { activeTab, setActiveTab, isQueued } = useStudio();

  const button = (tab: TabItem, options: { compact?: boolean } = {}) => {
    const Icon = tab.icon;
    const isActive = activeTab === tab.key;
    const isMonitor = tab.key === 'monitor';
    return (
      <button
        key={tab.key}
        onClick={() => setActiveTab(tab.key)}
        aria-current={isActive ? 'page' : undefined}
        className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold transition-all select-none text-center whitespace-nowrap ${
          isActive
            ? 'bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-sm border border-blue-200/80 dark:border-blue-900/60 ring-1 ring-blue-500/20'
            : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-white/60 dark:hover:bg-slate-800/60 border border-transparent'
        }`}
        title={tabLabel(tab)}
      >
        <Icon
          className={`w-4 h-4 shrink-0 ${
            isActive
              ? 'text-blue-600 dark:text-blue-400'
              : isMonitor
                ? 'text-amber-500 dark:text-amber-400'
                : 'text-slate-500 dark:text-slate-400'
          }`}
        />
        <span className="whitespace-nowrap">{tabLabel(tab)}</span>
        {isMonitor && isQueued && (
          <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping shrink-0" title="En cola de procesamiento" />
        )}
        {options.compact ? null : null}
      </button>
    );
  };

  return (
    <nav
      aria-label="Navegación de pestañas del workspace"
      className="w-full bg-slate-200/70 dark:bg-slate-900/80 p-2 rounded-xl border border-slate-300/80 dark:border-slate-800 shadow-sm space-y-2"
    >
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">{WORKSPACE_TABS.map((tab) => button(tab))}</div>

      {/* The monitor sits apart on purpose. It is not a step in the sequence -- it is the
          live console you keep open while any step runs -- and being 5th in the row read
          as "visit this after Models & SQL". */}
      <div className="flex items-center gap-2 border-t border-slate-300/70 dark:border-slate-800 pt-2">
        <span className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-500 shrink-0 px-1">
          Siempre disponible
        </span>
        <div className="flex-1">{button(MONITOR_TAB)}</div>
      </div>
    </nav>
  );
};
