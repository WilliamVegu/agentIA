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
  const [eventUrl, setEventUrl] = useState(streamUrl);
  const eventSourceRef = useRef<EventSource | null>(null);

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  const addLog = useCallback((log: SSELogEvent) => {
    setLogs((prev) => [...prev.slice(-499), log]);
  }, []);

  useEffect(() => {
    let active = true;
    setEventUrl(streamUrl);
    setLogs([]);
    setLastEvent(null);
    setIsConnected(false);
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
      if (!active) return;
      setIsConnected(true);
      addLog({
        id: Date.now(),
        timestamp: new Date().toLocaleTimeString(),
        type: 'SYSTEM',
        message: 'Canal SSE en vivo conectado con el orquestador.',
      });
    };

    const seen = new Set<string>();
    const handleEvent = (event: MessageEvent) => {
      if (!active) return;
      if (event.type !== "resync_required" && event.lastEventId && seen.has(event.lastEventId)) return;
      if (event.lastEventId) {
        seen.add(event.lastEventId);
        if (seen.size > 1000) seen.delete(seen.values().next().value!);
      }
      try {
        const parsed = typeof event.data === 'string' && event.data.startsWith('{')
          ? JSON.parse(event.data)
          : event.data;
        if (event.type === 'resync_required') {
          seen.clear();
          setLogs([]);
          window.dispatchEvent(new CustomEvent('agentia:session-resync', { detail: { sessionId: parsed?.sessionId } }));
        }
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
      'runtime_log',
      'repair_iteration',
      'queue_status',
      'connect',
      'operation_state',
      'operation_checkpoint',
      'resync_required',
    ];
    customEvents.forEach((evtName) => {
      es.addEventListener(evtName, handleEvent as EventListener);
    });

    es.onerror = () => {
      if (!active) return;
      setIsConnected(false);
    };

    return () => {
      active = false;
      customEvents.forEach((evtName) => {
        es.removeEventListener(evtName, handleEvent as EventListener);
      });
      es.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    };
  }, [streamUrl, addLog]);

  return { logs: eventUrl === streamUrl ? logs : [], isConnected: eventUrl === streamUrl && isConnected,
    lastEvent: eventUrl === streamUrl ? lastEvent : null, clearLogs, addLog };
}
