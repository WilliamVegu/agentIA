/**
 * Frontend workflow journeys, driven at the HTTP boundary.
 *
 * Every existing frontend test replaces the service layer with `vi.mock` factories, which
 * means the app never builds a request: the URL, method, params, body and headers are all
 * unverified, and the response shape is whatever the test author typed. A backend that
 * renamed a query parameter would keep 64 passing tests.
 *
 * These journeys register a fake backend with MSW instead, so the **real** service
 * modules, the real axios client and its interceptors, and the real views all run. What is
 * asserted is therefore the contract between the two halves of the product, plus the
 * properties the repo cares about most:
 *
 *  * the credentials travel in a header and never reach storage (Principle VI);
 *  * a failing backend produces a failure, not a fabricated success -- the class of defect
 *    `docs/frontend_audit.md` recorded four of.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse, server, pathEndsWith, apiPath } from './msw/server';
import { App } from '../App';
import { sessionService } from '../services/sessionService';
import { orchestratorService } from '../services/orchestratorService';
import { exportService } from '../services/exportService';
import { devopsService } from '../services/devopsService';
import { setEphemeralLlmCredentials } from '../services/apiClient';
import { authHandlers } from './msw/auth';

type Captured = {
  method: string;
  path: string;
  search: string;
  body: any;
  headers: Record<string, string>;
};

const captured: Captured[] = [];

async function capture(request: Request): Promise<void> {
  let body: any = null;
  try {
    body = await request.clone().json();
  } catch {
    body = null;
  }
  const headers: Record<string, string> = {};
  request.headers.forEach((value, key) => {
    headers[key.toLowerCase()] = value;
  });
  const url = new URL(request.url);
  captured.push({
    method: request.method,
    path: url.pathname,
    search: url.search,
    body,
    headers,
  });
}

const lastRequest = () => captured[captured.length - 1];

const SESSION_ID = 'sess-journey-1';

const SESSION_LIST_ITEM = {
  sessionId: SESSION_ID,
  specId: 'spec-journey-1',
  specName: 'orders-service',
  status: 'QUEUED',
  currentLifecyclePhase: 'REQUIREMENTS',
  lifecycleMode: 'GUIDED_STEP',
  completionPercentage: 0,
  createdAt: '2026-09-29T00:00:00Z',
};

const DEPLOYMENT_RUNNING = {
  sessionId: SESSION_ID,
  serviceName: 'orders-service',
  status: 'RUNNING',
  hostPort: 8080,
  dbEngine: 'POSTGRESQL',
  healthStatus: 'UP',
  message: 'running',
};

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => {
  server.resetHandlers();
  captured.length = 0;
  localStorage.clear();
  sessionStorage.clear();
  setEphemeralLlmCredentials('', 'mock');
});
afterAll(() => server.close());

/**
 * Every journey starts from an authenticated session.
 *
 * The studio authenticates against the server, so `App` shows a boot gate until
 * `GET /auth/session` answers and refuses every other `/api/v1` call without a cookie.
 * Registering the session here is what makes the rest of the journey reachable at all.
 */
beforeEach(() => {
  server.use(...authHandlers());
});

// ===========================================================================
// The request the frontend actually sends
// ===========================================================================
describe('Flujo de trabajo: contratos de petición y respuesta', () => {
  it('crea una sesión por inicio rápido y la lee de vuelta', async () => {
    server.use(
      http.post(pathEndsWith('/sessions/quick-start'), async ({ request }) => {
        await capture(request);
        return HttpResponse.json(
          {
            sessionId: SESSION_ID,
            specId: 'spec-journey-1',
            specName: 'orders-service',
            status: 'QUEUED',
            currentLifecyclePhase: 'REQUIREMENTS',
            lifecycleMode: 'GUIDED_STEP',
            pipelineStarted: false,
            message: 'Sesión creada e inicializada correctamente.',
          },
          { status: 201 },
        );
      }),
      http.get(pathEndsWith('/sessions'), async ({ request }) => {
        await capture(request);
        return HttpResponse.json([SESSION_LIST_ITEM]);
      }),
      http.get(apiPath('/sessions/[^/?]+$'), async ({ request }) => {
        await capture(request);
        return HttpResponse.json({
          id: SESSION_ID,
          specId: 'spec-journey-1',
          specName: 'orders-service',
          status: 'QUEUED',
          phase: 'INITIALIZATION',
          queuePosition: 0,
          repairAttempts: 0,
          createdAt: '2026-09-29T00:00:00Z',
        });
      }),
    );

    const created = await sessionService.quickStart({
      service_name: 'orders-service',
      prompt: 'un servicio de pedidos',
      database: 'POSTGRESQL',
      auto_run: false,
    });
    const list = await sessionService.listSessions();
    const detail = await sessionService.getSession(SESSION_ID);

    expect(created.sessionId).toBe(SESSION_ID);
    expect(list[0].specName).toBe('orders-service');
    expect(detail.id).toBe(SESSION_ID);

    const [quickStart, listCall, detailCall] = captured;
    expect(quickStart.method).toBe('POST');
    expect(quickStart.path).toBe('/api/v1/sessions/quick-start');
    expect(quickStart.body).toEqual({
      service_name: 'orders-service',
      prompt: 'un servicio de pedidos',
      database: 'POSTGRESQL',
      auto_run: false,
    });

    expect(listCall.method).toBe('GET');
    expect(listCall.path).toBe('/api/v1/sessions');
    expect(listCall.search).toBe('?limit=50');

    expect(detailCall.method).toBe('GET');
    expect(detailCall.path).toBe(`/api/v1/sessions/${SESSION_ID}`);
  });

  it('recorre el ciclo de control del Auto-Pilot: ejecutar, pausar, reanudar y cancelar', async () => {
    const ok = (payload: any = { status: 'RUNNING' }) =>
      async ({ request }: { request: Request }) => {
        await capture(request);
        return HttpResponse.json(payload);
      };

    server.use(
      http.post(pathEndsWith('/orchestrator/pipeline/run'), ok({ started: true })),
      http.post(apiPath('/orchestrator/pipeline/[^/]+/pause'), ok({ paused: true })),
      http.post(apiPath('/orchestrator/pipeline/[^/]+/resume'), ok({ resumed: true })),
      http.post(apiPath('/orchestrator/pipeline/[^/]+/cancel'), ok({ cancelled: true })),
    );

    await orchestratorService.runPipeline({
      session_id: SESSION_ID,
      target_phase: 'DEVOPS_DEPLOY',
      stop_on_gate: true,
      auto_deploy: false,
    });
    await orchestratorService.pausePipeline(SESSION_ID);
    await orchestratorService.resumePipeline(SESSION_ID);
    await orchestratorService.cancelPipeline(SESSION_ID);

    expect(captured.map((c) => [c.method, c.path])).toEqual([
      ['POST', '/api/v1/orchestrator/pipeline/run'],
      ['POST', `/api/v1/orchestrator/pipeline/${SESSION_ID}/pause`],
      ['POST', `/api/v1/orchestrator/pipeline/${SESSION_ID}/resume`],
      ['POST', `/api/v1/orchestrator/pipeline/${SESSION_ID}/cancel`],
    ]);
    expect(captured[0].body).toEqual({
      session_id: SESSION_ID,
      target_phase: 'DEVOPS_DEPLOY',
      stop_on_gate: true,
      auto_deploy: false,
    });
  });

  it('lee el resumen y el ciclo de vida de la sesión activa', async () => {
    server.use(
      http.get(apiPath('/orchestrator/sessions/[^/]+/overview'), async ({ request }) => {
        await capture(request);
        // Mirrors the real payload. The previous fixture used the invented shape the
        // frontend type declared, so this test passed for months while every studio
        // overview card in the running app rendered a fallback literal -- the mock and
        // the type agreed with each other and neither agreed with the API.
        return HttpResponse.json({
          sessionId: SESSION_ID,
          specName: 'orders-service',
          databaseEngine: 'POSTGRESQL',
          framework: 'Java 21 / Spring Boot 3',
          userStoriesCount: 3,
          entitiesCount: 1,
          testsPassed: true,
          securityAuditVerdict: 'PASS',
          deploymentStatus: 'IDLE',
          deploymentUrl: null,
          pipelineStatus: 'COMPLETED',
          lifecycle: { completionPercentage: 14.3 },
        });
      }),
      http.get(apiPath('/orchestrator/sessions/[^/]+/lifecycle'), async ({ request }) => {
        await capture(request);
        return HttpResponse.json({
          sessionId: SESSION_ID,
          pipelineStatus: 'IDLE',
          completionPercentage: 14.3,
          phases: [
            { phase: 'REQUIREMENTS', status: 'COMPLETED', title: '1. Requisitos' },
          ],
        });
      }),
    );

    const overview = await orchestratorService.getOverview(SESSION_ID);
    const lifecycle = await orchestratorService.getLifecycle(SESSION_ID);

    // `completionPercentage` was never a field on the overview payload -- the real one
    // is nested under `lifecycle`. Asserting the invented name is what let the type
    // drift this far from the API without a single test noticing.
    expect((overview.lifecycle as { completionPercentage?: number })?.completionPercentage).toBe(14.3);
    expect(lifecycle.phases).toHaveLength(1);
    expect(captured[0].path).toBe(`/api/v1/orchestrator/sessions/${SESSION_ID}/overview`);
    expect(captured[1].path).toBe(`/api/v1/orchestrator/sessions/${SESSION_ID}/lifecycle`);
  });

  it('lista los artefactos y compone la URL de descarga del paquete', async () => {
    server.use(
      http.get(apiPath('/sessions/[^/]+/artifacts'), async ({ request }) => {
        await capture(request);
        return HttpResponse.json([
          {
            id: 'a1',
            sessionId: SESSION_ID,
            relativePath: 'pom.xml',
            fileType: 'xml',
            sizeBytes: 2048,
          },
        ]);
      }),
    );

    const artifacts = await exportService.listArtifacts(SESSION_ID);

    expect(artifacts[0].relativePath).toBe('pom.xml');
    expect(captured[0].path).toBe(`/api/v1/sessions/${SESSION_ID}/artifacts`);
    expect(exportService.getDownloadZipUrl(SESSION_ID)).toBe(
      `/api/v1/sessions/${SESSION_ID}/export`,
    );
  });
});

// ===========================================================================
// The properties the product promises
// ===========================================================================
describe('Flujo de trabajo: garantías del producto', () => {
  it('transporta la credencial en una cabecera y no la persiste en ningún almacenamiento', async () => {
    // Principle VI: the key is ephemeral and lives in memory only. The header is the
    // only place it may appear -- not in the URL, not in localStorage, not in sessionStorage.
    const secret = 'sk-journey-must-never-be-stored';
    setEphemeralLlmCredentials(secret, 'deepseek');
    server.use(
      http.get(pathEndsWith('/sessions'), async ({ request }) => {
        await capture(request);
        return HttpResponse.json([]);
      }),
    );

    await sessionService.listSessions();

    expect(lastRequest().headers['x-llm-api-key']).toBe(secret);
    expect(lastRequest().headers['x-llm-provider']).toBe('deepseek');
    expect(lastRequest().search).not.toContain(secret);
    expect(JSON.stringify(localStorage)).not.toContain(secret);
    expect(JSON.stringify(sessionStorage)).not.toContain(secret);
  });

  it('propaga el fallo del backend en lugar de inventar una respuesta', async () => {
    server.use(
      http.get(pathEndsWith('/sessions'), () =>
        HttpResponse.json({ status: 500, message: 'boom' }, { status: 500 }),
      ),
    );

    await expect(sessionService.listSessions()).rejects.toBeTruthy();
  });

  it('propaga el fallo de la comprobación de salud en lugar de informar un contenedor sano', async () => {
    // The recorded defect: this used to fabricate status 'SUCCESS', code 200 and a 14 ms
    // latency on ANY failure, so pressing the button reported a verified endpoint that was
    // never contacted. The service must reject; the view turns that into "not executed".
    server.use(
      http.post(apiPath('/devops/[^/]+/smoke-test'), () =>
        HttpResponse.json({ message: 'connection refused' }, { status: 502 }),
      ),
    );

    await expect(devopsService.runSmokeTest(SESSION_ID)).rejects.toBeTruthy();
  });
});

// ===========================================================================
// The workflow through the real views
// ===========================================================================
describe('Flujo de trabajo en la interfaz', () => {
  it('crea un microservicio desde el formulario y envía el asunto al backend', async () => {
    server.use(
      http.get(pathEndsWith('/sessions'), async ({ request }) => {
        await capture(request);
        return HttpResponse.json([]);
      }),
      http.post(pathEndsWith('/sessions/quick-start'), async ({ request }) => {
        await capture(request);
        return HttpResponse.json(
          {
            sessionId: SESSION_ID,
            specId: 'spec-journey-1',
            specName: 'orders-service',
            status: 'QUEUED',
            currentLifecyclePhase: 'REQUIREMENTS',
            lifecycleMode: 'GUIDED_STEP',
            pipelineStarted: false,
            message: 'ok',
          },
          { status: 201 },
        );
      }),
      http.get(apiPath('/orchestrator/sessions/[^/]+/overview'), async ({ request }) => {
        await capture(request);
        return HttpResponse.json({
          sessionId: SESSION_ID,
          serviceName: 'orders-service',
          database: 'POSTGRESQL',
          totalStories: 0,
          totalEntities: 0,
          totalEndpoints: 0,
          testSuitesCount: 0,
          qualityGateStatus: 'PENDING',
          qualityScore: 0,
          deploymentStatus: 'IDLE',
          activePhase: 'REQUIREMENTS',
          completionPercentage: 0,
        });
      }),
      http.get(apiPath('/orchestrator/sessions/[^/]+/lifecycle'), async ({ request }) => {
        await capture(request);
        return HttpResponse.json({
          sessionId: SESSION_ID,
          pipelineStatus: 'IDLE',
          completionPercentage: 0,
          phases: [],
        });
      }),
    );

    render(<App />);

    const nameInput = await screen.findByPlaceholderText('ej. order-fulfillment-service');
    const promptInput = screen.getByPlaceholderText(
      'Describa el objetivo de negocio, entidades principales, validaciones y reglas requeridas...',
    );

    fireEvent.change(nameInput, { target: { value: 'orders-service' } });
    fireEvent.change(promptInput, { target: { value: 'un servicio de pedidos' } });

    const guided = await screen.findByText('👣 Crear e Iniciar Modo Asistido');
    fireEvent.click(guided.closest('button')!);

    await waitFor(() => {
      const posted = captured.find((c) => c.path === '/api/v1/sessions/quick-start');
      expect(posted).toBeTruthy();
      expect(posted!.body.service_name).toBe('orders-service');
      expect(posted!.body.prompt).toBe('un servicio de pedidos');
    });
  });

  it('informa que el smoke test NO se ejecutó cuando el backend falla', async () => {
    // The end-to-end version of the guarantee asserted above: the view must render the
    // third state ("not evaluable"), never a green success it did not observe.
    server.use(
      http.get(pathEndsWith('/sessions'), () => HttpResponse.json([SESSION_LIST_ITEM])),
      http.get(apiPath('/orchestrator/sessions/[^/]+/overview'), () =>
        HttpResponse.json({
          sessionId: SESSION_ID,
          serviceName: 'orders-service',
          database: 'POSTGRESQL',
          totalStories: 3,
          totalEntities: 1,
          totalEndpoints: 4,
          testSuitesCount: 2,
          qualityGateStatus: 'PASS',
          qualityScore: 98,
          deploymentStatus: 'RUNNING',
          activePhase: 'DEVOPS_DEPLOY',
          completionPercentage: 100,
        }),
      ),
      http.get(apiPath('/orchestrator/sessions/[^/]+/lifecycle'), () =>
        HttpResponse.json({
          sessionId: SESSION_ID,
          pipelineStatus: 'COMPLETED',
          completionPercentage: 100,
          phases: [],
        }),
      ),
      http.get(apiPath('/devops/[^/]+/status'), () => HttpResponse.json(DEPLOYMENT_RUNNING)),
      http.get(apiPath('/devops/[^/]+/logs'), () => HttpResponse.json({ logs: [] })),
      http.post(apiPath('/devops/[^/]+/smoke-test'), () =>
        HttpResponse.json({ message: 'connection refused' }, { status: 502 }),
      ),
    );

    render(<App />);

    // The active session is chosen by the context from the list call; tab 8's status
    // effect re-runs once it is set, so waiting on the button is enough.
    fireEvent.click(await screen.findByTitle('6. DevOps & Demo'));

    const smokeButton = await screen.findByText('🧪 Ejecutar Smoke Test');
    const button = smokeButton.closest('button')!;
    await waitFor(() => expect(button).not.toBeDisabled());

    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText(/Smoke test NO ejecutado/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Endpoint de salud verificado/i)).not.toBeInTheDocument();
  });
});
