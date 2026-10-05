import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { subscribeDeploymentLogs } from '../services/deploymentLogStream';

let stop: (() => void) | undefined;
const encoder = new TextEncoder();
const snapshot = (events: { id: number; message: string }[] = []) => ({
  ok: true, json: async () => ({ events, lastEventId: events.at(-1)?.id ?? 0 }),
});
const stream = (...chunks: string[]) => ({
  ok: true, headers: new Headers({ 'content-type': 'text/event-stream' }),
  body: new ReadableStream({ start(controller) {
    chunks.forEach(chunk => controller.enqueue(encoder.encode(chunk))); controller.close();
  } }),
});
beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { stop?.(); stop = undefined; vi.unstubAllGlobals(); vi.useRealTimers(); });
const flush = async () => { for (let i = 0; i < 30; i++) await Promise.resolve(); };

it('recupera snapshot y eventos fragmentados sin duplicar IDs; reconecta desde el último', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(snapshot([{ id: 1, message: 'first' }]))
    .mockResolvedValueOnce(stream('id: 1\ndata: "first"\n\n: heartbeat\n\nid: 2\r', '\ndata: "segundo ñ"\r\n\r', '\nid: 3\ndata: "third"\n\n'))
    .mockResolvedValueOnce(stream('id: 3\ndata: "third"\n\nid: 4\ndata: "fourth"\n\n'));
  vi.stubGlobal('fetch', fetcher);
  const logs = vi.fn();
  stop = subscribeDeploymentLogs('session with space', logs, vi.fn());
  await flush();
  expect(logs).toHaveBeenLastCalledWith(['first', 'segundo ñ', 'third']);
  await vi.advanceTimersByTimeAsync(1000);
  expect(fetcher.mock.calls[2][1].headers['Last-Event-ID']).toBe('3');
  expect(fetcher.mock.calls[1][0]).toContain('session%20with%20space');
  expect(fetcher.mock.calls[1][1].credentials).toBe('include');
  expect(logs).toHaveBeenLastCalledWith(['first', 'segundo ñ', 'third', 'fourth']);
});

it('un reset elimina historia de otro cursor y acepta los IDs recuperados', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(snapshot([{ id: 10, message: 'old' }]))
    .mockResolvedValueOnce(stream('id: 0\nevent: log-reset\ndata: {"reason":"cursor_ahead"}\n\nid: 1\ndata: "new"\n\n')));
  const logs = vi.fn();
  stop = subscribeDeploymentLogs('s', logs, vi.fn());
  await flush();
  expect(logs).toHaveBeenLastCalledWith(['new']);
});

it('muestra origen y timestamp del snapshot igual que el stream posterior', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({
    events: [{ id: 1, message: 'ready', source: 'application', timestamp: '2026-10-04T22:00:00Z' }], lastEventId: 1,
  }) }).mockResolvedValueOnce(stream('id: 2\ndata: "[2026-10-04T22:00:01Z] [database] ready"\n\n')));
  const logs = vi.fn();
  stop = subscribeDeploymentLogs('s', logs, vi.fn());
  await flush();
  expect(logs).toHaveBeenLastCalledWith(['[2026-10-04T22:00:00Z] [application] ready',
    '[2026-10-04T22:00:01Z] [database] ready']);
});

it('recupera historial por REST cuando falla SSE y vuelve a intentarlo', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(snapshot())
    .mockResolvedValueOnce({ ok: false, status: 503 })
    .mockResolvedValueOnce(snapshot([{ id: 8, message: 'recovered' }]))
    .mockResolvedValueOnce(stream());
  vi.stubGlobal('fetch', fetcher);
  const logs = vi.fn();
  const connection = vi.fn();
  stop = subscribeDeploymentLogs('s', logs, connection);
  await flush();
  expect(connection).toHaveBeenLastCalledWith('recovering');
  await vi.advanceTimersByTimeAsync(1000);
  expect(logs).toHaveBeenLastCalledWith(['recovered']);
  expect(fetcher.mock.calls[3][1].headers['Last-Event-ID']).toBe('8');
});

it('aborta una petición pendiente y no publica ni reconecta después de cancelar', async () => {
  let resolve: (value: any) => void = () => undefined;
  const fetcher = vi.fn().mockImplementation(() => new Promise(done => { resolve = done; }));
  vi.stubGlobal('fetch', fetcher);
  const logs = vi.fn();
  stop = subscribeDeploymentLogs('s', logs, vi.fn());
  stop();
  expect(fetcher.mock.calls[0][1].signal.aborted).toBe(true);
  resolve(snapshot([{ id: 1, message: 'late' }]));
  await flush();
  await vi.advanceTimersByTimeAsync(30000);
  expect(logs).not.toHaveBeenCalled();
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it('limita el historial a mil mensajes y cancela la espera de reconexión', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(snapshot())
    .mockResolvedValueOnce(stream(...Array.from({ length: 1005 }, (_, i) => `id: ${i + 1}\ndata: "${i}"\n\n`)));
  vi.stubGlobal('fetch', fetcher);
  const logs = vi.fn();
  stop = subscribeDeploymentLogs('s', logs, vi.fn());
  // Enough microtasks for all individual chunks.
  for (let i = 0; i < 1100; i++) await Promise.resolve();
  expect(logs.mock.lastCall?.[0]).toHaveLength(1000);
  expect(logs.mock.lastCall?.[0][0]).toBe('5');
  stop();
  await vi.advanceTimersByTimeAsync(30000);
  expect(fetcher).toHaveBeenCalledTimes(2);
});
