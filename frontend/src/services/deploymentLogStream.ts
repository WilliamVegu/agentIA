export type LogConnection = 'connecting' | 'connected' | 'recovering';
type LogEvent = { id: number; message: string; source?: string; timestamp?: string };
type Snapshot = { events: LogEvent[]; lastEventId: number };

/** One subscription owns its cursor, history and cancellation lifecycle. */
export function subscribeDeploymentLogs(
  sessionId: string,
  onLogs: (logs: string[]) => void,
  onConnection: (state: LogConnection) => void,
): () => void {
  const controller = new AbortController();
  const { signal } = controller;
  const url = `/api/v1/devops/${encodeURIComponent(sessionId)}/logs`;
  let cursor = 0;
  let history: LogEvent[] = [];
  let timer: ReturnType<typeof setTimeout> | undefined;
  let wake: (() => void) | undefined;
  const publish = () => { if (!signal.aborted) onLogs(history.map((event) =>
    event.source && event.source !== 'system' ? `[${event.timestamp ?? ''}] [${event.source}] ${event.message}` : event.message)); };
  const pause = (ms: number) => new Promise<void>((resolve) => {
    wake = resolve;
    timer = setTimeout(resolve, ms);
  });
  const check = (response: Response) => {
    if (!response.ok) throw new Error(`Logs HTTP ${response.status}`);
  };
  const recover = async () => {
    const response = await fetch(url, { credentials: 'include', signal });
    check(response);
    const snapshot: Snapshot = await response.json();
    if (!Array.isArray(snapshot.events) || !Number.isSafeInteger(snapshot.lastEventId)) {
      throw new Error('Invalid log snapshot');
    }
    if (signal.aborted) return;
    history = snapshot.events.slice(-1000);
    cursor = snapshot.lastEventId;
    publish();
  };
  const receive = (frame: string) => {
    let id: number | undefined;
    let event = 'message';
    const data: string[] = [];
    for (const line of frame.split('\n')) {
      if (line.startsWith('id:')) id = Number(line.slice(3).trim());
      if (line.startsWith('event:')) event = line.slice(6).trim();
      if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''));
    }
    if (id === undefined || !Number.isSafeInteger(id) || id < 0) return;
    if (event === 'log-reset') {
      JSON.parse(data.join('\n'));
      history = [];
      cursor = id;
      publish();
    } else if (event === 'message' && data.length && id > cursor) {
      const message: unknown = JSON.parse(data.join('\n'));
      if (typeof message !== 'string') throw new Error('Invalid log message');
      cursor = id;
      history = [...history, { id, message }].slice(-1000);
      publish();
    }
  };
  void (async () => {
    let delay = 1000;
    let needsSnapshot = true;
    while (!signal.aborted) {
      let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
      try {
        onConnection(needsSnapshot ? 'recovering' : 'connecting');
        if (needsSnapshot) await recover();
        if (signal.aborted) break;
        const response = await fetch(`${url}/stream`, {
          credentials: 'include', signal,
          headers: { Accept: 'text/event-stream', 'Last-Event-ID': String(cursor) },
        });
        check(response);
        if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body) {
          throw new Error('Log stream unavailable');
        }
        reader = response.body.getReader();
        if (signal.aborted) break;
        onConnection('connected');
        needsSnapshot = false;
        delay = 1000;
        const decoder = new TextDecoder();
        let buffer = '';
        while (!signal.aborted) {
          const chunk = await reader.read();
          if (chunk.done) break;
          buffer += decoder.decode(chunk.value, { stream: true });
          // Normalize only complete frames, so a CRLF split across chunks is preserved.
          let match: RegExpExecArray | null;
          while ((match = /\r?\n\r?\n/.exec(buffer))) {
            const frame = buffer.slice(0, match.index).replace(/\r\n/g, '\n');
            buffer = buffer.slice(match.index + match[0].length);
            if (!signal.aborted) receive(frame);
          }
          if (buffer.length > 65536) throw new Error('Oversized log frame');
        }
      } catch {
        needsSnapshot = true;
      } finally {
        await reader?.cancel().catch(() => undefined);
        reader?.releaseLock();
      }
      if (signal.aborted) break;
      onConnection('recovering');
      await pause(delay);
      delay = Math.min(delay * 2, 15000);
    }
  })();
  return () => {
    controller.abort();
    clearTimeout(timer);
    wake?.();
  };
}
