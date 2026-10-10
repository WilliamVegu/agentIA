# Copilot instructions for AgentIA

## Repository shape

This repo is a full-stack app for generating and validating Java 21 / Spring Boot microservices from natural-language specs. The two main runtime pieces are:

- `backend/`: FastAPI application that exposes the orchestration API, workspace/session management, security checks, DevOps outputs, and the LangGraph-driven generation pipeline.
- `frontend/`: React + Vite + TypeScript UI that drives the Studio workflow and calls the backend via REST/SSE.

The app is not a simple CRUD app: the important behavior is orchestrated across multiple layers in `backend/app/`:

- `app/api/` contains route modules such as `routes_requirements.py`, `routes_architecture.py`, `routes_models_sql.py`, `routes_security.py`, `routes_devops.py`, and `routes_orchestrator.py`.
- `app/services/` contains the domain logic (`requirements_service.py`, `security_service.py`, `devops_service.py`, `workspace_guard.py`, etc.).
- `app/orchestrator/` contains the LangGraph pipeline graph and repair/sandbox nodes used to generate and validate microservice code.
- `backend/workspaces/` and related session artifacts hold generated project output and runtime state.

The runtime entry points are `backend/app/main.py` (FastAPI app) and `scripts/start_services.sh` (starts the app stack: MLflow, backend, frontend). The frontend is a TypeScript React app with Vite/Vitest tests under `frontend/src/test`.

## Build, test, and lint commands

### Backend

This repo’s Python test setup is configured in `pytest.ini`:

```bash
# run the full backend test suite
python -m pytest backend/tests -o pythonpath=backend
```

For a single backend test file:

```bash
python -m pytest backend/tests/test_routes_orchestrator.py -q
python -m pytest backend/tests/test_security_service.py -k "secret or quality" -q
```

If you are working from the project root and want the repo’s test path and `pythonpath` defaults to apply, prefer the repo config rather than ad-hoc `PYTHONPATH` workarounds.

### Frontend

From `frontend/`:

```bash
cd frontend
npm install
npm run dev
npm run build
npm test -- --run src/test/auth.test.tsx
npx vitest run src/test/views_overview_reqs.test.tsx
```

`frontend/package.json` defines the front-end scripts:

- `npm run dev` -> Vite dev server
- `npm run build` -> `tsc && vite build`
- `npm test` -> `vitest run --no-file-parallelism`

There is no repo-level lint script configured in the root; linting is not part of the checked workflow unless a specific subproject adds it.

### Local stack startup

The supported local stack start command is:

```bash
./scripts/start_services.sh
```

This starts MLflow, the FastAPI backend, and the React frontend with built-in health checks. The script is intentionally strict about not killing unrelated services and writes logs under `.run/logs`.

## High-level architecture and execution flow

The app models a workflow that moves from requirements to generated Java microservices:

1. The UI collects specifications, requirements, architecture decisions, and session context.
2. The FastAPI backend exposes the major workflow endpoints (`/api/v1/requirements`, `/api/v1/architecture`, `/api/v1/models`, `/api/v1/security`, `/api/v1/devops`, `/api/v1/orchestrator`).
3. The orchestrator layer (`backend/app/orchestrator/`) runs the generation pipeline and repair loop. This is the repo’s central “gen AI + validation” logic.
4. The sandbox layer (`backend/app/sandbox/`) executes hermetic verification (Docker + Maven in offline mode), and repair logic re-runs failed builds under constraints.
5. Generated artifacts are stored in session/workspace folders and surfaced to the frontend for review, export, or publication.

The most important architectural constraint in this codebase is the “hermetic generation and verification” model: the README and runtime logic emphasize Dockerized offline validation rather than ad-hoc local compile/test behavior.

## Key repo conventions

- Backend is FastAPI-first, not Flask or plain WSGI. Route modules are mounted in `app.main` with dynamic import guards.
- The app uses authenticated API access for most `/api/v1/*` routes; public routes are explicitly whitelisted in `backend/app/main.py`.
- Session-scoped workspaces and `X-Session-ID` validation are first-class concerns for guided generation flows (`workspace_guard.py` and the middleware in `app.main`). Do not assume a session can be used without a valid session/workspace path.
- The product is centered on structured generation from formal inputs (specs, BDD stories, architecture, SQL models) and then automated verification. Prefer changes that preserve the generation pipeline and validation loop rather than patching isolated UI-only behavior.
- Most backend logic is organized by concern, not by a single giant module. If you need to change behavior, look in the route + service + model path together rather than editing a single file in isolation.
- `backend/app/config.py` and settings drive app config, including CORS, app metadata, and environment switches. Keep environment-driven behavior aligned with those settings instead of hard-coding ports or service names.
- The frontend uses a tab-based workflow UI in `frontend/src/views/` and shared components in `frontend/src/components/`. Changes should fit the existing view/component boundaries and the app’s generated-workflow mental model.

## File and workflow heuristics

- When debugging or extending a feature, trace the path from `frontend/src/services/*.ts` → `backend/app/api/*.py` → `backend/app/services/*.py` → `backend/app/orchestrator/*`.
- For backend changes that affect session generation or validation, check the relevant route and the workspace/session guard before editing.
- For frontend changes, keep the view/component structure stable and prefer extending existing patterns in `frontend/src/views` and `frontend/src/context` before adding one-off architecture.
- The repo expects `.venv` for backend Python work; the startup script checks for `.venv/bin/python` and `.venv/bin/mlflow` before starting services.

## Project-specific notes

- `README.md` is the best source of product/architecture intent. It documents the Java 21 + Spring Boot 3.x generator intent, hermetic Docker verification, and the overall workflow.
- `TESTING_EXAMPLES.md` and the backend tests are the best references for concrete pytest patterns and single-test execution.
- The repo includes optional MLflow tracing and telemetry. It is best-effort and should not block local startup if the tracking service is absent.

## External Copilot gateway setup

`setup_copilot.py` is a local setup utility for registering the TCS GenAI Lab gateway as VS Code's official Custom Endpoint BYOK provider. It writes the user-level `chatLanguageModels.json` configuration and enables BYOK models for Agent Host sessions; it is not part of the application runtime.

The gateway must expose an OpenAI-compatible Chat Completions API. The gateway URL defaults to `https://genailab.tcs.in/v1/chat/completions` and can be overridden with `TCS_GATEWAY_URL`. The model ID defaults to `genailab-maas-gpt-5.3-codex` and can be overridden with `TCS_MODEL_ID`.

```bash
export TCS_GATEWAY_URL='https://genailab.tcs.in/v1/chat/completions'
export TCS_MODEL_ID='genailab-maas-gpt-5.3-codex'
python setup_copilot.py
```

After running the script, reload VS Code, run **Chat: Manage Language Models**, and select the TCS model in the chat model picker. VS Code prompts for the gateway key through its secure input/secret flow because `chatLanguageModels.json` contains `${input:tcsGatewayApiKey}`, not the credential itself. Enable `chat.agentHost.byokModels.enabled` if Agent mode does not list the model.

Do not put the key in `setup_copilot.py`, `.env`, generated JSON, or committed VS Code configuration. The script is machine-local and should be rerun after changing the gateway URL/model or after a VS Code configuration reset.

## Existing assistant config notes

No repo-local instruction files in the standard Claude/Cursor/Codex/Windsurf/Aider patterns were found at the root of this repository, so there was no project-specific convention file to merge. Keep changes consistent with the patterns above and with the README’s architectural principles.
