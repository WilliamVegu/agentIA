# AgentIA — Implementation Map

A navigable map of the codebase for a quick review: every agent, every feature,
and the components the design diagram shows, each mapped to its concrete files.
Current branch: `levantando_observaciones`.

---

## 1. The agents (the 8 LangGraph nodes)

Each generation node is a thin *node* (graph boundary) that delegates to a *stage*
implementation, selected once per session as `DETERMINISTIC` (template) or `MODEL`
(LLM). The stage boundary (`stages/runner.py`) owns mode dispatch, the compliance
gate, correction budgeting, and provenance.

| Node | Graph file | Deterministic stage | Model stage | Prompt |
|---|---|---|---|---|
| validator | `orchestrator/nodes/validator_node.py` | — (deterministic gate) | — | none |
| scaffolder | `orchestrator/nodes/scaffolder_node.py` | `stages/deterministic/scaffolder.py` | `stages/model/scaffolder.py` | `resources/instructions/scaffolder.md` |
| domain | `orchestrator/nodes/domain_node.py` | `stages/deterministic/domain.py` | `stages/model/domain.py` | `resources/instructions/domain.md` |
| service | `orchestrator/nodes/service_node.py` | `stages/deterministic/service.py` | `stages/model/service.py` | `resources/instructions/service.md` |
| controller | `orchestrator/nodes/controller_node.py` | `stages/deterministic/controller.py` | `stages/model/controller.py` | `resources/instructions/controller.md` |
| test | `orchestrator/nodes/test_node.py` | `stages/deterministic/test_synthesis.py` | `stages/model/test.py` | `resources/instructions/test.md` |
| sandbox | `orchestrator/nodes/sandbox_node.py` | — (Docker build) | — | none |
| repair | `orchestrator/nodes/repair_node.py` + `orchestrator/repair.py` | — (parser-driven) | — | none |

**Orchestrator plumbing**
- `orchestrator/graph.py` — the 8-node state machine + `_ModeInjectingGraph` entry wrapper.
- `orchestrator/state.py` — `GenerationAgentState` (all fields incl. `architecture_plan`, `llm_*`, `generation_mode`).
- `orchestrator/stages/runner.py` — the stage execution boundary (`run_stage`, `resolve_generation_mode`, `select_generation_mode`, artifact scopes, extraction).
- `orchestrator/stages/compliance.py` — verdict normalization + dependency-allowlist rule.
- `orchestrator/stages/instructions.py` — instruction-set loader (content-addressed revision).
- `orchestrator/stages/journal.py` — generation journal + provenance.
- `orchestrator/stages/deterministic/module_layout.py` — multi-module reactor layout (item 4).
- `orchestrator/repair.py` + `services/repair_parser.py` — Maven trace → failure class → surgical patch.

---

## 2. Features → implementation

| Feature | Spec | Implementation |
|---|---|---|
| 001 studio | `specs/001-…` | `services/spec_service.py`, `services/pipeline_runner.py`, `api/routes_spec.py`, `api/routes_session.py` |
| 002 requirements→stories | `specs/002-…` | `services/requirements_service.py`, `api/routes_requirements.py`, `models/requirements.py` |
| 003 architecture | `specs/003-…` | `services/architecture_service.py`, `api/routes_architecture.py`, `models/architecture.py` |
| 004 domain models + SQL | `specs/004-…` | `services/model_sql_service.py`, `api/routes_models_sql.py`, `models/domain_model.py` |
| 005 test analysis (Family A) | `specs/005-…` | `services/test_analysis_service.py`, `api/routes_tests.py` |
| 006 security audit (Family B) | `specs/006-…` | `services/security_service.py`, `api/routes_security.py`, `resources/cve_database.json` |
| 007 docker/CI | `specs/007-…` | `services/devops_service.py`, `services/docker_service.py`, `api/routes_devops.py` |
| 008 workflow orchestration | `specs/008-…` | `services/lifecycle_service.py`, `services/queue_service.py`, `api/routes_orchestrator.py` |
| 009 historical baseline | `specs/009-…` | `services/corpus_report.py`, `scripts/` (measurement) |
| 010 skill injection | `specs/010-…` | `resources/skills/*`, `skills/active.md` pointer (currently absent) |
| 011 LLM generation nodes | `specs/011-…` | `orchestrator/stages/*` (above), `resources/instructions/*` |
| 012 verifier honesty | `specs/012-…` | `sandbox/docker_runner.py`, `services/workspace_verification.py`, `services/platform_verification.py` |
| 013 cost tracing | `specs/013-…` | `cost/{recording,store,pricing,aggregate,mlflow_sink}.py`, `api/routes_llm.py` |
| 014 skillopt | `specs/014-…` | `scripts/skillopt/{collect,reflect,apply,gate,currency,round}.py`, `services/skill_contribution.py` |
| 015 diagnostic skill evolution | `specs/015-…` | `services/conformance_diagnostics.py`, `models/diagnostics.py` |
| **levantando_observaciones** (reframing) | `reports/agentia-reframing-plan.md` | `models/blueprint.py` (`inputInterface`), `models/architecture_plan.py`, `services/architecture_catalog.py`, `services/inference_engine.py`, `stages/deterministic/module_layout.py` |

---

## 3. Service components (the "big picture" boxes)

| Component | File | Role |
|---|---|---|
| Spec ingestion | `services/spec_service.py`, `api/routes_spec.py` | spec.md / JSON blueprint parse + validate + store |
| Requirements | `services/requirements_service.py` | narrative → stories/entities |
| Architecture | `services/architecture_service.py` | draft → 4-layer design + Mermaid + OpenAPI |
| Domain/SQL | `services/model_sql_service.py` | entities, DTOs, schema.sql, ER |
| Inference engine | `services/inference_engine.py` | spec interface → `ArchitecturePlan` |
| Architecture catalog | `services/architecture_catalog.py` | profiles + allowlist (data) |
| Compliance gate | `orchestrator/stages/compliance.py` | merged verdict + allowlist |
| Conformance diagnostics | `services/conformance_diagnostics.py` | rule-attributed scorer + `new_penalty` |
| Verification seam | `services/workspace_verification.py` | strip VCS, inject contract test, run build |
| Platform contract test | `services/platform_verification.py` | `@SpringBootTest` ddl=validate |
| Verification selection | `services/verification_selection.py` | best-of-k |
| Sandbox runner | `sandbox/docker_runner.py` | hermetic `mvn test -o`, surefire parse |
| LLM factory | `services/llm_factory.py` | provider detect + client build |
| Structured output | `services/structured_output.py` | JSON-schema fallback |
| Injection guard | `services/injection_guard.py` | heuristic prompt-injection scan |
| Injection judge | `services/injection_judge.py` | constrained LLM verdict |
| Cost recording | `cost/{recording,store,pricing,aggregate,mlflow_sink}.py` | per-call/session + MLflow mirror |
| Skill contribution | `services/skill_contribution.py` | leave-one-out |

---

## 4. API routes

| Route | Endpoints | Backing service |
|---|---|---|
| `routes_spec` | `POST /specifications`, `/upload` | `spec_service` |
| `routes_requirements` | `/requirements/transform`, `/refine` | `requirements_service` |
| `routes_architecture` | `/architecture/design`, `/refine` | `architecture_service` |
| `routes_models_sql` | `/models-sql/…` | `model_sql_service` |
| `routes_tests` | `/tests/…` | `test_analysis_service` |
| `routes_security` | `/security/…` | `security_service` |
| `routes_devops` | `/devops/…` | `devops_service`, `docker_service` |
| `routes_orchestrator` | `/orchestrator/…` | `lifecycle_service`, `pipeline_runner` |
| `routes_session` | `POST /sessions`, `/quick-start` | `pipeline_runner`, graph |
| `routes_llm` | `/llm/verify` | `llm_factory` |
| `routes_publish`, `routes_artifact` | export/git | `export_service`, `git_service` |

---

## 5. Frontend

| Tab | View | Backing service |
|---|---|---|
| 0 Resumen | `views/StudioOverviewView.tsx` | `sessionService` |
| 1 Requisitos | `views/RequirementsView.tsx` | `requirementsService` |
| 2 Arquitectura | `views/ArchitectureView.tsx` | `architectureService` |
| 3 Modelos & SQL | `views/DomainModelsView.tsx` | `modelsService` |
| 4 Blueprints (+ Interfaz) | `views/SpecIngestionView.tsx` | `specService` |
| 5 Monitor Live | `views/GenerationMonitorView.tsx` | `orchestratorService` (SSE) |
| 6 Código & Fix | `views/CodeExplorerView.tsx` | `sessionService` |
| 7 Calidad SAST | `views/SecurityQualityView.tsx` | `securityService` |
| 8 DevOps & Demo | `views/DevOpsDeploymentView.tsx` | `devopsService` |
| 9 Entrega Git | `views/ExportPublishView.tsx` | `exportService` |

Shared: `context/{Auth,Llm,Studio,Theme}Context.tsx`, `hooks/useSSE.ts`,
`components/common/{ResponsiveTabGrid,LifecycleStepper,MermaidViewer,TcsLogo}`,
`services/apiClient.ts`.

---

## 6. Data stores & resources

| Store / resource | Path | Role |
|---|---|---|
| System of record (cost) | `backend/cost_tracking.db` | authoritative cost/tokens |
| MLflow mirror | `mlflow.db` (SQLite) | cost mirror (drifted — see reports) |
| Session DB | `studio.db` (or config `DB`) | sessions, diagnostics |
| Instruction set | `resources/instructions/*.md` + `manifest.json` + `VERSION` | the 5 stage prompts |
| Skills | `resources/skills/*.md` | `layer_architecture.md` populated; 2 empty; `active.md` absent |
| Dependency allowlist | `resources/dependency_allowlist.json` | build boundary |
| Model pricing | `resources/model_pricing.json` | cost basis |
| CVE database | `resources/cve_database.json` | SAST secrets/CVE rules |

---

## 7. Quick-review pointers

- **Agent dispatch** starts at `orchestrator/stages/runner.py::run_stage`; mode is set
  once at `runner.py::select_generation_mode`.
- **The prompt assembly** (skill prefix → instruction → payload → output paths →
  response format) is in `runner.py` / the model stages' `build_request`.
- **Multi-module (item 4)** lives in `stages/deterministic/module_layout.py` +
  the `{prefix}` path prefixing in the 4 deterministic stages + `scaffolder.py`.
- **Inference (reframing)** is `services/inference_engine.py` (spec → plan) backed
  by `services/architecture_catalog.py` (profiles as data).
- **Verification** runs through `services/workspace_verification.py` →
  `services/platform_verification.py` (contract test) → `sandbox/docker_runner.py`.
- **Input guardrails** are `services/injection_guard.py` (heuristic) +
  `services/injection_judge.py` (constrained LLM judge), enforced in
  `api/routes_spec.py` and `api/routes_requirements.py`.
