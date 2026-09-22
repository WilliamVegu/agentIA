import { useEffect, useState, useRef, useCallback } from 'react';

export interface SSELogEvent {
  id: string | number;
  timestamp: string;
  stage?: string;
  type?: string;
  message: string;
  raw?: any;
}

export function useSSE(streamUrl: string | null) {
  const [logs, setLogs] = useState<SSELogEvent[]>([]);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [lastEvent, setLastEvent] = useState<any>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  const addLog = useCallback((log: SSELogEvent) => {
    setLogs((prev) => [...prev.slice(-499), log]);
  }, []);

  useEffect(() => {
    if (!streamUrl) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setIsConnected(false);
      return;
    }

    const es = new EventSource(streamUrl);
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
      addLog({
        id: Date.now(),
        timestamp: new Date().toLocaleTimeString(),
        type: 'SYSTEM',
        message: 'Canal SSE en vivo conectado con el orquestador.',
      });
    };

    const handleEvent = (event: MessageEvent) => {
      try {
        const parsed = typeof event.data === 'string' && event.data.startsWith('{')
          ? JSON.parse(event.data)
          : event.data;
        setLastEvent(parsed);
        const msg =
          (typeof parsed === 'object' && parsed !== null)
            ? (parsed.line || parsed.message || parsed.log || parsed.diffSummary || JSON.stringify(parsed))
            : String(parsed);
        addLog({
          id: event.lastEventId || Date.now() + Math.random(),
          timestamp: new Date().toLocaleTimeString(),
          stage: parsed?.stage || parsed?.phase || parsed?.currentPhase,
          type: parsed?.type || parsed?.event || event.type || 'INFO',
          message: msg,
          raw: parsed,
        });
      } catch {
        addLog({
          id: Date.now() + Math.random(),
          timestamp: new Date().toLocaleTimeString(),
          type: 'RAW',
          message: event.data,
        });
      }
    };

    es.onmessage = handleEvent;
    const customEvents = [
      'phase_transition',
      'session_completed',
      'session_blocked',
      'pipeline_progress',
      'progress',
      'build_log',
      'repair_iteration',
      'queue_status',
      'connect',
    ];
    customEvents.forEach((evtName) => {
      es.addEventListener(evtName, handleEvent as EventListener);
    });

    es.onerror = () => {
      setIsConnected(false);
    };

    return () => {
      customEvents.forEach((evtName) => {
        es.removeEventListener(evtName, handleEvent as EventListener);
      });
      es.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    };
  }, [streamUrl, addLog]);

  return { logs, isConnected, lastEvent, clearLogs, addLog };
}
