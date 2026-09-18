import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { SessionListItem, sessionService } from '../services/sessionService';
import { orchestratorService, ProjectOverview } from '../services/orchestratorService';

interface StudioContextType {
  activeTab: number;
  setActiveTab: (tab: number) => void;
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
  const [activeTab, setActiveTab] = useState<number>(0);
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
    setActiveSessionId(sessionId);
    if (!sessionId) {
      setProjectOverview(null);
      setLifecycle(null);
      setCurrentDraft(null);
      setArchitectureDesign(null);
      setDataModelDesign(null);
      setCurrentSpecId(null);
      setParsedSpec(null);
    }
  };

  const startNewService = () => {
    setActiveSessionId(null);
    setActiveTab(0);
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
