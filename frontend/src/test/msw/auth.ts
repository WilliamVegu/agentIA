import { http, HttpResponse, pathEndsWith } from './server';

/**
 * The studio authenticates against the server now: `App` renders a boot gate until
 * `GET /auth/session` answers, and every `/api/v1` route is guarded by a session cookie.
 * A test that renders the app therefore has to answer that call, exactly as a browser
 * would -- there is no client-side demo user to fall back on any more.
 *
 * These handlers are shared rather than repeated per file because the shape of the user is
 * a contract: when it changes, every test that renders the shell should fail in one place.
 */
export const DEMO_USER = {
  email: 'mvp@localhost',
  name: 'MVP local',
  role: 'Architect',
  accessMode: 'mvp',
};

/**
 * An authenticated session, plus the endpoints the shell calls on mount.
 *
 * Pass `user: null` to simulate a visitor with no session.
 */
export const authHandlers = (user: typeof DEMO_USER | null = DEMO_USER) => [
  http.get(pathEndsWith('/auth/session'), () =>
    user ? HttpResponse.json(user) : HttpResponse.json({ detail: 'Authentication required' }, { status: 401 }),
  ),
  http.post(pathEndsWith('/auth/logout'), () => HttpResponse.json({ success: true })),
  http.post(pathEndsWith('/auth/mvp'), () => (user ? HttpResponse.json(user) : HttpResponse.json({ detail: 'Forbidden' }, { status: 403 }))),
];
