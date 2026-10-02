# Anexo A — Fragmentos de código de las pruebas

Este anexo muestra **cómo está escrito** un caso de prueba en este proyecto, por tipo. Cada
fragmento es código real del repositorio, no un ejemplo inventado.

La regla que gobierna todos ellos: **se falsea la frontera que no es nuestra; jamás el sujeto
bajo prueba.** Y la estructura siempre es la misma: *Arrange* (montar el mundo), *Act* (una
sola acción), *Assert* (el contrato, no la implementación).

---

## 1. Prueba unitaria: la regla de negocio aislada

El límite constitucional de 3 intentos de auto-reparación (Principio V). Se prueba en el borde:
con 3 intentos debe bloquear, con 2 no.

```python
def test_a_blocked_repair_loop_blocks_phase_five_and_the_whole_session(session):
    """Principle V: three failed repairs stop the pipeline and wait for a human.

    ``can_advance`` is what the UI reads to decide whether to offer the next step, so a
    BLOCKED phase that still allowed advancing would silently defeat the limit.
    """
    session_id, ws = session
    _make_session(session_id, status=SessionStatus.BLOCKED, repair_attempts=3)
    _complete_through_phase_4(ws)
    _complete_phase_5(ws)

    state = lifecycle.get_session_lifecycle(session_id)

    assert state.phases[4].status == PhaseStatus.BLOCKED
    assert "3 auto-reparaciones" in state.phases[4].blocking_reason
    assert state.can_advance is False
```

**Por qué está escrito así.** La afirmación no es «la fase 5 existe», sino «el sistema se
detiene y **dice por qué**». Esa segunda parte es la que descubrió el defecto **D-02**: la fase
se reportaba `BLOCKED` correctamente, pero la razón se calculaba en una variable que nadie leía.

---

## 2. Partir el espacio de entrada en lugar de repetir código

Seis posiciones de pausa, un caso parametrizado. Cada parámetro ejercita **una frontera
distinta** del mismo código; escribirlos como seis funciones sería seis veces el mismo texto.

```python
STEP_ARTIFACTS = [
    (LifecyclePhase.REQUIREMENTS, "user_stories.json"),
    (LifecyclePhase.STORIES, "architecture.json"),
    (LifecyclePhase.ARCHITECTURE, "schema.sql"),
    (LifecyclePhase.DATA_MODEL, "pom.xml"),
    (LifecyclePhase.CODE_TESTS, "docker-compose.yml"),
    (LifecyclePhase.SECURITY_AUDIT, "docker-compose.yml"),
]

@pytest.mark.parametrize("pause_after,next_artifact", STEP_ARTIFACTS,
                         ids=[p.value for p, _ in STEP_ARTIFACTS])
def test_pausing_after_a_step_stops_before_the_next_one(session, monkeypatch,
                                                       pause_after, next_artifact):
    """A pause must take effect at the *next* boundary, not after the whole run."""
    ...
    assert pr._pipeline_statuses[session_id] == PipelineRunStatus.PAUSED
    assert not (ws / next_artifact).exists(), (
        f"the step after {pause_after.value} ran despite the pause"
    )
```

---

## 3. Doble de prueba fiel: el hilo que se ejecuta en línea

`deploy_local` devuelve el control en cuanto lanza su hilo trabajador. Una prueba que esperase a
que terminara sería lenta en una máquina descargada y fallida en una cargada. Se sustituye el
**hilo**, no la función:

```python
class _InlineThread:
    """Runs the compose worker on the calling thread.

    ``deploy_local`` returns the moment it spawns the worker, so the only way to
    assert on a *finished* deployment without sleeping is to make ``start()`` run the
    target inline. A test that polled the module dict for up to N seconds would pass
    on a fast machine and fail on a loaded one.
    """

    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        self._target()


@pytest.fixture(autouse=True)
def clean_deploy_state(monkeypatch):
    """Isolate the module-level stores, which are process-global by design.

    Without this, one test's deployment row leaks into the next and
    ``get_deployment_status`` returns another test's session -- the classic way a
    suite becomes order-dependent.
    """
    monkeypatch.setattr(ds, "_active_deployments", {})
    monkeypatch.setattr(ds, "_log_queues", {})
    monkeypatch.setattr(ds, "_raw_log_history", {})
    monkeypatch.setattr(ds.threading, "Thread", _InlineThread)
    yield
```

---

## 4. Prueba negativa: forzar el fallo de una dependencia

El respaldo del esquema SQL. Este caso ejecutó por primera vez una rama que nunca se había
ejecutado, y encontró el defecto **D-05**.

```python
def test_a_failed_schema_synthesis_falls_back_to_this_blueprints_own_ddl(session, monkeypatch):
    """The fallback must derive from the blueprint.

    The previous fallback wrote a hardcoded ``items`` table whatever the service was
    about, so the shipped schema contradicted the JPA entities beside it.
    """
    session_id, ws = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch)

    def explode(*args, **kwargs):
        raise RuntimeError("synthesis unavailable")

    monkeypatch.setattr(pr.model_sql_service, "synthesize_domain_models_and_sql", explode)

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False)

    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.COMPLETED, (
        "the run died in the fallback instead of falling back"
    )
    schema = (ws / "schema.sql").read_text(encoding="utf-8")
    assert schema.strip(), "the fallback left an empty schema.sql behind"
    assert "items" not in schema.lower(), "the hardcoded fallback table came back"
    assert "orders" in schema.lower(), "the fallback did not use this blueprint's entity"
```

---

## 5. Hermetismo de la suite: ninguna prueba toca la red

```python
@pytest.fixture(autouse=True)
def no_outbound_telemetry(tmp_path, monkeypatch):
    """Keep the suite hermetic: no test may reach the telemetry destination over the wire.

    ... With MLflow's stock HTTP defaults (120 s timeout, 5 retries) that blocked the
    whole suite for minutes on a host with no tracking server, so the suite could not be
    run to completion and coverage could not be measured at all.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", (tmp_path / "mlruns").as_uri())
```

**Decisión de diseño.** Se **redirige** el destino, no se anula. Anularlo habría vuelto vacía
`test_the_local_store_is_written_even_when_the_mirror_is_absent`, que afirma que el espejo
*sí* fue consultado.

---

## 6. Prueba de contrato en el frontend: la petición real, en la frontera HTTP

Lo que faltaba por completo: las 64 pruebas anteriores sustituían la capa de servicios, así que
**ninguna construía una petición**. Aquí se ejecutan los módulos de servicio reales, el cliente
HTTP real y las vistas reales, contra un backend simulado.

```ts
it('crea una sesión por inicio rápido y la lee de vuelta', async () => {
  server.use(
    http.post(pathEndsWith('/sessions/quick-start'), async ({ request }) => {
      await capture(request);                       // espía: registra la petición real
      return HttpResponse.json({ sessionId: SESSION_ID, ... }, { status: 201 });
    }),
    http.get(pathEndsWith('/sessions'), async ({ request }) => {
      await capture(request);
      return HttpResponse.json([SESSION_LIST_ITEM]);
    }),
  );

  const created = await sessionService.quickStart({
    service_name: 'orders-service',
    prompt: 'un servicio de pedidos',
    database: 'POSTGRESQL',
    auto_run: false,
  });
  const list = await sessionService.listSessions();

  expect(created.sessionId).toBe(SESSION_ID);
  expect(list[0].specName).toBe('orders-service');

  const [quickStart, listCall] = captured;
  expect(quickStart.method).toBe('POST');
  expect(quickStart.path).toBe('/api/v1/sessions/quick-start');
  expect(quickStart.body).toEqual({
    service_name: 'orders-service',
    prompt: 'un servicio de pedidos',
    database: 'POSTGRESQL',
    auto_run: false,
  });
  expect(listCall.path).toBe('/api/v1/sessions');
  expect(listCall.search).toBe('?limit=50');       // el contrato de los parámetros
});
```

---

## 7. Principio VI verificado en el cliente

```ts
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
  expect(lastRequest().search).not.toContain(secret);
  expect(JSON.stringify(localStorage)).not.toContain(secret);
  expect(JSON.stringify(sessionStorage)).not.toContain(secret);
});
```

---

## 8. Flujo de usuario de extremo a extremo, y la honestidad del resultado

Se recorre la aplicación real —sesión iniciada, pestaña DevOps— y se provoca el fallo del
endpoint de salud. El contrato es que la interfaz informe **«no ejecutado»**, nunca un éxito
que nadie observó.

```tsx
it('informa que el smoke test NO se ejecutó cuando el backend falla', async () => {
  server.use(
    http.get(pathEndsWith('/sessions'), () => HttpResponse.json([SESSION_LIST_ITEM])),
    http.get(apiPath('/devops/[^/]+/status'), () => HttpResponse.json(DEPLOYMENT_RUNNING)),
    http.post(apiPath('/devops/[^/]+/smoke-test'),
              () => HttpResponse.json({ message: 'connection refused' }, { status: 502 })),
  );

  render(<App />);
  fireEvent.click(await screen.findByTitle('6. DevOps & Demo'));

  const button = (await screen.findByText('🧪 Ejecutar Smoke Test')).closest('button')!;
  await waitFor(() => expect(button).not.toBeDisabled());
  fireEvent.click(button);

  await waitFor(() => {
    expect(screen.getByText(/Smoke test NO ejecutado/i)).toBeInTheDocument();
  });
  expect(screen.queryByText(/Endpoint de salud verificado/i)).not.toBeInTheDocument();
});
```

---

## 9. Prueba de seguridad que ataca, no que confirma

```python
def test_the_guard_cannot_be_bypassed_with_a_header(loopback):
    """A cookie is the only credential. No header may stand in for it."""
    for header in (
        {"X-Session-ID": "anything"},
        {"X-User": "mvp@localhost"},
        {"Authorization": "Bearer whatever"},
        {"X-Forwarded-For": "127.0.0.1"},
    ):
        assert loopback.get(PROTECTED, headers=header).status_code == 401, header
```

---

## 10. El arnés que permitió reparar 154 pruebas sin debilitar ninguna

Cuando llegó la autenticación de sesión, 154 pruebas existentes empezaron a fallar con `401`.
La reparación **no** fue desactivar el control: es un cliente que entra por el endpoint real.

```python
class AuthenticatedTestClient(TestClient):
    """A ``TestClient`` that has already entered the local MVP session."""

    def __init__(self, app: Any, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("base_url", LOOPBACK_BASE_URL)
        kwargs.setdefault("client", LOOPBACK_CLIENT)
        super().__init__(app, *args, **kwargs)
        try:
            self.post("/api/v1/auth/mvp")     # el endpoint real concede la cookie
        except Exception:                     # construction must never explode
            pass
```

**Por qué es la solución correcta y no un atajo.** Se sigue ejercitando el *middleware* real, el
almacén de sesiones real y la ruta de cookie real. Y `PLAIN_TEST_CLIENT` queda disponible para
los casos cuyo sujeto es precisamente la *ausencia* de sesión, de modo que «esta prueba trata
sobre no estar autenticado» es una decisión visible y no un accidente del arnés.
