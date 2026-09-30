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

/**
 * Stable identity for every workspace tab.
 *
 * Tabs used to be identified by a **positional number** -- `activeTab === 5`, and
 * `setActiveTab(5)` in 23 places across 8 views. Reordering the row therefore broke
 * every navigation silently: the button moved, the number stayed, and clicking "approve
 * requirements" landed on the wrong screen. Numbers are now display order only, and the
 * key is what code refers to, so the order can change without touching a single caller.
 */
export type TabKey =
  | 'blueprints'
  | 'overview'
  | 'requirements'
  | 'architecture'
  | 'models'
  | 'code'
  | 'quality'
  | 'devops'
  | 'delivery'
  | 'monitor';

export interface TabItem {
  key: TabKey;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  /**
   * Position in the workflow chain, rendered as a prefix. Absent for the surfaces that
   * are not steps: specification ingestion, the dashboard, and the live monitor.
   */
  step?: number;
}

/**
 * The workflow chain, in order. Blueprint ingestion is first because it is an *entry
 * point*: if the specification already exists as a formal document, validating it is
 * step one, and everything after it derives from that. The requirements tab is the other
 * entry point, for when the specification still has to be written.
 */
export const WORKSPACE_TABS: TabItem[] = [
  // Entry point: bring a specification you already have.
  { key: 'blueprints', label: 'Blueprints', icon: FileInput },
  // Dashboard, not a step.
  { key: 'overview', label: 'Resumen', icon: LayoutDashboard },

  // The chain.
  { key: 'requirements', label: 'Requisitos', icon: FileText, step: 1 },
  { key: 'architecture', label: 'Arquitectura', icon: Layers, step: 2 },
  { key: 'models', label: 'Modelos & SQL', icon: Database, step: 3 },
  { key: 'code', label: 'Código & Fix', icon: Code, step: 4 },
  { key: 'quality', label: 'Calidad SAST', icon: ShieldCheck, step: 5 },
  { key: 'devops', label: 'DevOps & Demo', icon: Server, step: 6 },
  { key: 'delivery', label: 'Entrega Git', icon: Share2, step: 7 },
];

/**
 * Always available, deliberately outside the chain above.
 *
 * The monitor is an observability surface, not a phase: you want it while *any* step is
 * running, and its position in the sequence implied you were meant to visit it in turn.
 * It renders in its own strip, separated from the workflow.
 */
export const MONITOR_TAB: TabItem = { key: 'monitor', label: 'Monitor Live', icon: Activity };

export const ALL_TABS: TabItem[] = [...WORKSPACE_TABS, MONITOR_TAB];

export const tabLabel = (tab: TabItem): string =>
  typeof tab.step === 'number' ? `${tab.step}. ${tab.label}` : tab.label;
