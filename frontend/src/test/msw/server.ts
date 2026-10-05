import { setupServer } from 'msw/node';
import type { HttpHandler } from 'msw';
import { http, HttpResponse } from 'msw';

/**
 * A backend simulated at the HTTP boundary.
 *
 * The existing view tests replace `sessionService`, `orchestratorService` and friends with
 * `vi.mock` factories, so nothing below the component is exercised: the request the app
 * actually sends -- its URL, method, params, body and headers -- is never built, and the
 * response shape is whatever the test author typed rather than what the backend returns.
 * Registering the fake here instead means the real service modules, the real axios client
 * and its interceptors all run, and the contract between the two halves is what gets
 * asserted.
 */
export const server = setupServer();

export const API_PREFIX = '/api/v1';

/**
 * Match a request path in a full URL, with a boundary so `/sessions` does not also match
 * `/sessions/quick-start`.
 */
export const pathEndsWith = (suffix: string) => {
  const escaped = suffix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`${API_PREFIX}${escaped}(\\?|$)`);
};

/** Match a path shape, e.g. ``apiPath('/sessions/[^/?]+$')`` for a session by id. */
export const apiPath = (pattern: string) => new RegExp(`${API_PREFIX}${pattern}`);

export { http, HttpResponse } from 'msw';

export const useHandlers = (...handlers: HttpHandler[]) => {
  server.use(...handlers);
};

export const registerLocalAuth = () => {
  const user = { name: 'Rodrigo Mendoza', email: 'rodrigo@tcs.com', role: 'Developer', accessMode: 'authenticated' };
  server.use(
    http.get(pathEndsWith('/auth/session'), () => HttpResponse.json(user)),
    http.post(pathEndsWith('/auth/logout'), () => HttpResponse.json({ success: true })),
    http.post(pathEndsWith('/auth/mvp'), () => HttpResponse.json({ ...user, accessMode: 'mvp' })),
  );
};
