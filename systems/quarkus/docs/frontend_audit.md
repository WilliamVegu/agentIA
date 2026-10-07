# Frontend audit — fabricated results and hardcoded assumptions

Raised from a mock run: a nonsense prompt ("a ceviche") was accepted, and the
Architecture / Models-SQL / Blueprints tabs came back empty. Auditing the frontend
found **four places where the UI reports an outcome that did not happen**. Three are
fixed here; the rest are recorded with a recommended fix.

---

## 1. FIXED — the smoke test invented a passing result

`views/DevOpsDeploymentView.tsx` · `handleSmokeTest`

On any failure of the backend call, the catch block set:

```ts
status: 'SUCCESS', httpStatusCode: 200, latencyMs: 14,
message: 'Endpoint de salud verificado: Status UP en 14ms',
```

So pressing **"Ejecutar Smoke Test"** reported a healthy, verified endpoint that was
never contacted. This is the most serious of the four because it is a *verification
claim*, and it is exactly the dishonesty feature 012 removed from the backend
verifier.

**Fixed** to the third state the type already offers:

```ts
status: 'SKIPPED',
message: 'Smoke test NO ejecutado: <reason>. No se contactó ningún endpoint, así que
          esto no dice nada sobre el servicio (ni bueno ni malo).'
```

*verified* / *verified with findings* / *not evaluable* must never be conflated —
the same three-state rule the diagnostic channel uses.

## 2. FIXED — the REST console fabricated 200 / 201 / 204

`views/DevOpsDeploymentView.tsx` · `handleSendCustomRest`

Any `fetch` failure (container down, wrong port, CORS, DNS) fell into
`// Local simulated response fallback` and produced:

| Method | Fabricated |
| --- | --- |
| GET | `200` + the local orders array as JSON |
| POST | `201` + `{"id": 105, ...parsed, "status": "CONFIRMED"}` |
| DELETE | `204` + `{}` |

The operator reads `HTTP Status: 200` and a JSON body and concludes the generated API
answered. **Fixed**: the console now shows `NO HUBO RESPUESTA DEL SERVICIO`, the URL
attempted, the error, and a pointer to the deploy tab.

## 3. FIXED — the CRUD form fabricated a created record

`views/DevOpsDeploymentView.tsx` · `handleCreateOrderSubmit`

The failure path was a silent `catch {}`. The record was then added to the table with
an invented id (`orders.length + 101`), a defaulted status (`'CONFIRMED'`), and a log
line claiming `201 CREATED`. **The row appeared and the log showed a success whether
or not anything was called.**

**Fixed**: a failed request adds no row, logs `FAILED (<reason>)`, and surfaces the
error and the URL it tried.

## 4. FIXED — "Contenedores detenidos" on a failed stop

`handleStopContainers` reported success in its catch block. Now reports the failure
and warns that the displayed state may not reflect the host.

---

## OPEN — 5. `/api/v1/orders` is hardcoded in three places

`views/DevOpsDeploymentView.tsx` lines 227, 377, 401.

The CRUD form assumes the generated service exposes an **Order** entity. For any
blueprint without it — e.g. `hard-01` logistics (Shipment), `hard-08` clinic,
`hard-10` identity — the form posts to an endpoint that does not exist. Before fix 3,
the silent fallback hid the 404; now it reports it, which is an improvement but not a
cure.

**Recommended**: derive the path from the active session's blueprint entities (the
`/orchestrator/sessions/{id}/overview` response already carries the counts), or make
the endpoint an editable field defaulting to the first entity's resource. Until then
the REST console (now honest) can be pointed at the correct path manually.

## OPEN — 6. Offline mode ignores the prompt entirely

`services/requirements_service.py` · `_generate_mock_decomposition(raw_text, service_name)`

**`raw_text` is never read.** Proven:

```
prompt='Quiero un microservicio de órdenes…'  -> entities=['Order'] stories=3
prompt='a ceviche'                            -> entities=['Order'] stories=3
prompt=''                                     -> entities=['Order'] stories=3
prompt='asdkjhasd kjhasd kjhasd'              -> entities=['Order'] stories=3
```

Consequences:

- **A nonsense request cannot be rejected in mock mode.** There is nothing to reject:
  the fabricated Order blueprint is always valid, so the validator never sees a bad
  input. This is the reported "it didn't reject the ceviche".
- The generated spec has nothing to do with the request, so any downstream tab that
  does populate shows Order/orders content for a ceviche prompt — which reads as
  "hardcoded responses", because it is one.
- In **MODEL** mode the prompt *is* used (`transform_requirements`), so this is a
  mock-mode defect. It matters because mock is the default provider in the UI.

**Recommended**: (a) label offline output unmistakably as a fixed sample, not a
response to the prompt; (b) add an input-quality gate before the pipeline that
rejects obviously non-spec input in *both* modes, so the "did it reject nonsense"
question has an answer independent of the provider.

## OPEN — 7. The empty tabs: likely by design, needs a repro

The Architecture and Models-SQL views generate **on demand** (`architectureService.design`,
`modelsService.generate`) and otherwise load what the session workspace contains. The
pipeline writes `architecture.json` / `schema.sql` only when it reaches those phases.

So the most likely cause is the session mode, not a skipped step:

- `handleCreateQuickStart(isAuto=false)` → `lifecycle_mode: "GUIDED_STEP"` → only the
  Requirements phase runs, and the UI switches to tab 1. **Architecture, Models-SQL
  and Blueprints stay empty by design** until the user advances.
- `isAuto=true` → `AUTO_PILOT` → the pipeline runs every phase and writes the files.

**The "Monitor Live skips previous tasks" hypothesis is not supported by the code I
read**: the monitor's `useEffect`s only *react* to `phase_transition` /
`session_completed` / `session_blocked` events and refresh the overview; the only
trigger is the explicit `handleStartGeneration` button.

To confirm rather than assume, capture for the failing session: `lifecycleMode` and
`currentLifecyclePhase` from `GET /api/v1/sessions/{id}`, and whether
`architecture.json` / `schema.sql` exist in its workspace.

**Recommended** regardless of the cause: when a phase tab has no data because the
phase never ran, say so — "this phase has not run yet (Guided mode: advance from
Requirements)" — instead of rendering an empty panel that reads as a failure.

---

## The pattern

Every fixed item has the same shape: **a catch block turning "we do not know" into a
plausible success.** The backend spent a whole feature (012) removing exactly that
from the verifier. The frontend kept four instances of it, in the one screen a
stakeholder is most likely to demo. Worth a lint rule or a review checklist item:
*a catch block must not set a success status.*
