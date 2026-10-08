import { afterEach, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useSSE } from '../hooks/useSSE';

afterEach(() => vi.unstubAllGlobals());
it('limpia eventos/logs y descarta callbacks de conexiones anteriores', () => {
  const sources: any[] = [];
  class Source {
    onopen: any; onmessage: any; onerror: any;
    close = vi.fn(); addEventListener = vi.fn(); removeEventListener = vi.fn();
    constructor(_url: string) { sources.push(this); }
  }
  vi.stubGlobal('EventSource', Source);
  const view = renderHook(({ url }) => useSSE(url), { initialProps: { url: '/old' as string | null } });
  act(() => sources[0].onmessage({ data: '{"status":"COMPLETED","message":"old"}', lastEventId: '1' }));
  expect(view.result.current.lastEvent.status).toBe('COMPLETED');
  view.rerender({ url: '/new' });
  expect(sources[0].close).toHaveBeenCalled();
  expect(view.result.current.logs).toEqual([]);
  expect(view.result.current.lastEvent).toBeNull();
  act(() => sources[0].onmessage({ data: '{"message":"late"}', lastEventId: '2' }));
  expect(view.result.current.logs).toEqual([]);
  act(() => sources[1].onmessage({ data: '{"message":"new"}', lastEventId: '1' }));
  expect(view.result.current.logs[0].message).toBe('new');
  view.rerender({ url: null });
  expect(view.result.current.logs).toEqual([]);
  expect(view.result.current.lastEvent).toBeNull();
});


it('deduplica mensajes y solicita resync aunque el ID ya se haya visto', () => {
  const sources: any[] = [];
  class Source {
    onmessage: any; onopen: any; onerror: any;
    close = vi.fn(); removeEventListener = vi.fn();
    handlers = new Map<string, any>();
    addEventListener = (name: string, handler: any) => this.handlers.set(name, handler);
    constructor(_url: string) { sources.push(this); }
  }
  vi.stubGlobal('EventSource', Source);
  const received = vi.fn();
  window.addEventListener('agentia:session-resync', received);
  const view = renderHook(() => useSSE('/session/stream'));
  try {
    act(() => {
      sources[0].onmessage({data:'{"sessionId":"one","message":"first"}',lastEventId:'10'});
      sources[0].onmessage({data:'{"sessionId":"one","message":"first"}',lastEventId:'10'});
    });
    expect(view.result.current.logs).toHaveLength(1);
    act(() => sources[0].handlers.get('resync_required')({type:'resync_required',data:'{"sessionId":"one","snapshot":{"status":"PAUSED"}}',lastEventId:'10'}));
    expect(received).toHaveBeenCalledTimes(1);
    expect(view.result.current.logs).toHaveLength(1);
    expect(view.result.current.lastEvent.snapshot.status).toBe('PAUSED');
  } finally {
    view.unmount();
    window.removeEventListener('agentia:session-resync', received);
  }
});
