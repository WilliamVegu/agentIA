import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { SessionListItem, sessionService } from '../services/sessionService';
import { orchestratorService, ProjectOverview } from '../services/orchestratorService';
import type { TabKey } from '../config/workspaceTabs';

interface StudioContextType {
  activeTab: TabKey;
  setActiveTab: (tab: TabKey) => void;
  activeSessionId: string | null;
  activeSession: SessionListItem | null;
  sessions: SessionListItem[];
  projectOverview: ProjectOverview | null;
  lifecycle: any | null;
  isLoading: boolean;
  isQueued: boolean;
  currentDraft: any | null;
  setCurrentDraft: (draft: any) => void;
  architectureDesign: any | null;
  setArchitectureDesign: (design: any) => void;
  dataModelDesign: any | null;
  setDataModelDesign: (design: any) => void;
  currentSpecId: string | null;
  setCurrentSpecId: (id: string | null) => void;
  parsedSpec: any | null;
  setParsedSpec: (spec: any) => void;
  refreshSessions: () => Promise<void>;
  selectSession: (sessionId: string | null) => void;
  startNewService: () => void;
  reloadCurrentOverview: () => Promise<void>;
}

const StudioContext = createContext<StudioContextType | undefined>(undefined);

export const StudioProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // A key, not an index: see config/workspaceTabs.ts for why the number was removed.
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [projectOverview, setProjectOverview] = useState<ProjectOverview | null>(null);
  const [lifecycle, setLifecycle] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [currentDraft, setCurrentDraft] = useState<any | null>(null);
  const [architectureDesign, setArchitectureDesign] = useState<any | null>(null);
  const [dataModelDesign, setDataModelDesign] = useState<any | null>(null);
  const [currentSpecId, setCurrentSpecId] = useState<string | null>(null);
  const [parsedSpec, setParsedSpec] = useState<any | null>(null);
  const initialLoadDone = useRef(false);

  const refreshSessions = useCallback(async () => {
    try {
      const list = await sessionService.listSessions(50);
      setSessions(list);
      if (!initialLoadDone.current) {
        initialLoadDone.current = true;
        if (list.length > 0) {
          setActiveSessionId(list[0].sessionId);
        }
      }
    } catch {
      // Graceful fallback if backend is starting up
    }
  }, []);

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  const reloadCurrentOverview = useCallback(async () => {
    if (!activeSessionId) return;
    try {
      const [overviewData, lifecycleData] = await Promise.allSettled([
        orchestratorService.getOverview(activeSessionId),
        orchestratorService.getLifecycle(activeSessionId),
      ]);
      if (overviewData.status === 'fulfilled') {
        setProjectOverview(overviewData.value);
      }
      if (lifecycleData.status === 'fulfilled') {
        setLifecycle(lifecycleData.value);
      }
    } catch {
      // Fallback
    }
  }, [activeSessionId]);

  useEffect(() => {
    if (activeSessionId) {
      reloadCurrentOverview();
    } else {
      setProjectOverview(null);
      setLifecycle(null);
    }
  }, [activeSessionId, reloadCurrentOverview]);

  const selectSession = (sessionId: string | null) => {
    if (sessionId !== activeSessionId) {
      setCurrentDraft(null);
      setArchitectureDesign(null);
      setDataModelDesign(null);
      setCurrentSpecId(null);
      setParsedSpec(null);
      setProjectOverview(null);
      setLifecycle(null);
    }
    setActiveSessionId(sessionId);
  };

  const startNewService = () => {
    setActiveSessionId(null);
    // Resumen, because that is where the new-service form is (name, description,
    // database). This read `setActiveTab(0)` when 0 was Resumen, and the reorder turned
    // that into "the first tab" -- which is now Blueprints -- so the button navigated away
    // from the form it exists to open. Worse, the copy of this button *inside* Resumen
    // took you off the page you were already on. A refactor has to preserve what a control
    // does; pointing at the first tab preserved the number instead.
    setActiveTab('overview');
    setProjectOverview(null);
    setLifecycle(null);
    setCurrentDraft(null);
    setArchitectureDesign(null);
    setDataModelDesign(null);
    setCurrentSpecId(null);
    setParsedSpec(null);
  };

  const activeSession = sessions.find((s) => s.sessionId === activeSessionId) || null;
  const isQueued = activeSession?.status === 'QUEUED';

  // Real-time reactive polling only when the active session or its pipeline is RUNNING or QUEUED
  const isActiveRunning =
    activeSession?.status === 'RUNNING' ||
    activeSession?.status === 'QUEUED' ||
    lifecycle?.pipelineStatus === 'RUNNING' ||
    lifecycle?.pipeline_status === 'RUNNING';
  const shouldPoll = Boolean(isActiveRunning);

  useEffect(() => {
    if (!shouldPoll) return;

    const intervalId = setInterval(async () => {
      try {
        await refreshSessions();
        if (activeSessionId) {
          await reloadCurrentOverview();
        }
      } catch {
        // Ignore transient background polling errors
      }
    }, 2000);

    return () => clearInterval(intervalId);
  }, [shouldPoll, activeSessionId, refreshSessions, reloadCurrentOverview]);

  return (
    <StudioContext.Provider
      value={{
        activeTab,
        setActiveTab,
        activeSessionId,
        activeSession,
        sessions,
        projectOverview,
        lifecycle,
        isLoading,
        isQueued,
        currentDraft,
        setCurrentDraft,
        architectureDesign,
        setArchitectureDesign,
        dataModelDesign,
        setDataModelDesign,
        currentSpecId,
        setCurrentSpecId,
        parsedSpec,
        setParsedSpec,
        refreshSessions,
        selectSession,
        startNewService,
        reloadCurrentOverview,
      }}
    >
      {children}
    </StudioContext.Provider>
  );
};

export const useStudio = () => {
  const context = useContext(StudioContext);
  if (!context) {
    throw new Error('useStudio must be used within a StudioProvider');
  }
  return context;
};
