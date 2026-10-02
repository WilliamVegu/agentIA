# AgentIA — State Map

**Date:** 2026-09-25
**Subject:** `github`-local checkout at `/home/gjanampa/Projects/AI_AGENTS/agentIA` @ HEAD `4518576`
**Scope:** Read-only reconnaissance. No source file was modified to produce this report.
**Companion:** [`reports/009-historical-baseline.md`](009-historical-baseline.md), [`docs/notes.tex`](docs/notes.tex) (SkillOpt proposal brief), [`specs/010-skill-injection/spec.md`](specs/010-skill-injection/spec.md)

---

## 0. Executive summary (read this before the detail)

Five findings dominate everything else in this document. They change what "inject a skill into the generation prompt" can even mean here.

1. **No LangGraph node calls an LLM.** All five "generation nodes" (`scaffolder`, `domain`, `service`, `controller`, `test`) emit Java source from hardcoded Python f-strings. There is no prompt to prepend skill text to. The graph performs **0 LLM invocations per session**.
2. **The primary product path bypasses the graph.** `pipeline_runner._execute_pipeline_steps` calls the node *functions* directly and never invokes `validator_node`, `sandbox_node`, or `repair_node`. So "Auto-Pilot" runs no sandbox build and no repair loop.
3. **The Docker verifier silently self-neutralises.** When Docker is absent, the image is missing, or the offline Maven cache is cold, `run_docker_sandbox` returns a canned `exit_code=0` / `BUILD SUCCESS` result. `build_success` is therefore almost always `True`, and the repair loop is dead code in practice.
4. **The persisted state is minimal and partly fake.** `studio.db` has exactly one table, `generation_sessions`. Its 50 rows are seeded fixtures, not telemetry — so the entire empirical basis of `reports/009-historical-baseline.md` is synthetic.
5. **The skill-injection feature is scaffolded but empty.** Committed in HEAD: three 0-byte skill documents, a 0-byte validator script, a 0-byte test file, and four 0-byte spec deliverables. Commit `4518576`'s message claims deliverables that do not exist.

---

## 1. ARCHITECTURE MAP

### 1.1 Where the LangGraph state machine is defined

**File:** [`backend/app/orchestrator/graph.py`](backend/app/orchestrator/graph.py) — 71 lines, the entire machine.

| Element | Location |
|---|---|
| Imports of the 8 node callables | `graph.py:3-10` |
| `_route_after_validator` | `graph.py:12-15` |
| `_route_after_sandbox` | `graph.py:17-22` |
| `_route_after_repair` | `graph.py:24-27` |
| `create_generation_graph()` factory | `graph.py:29-67` |
| `StateGraph(GenerationAgentState)` construction | `graph.py:34` |
| Node registration (8 × `add_node`) | `graph.py:37-44` |
| Edge wiring | `graph.py:47-65` |
| `workflow.compile()` | `graph.py:67` |
| Module-level compiled singleton `generation_graph` | `graph.py:70` |

**Nodes registered** (`graph.py:37-44`), in registration order:

| # | Node name | Callable | Definition |
|---|---|---|---|
| 1 | `validator` | `validator_node` | [`backend/app/orchestrator/nodes/validator_node.py:5`](backend/app/orchestrator/nodes/validator_node.py) |
| 2 | `scaffolder` | `scaffolder_node` | [`backend/app/orchestrator/nodes/scaffolder_node.py:11`](backend/app/orchestrator/nodes/scaffolder_node.py) |
| 3 | `domain` | `domain_node` | [`backend/app/orchestrator/nodes/domain_node.py:25`](backend/app/orchestrator/nodes/domain_node.py) |
| 4 | `service` | `service_node` | [`backend/app/orchestrator/nodes/service_node.py:5`](backend/app/orchestrator/nodes/service_node.py) |
| 5 | `controller` | `controller_node` | [`backend/app/orchestrator/nodes/controller_node.py:5`](backend/app/orchestrator/nodes/controller_node.py) |
| 6 | `test` | `test_node` | [`backend/app/orchestrator/nodes/test_node.py:12`](backend/app/orchestrator/nodes/test_node.py) |
| 7 | `sandbox` | `sandbox_node` | [`backend/app/orchestrator/nodes/sandbox_node.py:9`](backend/app/orchestrator/nodes/sandbox_node.py) |
| 8 | `repair` | `repair_node` | [`backend/app/orchestrator/nodes/repair_node.py:28`](backend/app/orchestrator/nodes/repair_node.py) |

### 1.2 Exact node sequence

Linear spine plus one bounded cycle (`graph.py:47-65`):

```
START
  └─> validator                      (graph.py:47)
        ├─ status == "FAILED" ─────────────────────────────> END   (graph.py:13-14)
        └─> scaffolder               (graph.py:48-51)
              └─> domain             (graph.py:52)
                    └─> service      (graph.py:53)
                          └─> controller  (graph.py:54)
                                └─> test      (graph.py:55)
                                      └─> sandbox   (graph.py:56)
                                            ├─ build_success ────> END   (graph.py:18-19)
                                            ├─ status == BLOCKED ─> END  (graph.py:20-21)  ← dead branch
                                            └─> repair        (graph.py:58-61)
                                                  ├─ status == BLOCKED ─> END  (graph.py:25-26)
                                                  └─> sandbox   (graph.py:62-65)  ← cycle back
```

Concretely: `validator → scaffolder → domain → service → controller → test → sandbox → [repair → sandbox]* → END`.

Note the `status == "BLOCKED"` guard in `_route_after_sandbox` (`graph.py:20-21`) is unreachable: `sandbox_node` never writes `status = "BLOCKED"` (it writes `COMPLETED` at `sandbox_node.py:42` on success and nothing at all on failure — see `sandbox_node.py:57-63`). The only exit from the cycle is `build_success == True` or `repair_node` returning `BLOCKED`.

### 1.3 Where a new node would be inserted before `validator_node`

Three edits in `graph.py`, plus two outside it:

| Step | File:line | Change |
|---|---|---|
| 1 | `graph.py:3-10` | Add `from app.orchestrator.nodes.<new>_node import <new>_node` alongside the existing node imports |
| 2 | `graph.py:37` | Add `workflow.add_node("skill_injection", skill_injection_node)` — immediately before or after the `"validator"` registration |
| 3 | **`graph.py:47`** | **This is the single insertion line.** Replace `workflow.add_edge(START, "validator")` with `workflow.add_edge(START, "skill_injection")` + `workflow.add_edge("skill_injection", "validator")` |
| 4 | `backend/app/orchestrator/state.py:3-16` | Declare any new state fields the node writes (e.g. `skill_ids`, `skill_versions`, `injection_point`) |
| 5 | `backend/app/api/routes_session.py:95-105` | Seed those fields in `initial_state`; otherwise `total=False` silently tolerates their absence but downstream reads get `None` |

Secondary insertion points if the node must also run on the Auto-Pilot path: `backend/app/services/pipeline_runner.py:357-368` (the `agent_state` dict and the five direct node calls).

### 1.4 `GenerationAgentState` definition

**File:** [`backend/app/orchestrator/state.py:3-16`](backend/app/orchestrator/state.py) — a `TypedDict` with `total=False`, 12 declared fields:

| Field | Type | Written by |
|---|---|---|
| `session_id` | `str` | `routes_session.py:96` |
| `blueprint` | `Dict[str, Any]` | `routes_session.py:97` |
| `workspace_path` | `str` | `routes_session.py:98` |
| `current_phase` | `str` | `validator_node.py:18,26`; `scaffolder_node.py:139`; `test_node.py:176`; `sandbox_node.py:41,58`; `repair_node.py:74,105` |
| `generated_files` | `Dict[str, str]` (relative path → content) | all 5 generation nodes; `repair_node.py:107` |
| `repair_attempts` | `int` | `repair_node.py:72,104` |
| `max_repair_attempts` | `int` | `routes_session.py:102` |
| `last_diagnostic` | `Optional[Dict[str, Any]]` | `sandbox_node.py:60` |
| `build_success` | `bool` | `sandbox_node.py:43,59` |
| `test_metrics` | `Optional[Dict[str, Any]]` | `sandbox_node.py:44,61` |
| `logs` | `List[str]` | every node (append-only) |
| `status` | `str` | `validator_node.py:19`; `sandbox_node.py:42`; `repair_node.py:73` |
| `error` | `Optional[str]` | `validator_node.py:20`; `repair_node.py:75` |

**Two type-integrity defects to note:**

- `repair_node.py:76` and `:106` write a key **`diff_summary` that is not declared** in `GenerationAgentState`. Because `total=False`, mypy/LangGraph do not reject it; it silently joins the accumulated state and is read by `routes_session.py:153`.
- `repair_node.py:69-70` stores a **Pydantic `FailureDiagnostic` object** into `BLOCKED_SESSIONS_STORE`, not a dict, while `sandbox_node.py:49` stores a plain `dict` into `last_diagnostic`. `repair_node.py:42-44` handles both shapes defensively — evidence of drift.

There is **no field for external guidance or skill content**. This is the schema change any injection feature requires.

### 1.5 Where the repair loop is implemented, and how `repair_node` re-enters `sandbox_node`

The loop is split across three places:

**(a) The graph edges** — `graph.py:58-65`. `add_conditional_edges("sandbox", _route_after_sandbox, {END: END, "repair": "repair"})` then `add_conditional_edges("repair", _route_after_repair, {END: END, "sandbox": "sandbox"})`. The routing functions are `_route_after_sandbox` (`graph.py:17-22`) and `_route_after_repair` (`graph.py:24-27`).

**(b) The loop body** — `repair_node` at `repair_node.py:28-109`:
1. `repair_attempts = state.get("repair_attempts", 0) + 1` (`:29`) — the counter lives in graph state, **not** in the database.
2. Reads `max_repair_attempts` (`:30`, default 5) and `last_diagnostic` (`:32`).
3. Normalises the diagnostic into a `FailureDiagnostic` (`:40-62`).
4. **Bound check** `:64`: `if not can_retry(repair_attempts - 1, max_attempts) or repair_attempts > max_attempts:` → returns `status = BLOCKED` (`:71-78`), which makes `_route_after_repair` return `END`.
5. Otherwise calls `test_analysis_service.execute_repair_iteration(...)` (`:81-86`) — **deterministic, no LLM**.
6. Appends the record to `REPAIR_HISTORIES_STORE[session_id]` (`:88-90`) — an **in-process dict**, lost on restart.
7. Applies each patch to the in-memory `generated_files` map and rewrites the file on disk (`:93-98`).
8. Returns `current_phase = SELF_REPAIR_LOOP` (`:105`).

**(c) The re-entry mechanism.** `repair_node` never imports or calls `sandbox_node`. Re-entry is purely a graph edge: `repair_node` returns a state dict, `_route_after_repair` (`graph.py:24-27`) inspects it, and because `status` is not `BLOCKED` it returns the literal string `"sandbox"`, which `add_conditional_edges` (`graph.py:62-65`) resolves to the `sandbox` node. LangGraph then re-invokes `sandbox_node` with the accumulated state — including the patched `generated_files` already flushed to disk by `repair_node.py:95-98`.

**Bound arithmetic.** With `max_attempts = 5`: sandbox runs once initially; then repair(1)→sandbox, repair(2)→sandbox, repair(3)→sandbox, repair(4)→sandbox, repair(5)→sandbox; the 6th visit to repair takes the `:64` branch and blocks. So `sandbox_node` executes **6 times** and `repair_node` **6 times** (5 productive + 1 blocking). This off-by-one is worth confirming against intent before adding a per-attempt injection hook.

**Supporting helpers:** [`backend/app/orchestrator/repair.py`](backend/app/orchestrator/repair.py) — `can_retry` (`:4-9`), `parse_maven_errors` (`:11-83`), `format_repair_prompt` (`:85-110`). A near-duplicate parser exists at `backend/app/services/repair_parser.py` (`parse_granular_diagnostics`, `can_retry` at `:21`).

---

## 2. LLM CALL SURFACE

### 2.1 How each generation node builds its "prompt" — there is no prompt

**There is no shared prompt-building helper.** A glob for `**/*prompt*` across the repository returns **no files**. There is no prompt module, no template registry, no prompt-assembly layer. Every prompt in the codebase is an inline Python string inside the function that uses it.

Critically: **the five generation nodes never call an LLM.** They construct Java source with f-strings and write it to disk. The mapping from blueprint → Java is total and deterministic.

| Node | Function | Template literals (the "would-be prompt" surface) | LLM? |
|---|---|---|---|
| `scaffolder` | `scaffolder_node` (`scaffolder_node.py:11`) | `pom_xml` `:24`; `app_yml` `:94`; `app_java` `:112`; disk writes `:130-134` | **No** |
| `domain` | `domain_node` (`domain_node.py:25`) | `entity_src` `:80`; `create_dto_src` `:122`; `resp_dto_src` `:145` | **No** |
| `service` | `service_node` (`service_node.py:5`) | `not_found_ex` `:17`; `repo_src` `:37`; `service_iface` `:51`; `service_impl` `:77` | **No** |
| `controller` | `controller_node` (`controller_node.py:5`) | `handler_src` `:18`; `home_src` `:102`; `ctrl_src` `:193` | **No** |
| `test` | `test_node` (`test_node.py:12`) | `app_test` `:26`; `test_src` `:76` | **No** |
| `validator` | `validator_node` (`validator_node.py:5`) | none | **No** |
| `sandbox` | `sandbox_node` (`sandbox_node.py:9`) | none | **No** |
| `repair` | `repair_node` (`repair_node.py:28`) | delegates to `test_analysis_service.execute_repair_iteration` (`:81`) | **No** |

The template inputs are only `blueprint` keys (`serviceName`, `packageName`, `entities[].name`, `entities[].attributes`, `userStories`) read at the top of each node — e.g. `scaffolder_node.py:12-17`, `domain_node.py:26-33`, `service_node.py:6-13`, `controller_node.py:6-14`, `test_node.py:13-21`.

Verification: a grep for `.invoke(` / `.ainvoke(` / `with_structured_output` across `backend/app` returns **9 hits**, none in `backend/app/orchestrator/`.

### 2.2 The real prompts (and their non-shared construction)

Only two services build genuine LLM prompts. Both inline a `system_prompt` and pair it with a `HumanMessage`; neither imports a helper.

| Prompt | File:line | Invocation |
|---|---|---|
| Requirements decomposition — system prompt | `backend/app/services/requirements_service.py:243-259` | `structured_llm.invoke(messages)` @ `:272` |
| Requirements decomposition — user content | `requirements_service.py:261-265` | messages assembled `:267-270` |
| Requirements refinement — system prompt | `requirements_service.py:428-434` | `structured_llm.invoke(messages)` @ `:449` |
| Requirements refinement — user content | `requirements_service.py:436-442` | messages assembled `:444-447` |
| Architecture design — system prompt | `backend/app/services/architecture_service.py:432-444` | `structured_llm.invoke(messages)` @ `:458` |
| Architecture design — user content | `architecture_service.py:446-451` | messages assembled `:453-456` |
| Architecture refinement — system prompt | `architecture_service.py:572-585` | `structured_llm.invoke(messages)` @ `:586` |
| LLM connectivity ping | `backend/app/api/routes_llm.py:67-69` | `chat_model.invoke([HumanMessage(...)])` @ `:69` |

**One prompt is constructed and never called.** `backend/app/orchestrator/repair.py:85-110` defines `format_repair_prompt(diag, context=None)`, which returns a complete instruction block ending with four hardcoded constitution rules (`:104-109`: "Java 21 LTS syntax…", "Spring Boot 3.x patterns (Jakarta EE, not javax)…", "Layered architecture separation…", "Record DTOs and Mockito unit tests…"). It is **the closest existing analogue to skill injection** and it is wired to nothing: `repair_node.py:5` imports it, and `repair_node.py:100` uses it only as a fallback string for a `diff_summary` field. Its `context: Optional[str] = None` parameter (`:85`) and its `context or 'No additional context'` default (`:102`) constitute an **unused external-guidance seam**.

**One LLM object is constructed and deliberately discarded.** `backend/app/services/model_sql_service.py:498-511`: after the mock check, it calls `LLMFactory.get_chat_model(...)` at `:502` and then, unconditionally, `return _mock_domain_model_response(draft)` at `:509`. The LLM is never invoked; the deterministic generator is always the answer.

### 2.3 How many LLM calls happen per session

It depends entirely on which of two disjoint entry paths created the session.

| Path | Entry point | LLM invocations per session |
|---|---|---|
| **A — LangGraph generation** | `POST /api/v1/sessions` → `routes_session.create_generation_session` (`routes_session.py:326`) → `execute_generation_pipeline` (`:68`) → `generation_graph.stream` (`:112`) | **0** |
| **B — Auto-Pilot pipeline** | `POST /api/v1/sessions/quick-start` with `autoRun=true` (`routes_session.py:308-311`) or `POST /api/v1/orchestrator/pipeline/run` (`routes_orchestrator.py:110`) → `pipeline_runner.run_pipeline` → `_execute_pipeline_steps` | **0 or 2** |
| **C — Interactive refinement** | `POST /requirements/refine` → `requirements_service.py:449`; architecture refine → `architecture_service.py:586` | **+1 each, user-triggered** |
| **D — Credential check** | `POST /api/v1/llm/verify` → `routes_llm.py:69` | **1 ping** |

For Path B, the two possible calls are:
- `_get_or_create_draft` → `transform_requirements` (`pipeline_runner.py:180-189` → `requirements_service.py:272`) — **only if `api_key` is set and not mock** (`pipeline_runner.py:180`).
- `design_architecture` (`pipeline_runner.py:304-305` → `architecture_service.py:458`).

Path B step 4 (`model_sql_service.synthesize_domain_models_and_sql`, `pipeline_runner.py:329`) constructs a chat model but invokes nothing (see §2.2). Steps 5–7 (`pipeline_runner.py:342-404`) are fully deterministic.

**Practical headline: a fully greenfield Session that a user launches from the UI costs 0 LLM calls if it goes through `POST /sessions`, and at most 2 if it goes through Auto-Pilot with a live API key.** Compare `docs/notes.tex:50-61`, which frames AgentIA as a platform whose failures come from a model that "knows a rule but forgets to apply it in a given session" — that framing presumes a model is in the loop during generation.

### 2.4 `LLMFactory` — location and provider routing

**File:** [`backend/app/services/llm_factory.py`](backend/app/services/llm_factory.py) — class `LLMFactory` at `:62`.

**Providers** (`LLMProvider` enum, `:6-10`): `GEMINI`, `GROQ`, `OPENAI`, `MOCK`.

| Concern | Method | Lines |
|---|---|---|
| Provider detection (explicit arg → key prefix → env fallback) | `detect_provider` | `:70-118` |
| Mock-mode predicate | `is_mock` | `:121-123` |
| Deprecated→active model remap | `resolve_model_name` | `:126-141` |
| Supported-model listing | `get_supported_models` | `:144-146` |
| **Model instantiation** | `get_chat_model` | `:149-207` |

Routing rules (`:105-118`): `AIza*` or `AQ.*` → Gemini; `gsk_*` → Groq; `sk-*` (not `gsk_`) → OpenAI; any key containing `mock`, `mock-*`, or `offline-*`, or the string `mock` as an explicit provider → `MOCK`; no key at all → `MOCK` (`:82-83`). `get_chat_model` returns **`None`** for mock mode (`:162-163`) rather than a fake model — every caller must null-check (e.g. `requirements_service.py:238`, `architecture_service.py:427`).

Per-provider client construction: Gemini `:168-177` (`langchain_google_genai.ChatGoogleGenerativeAI`), Groq `:179-191` (`langchain_groq.ChatGroq`), OpenAI `:193-205` (`langchain_openai.ChatOpenAI`). All use `temperature` default `0.2`, `max_retries=2`, 120 s timeout. Unsupported provider raises `ValueError` at `:207`.

**Model inventories:** `DEFAULT_MODELS` `:13-17`; `SUPPORTED_MODELS` `:20-39`; `DEPRECATED_MODEL_FALLBACKS` `:42-60`. Note the declared defaults target versions that do not exist in the public Gemini/Groq catalogues (`gemini-3.6-flash`, `qwen/qwen3.8-27b`) — consistent with the fabricated-date framing throughout this repo (`docs/notes.tex:290-295` cites 2026 arXiv IDs).

---

## 3. VERIFIER SURFACE

### 3.1 Where `sandbox_node` invokes Docker and `mvn test -o`

`sandbox_node` (`sandbox_node.py:9-63`) does not build a Docker command itself. It bridges sync→async and delegates:

- Async-loop detection and execution: `sandbox_node.py:18-29` (threadpool `:26-27`, direct loop `:29`).
- The call: **`run_docker_sandbox(workspace_path, log_callback=log_cb)`** at `sandbox_node.py:27` and `:29`.
- Log lines streamed back through `log_cb` (`:14-15`) into `state["logs"]`.

The actual Docker invocation lives in [`backend/app/sandbox/docker_runner.py`](backend/app/sandbox/docker_runner.py):

| Step | Location |
|---|---|
| **Command construction** | `build_docker_cmd`, `docker_runner.py:20-44` |
| Docker daemon pre-check | `docker_runner.py:87-92` (via `app.services.docker_service.check_docker_daemon`) |
| Early hermetic fallback if daemon down | `docker_runner.py:94-95` |
| **Process spawn** | `asyncio.create_subprocess_exec(*cmd, ...)`, `docker_runner.py:105-109` |
| Line-by-line stdout/stderr streaming | `docker_runner.py:111-119` |
| 300 s timeout guard | `docker_runner.py:121-128`, `:135-145` |

The command (`docker_runner.py:36-44`):

```python
["docker", "run", "--rm",
 "--network", "none",
 "-v", f"{ws_path}:/workspace",
 "-v", f"{m2_path}:/root/.m2/repository:ro",
 "-w", "/workspace",
 docker_image,
 "mvn", "test", "-o"]
```

This **matches** the documented hermetic contract (`README.md:26`, `README.md:39`, `.specify/memory/constitution.md` Principle IV): `--network none`, read-only `.m2` cache mount, offline `mvn test -o`, image default `maven:3.9-eclipse-temurin-21` (`config.py:47`, `docker_runner.py:23`).

**However — verified failure modes that make it a no-op:**

- `docker_runner.py:46-71`: `_build_hermetic_fallback_result` returns a **canned success** — `exit_code=0` and the literal `OFFLINE_SANDBOX_STDOUT` claiming `Tests run: 5, Failures: 0, Errors: 0` and `BUILD SUCCESS`.
- It is returned when the daemon is unavailable (`:94-95`), when the `docker` binary is missing (`FileNotFoundError`, `:132-134`), on generic connection errors (`:146-149`), and — most insidiously — on any non-zero exit whose combined output matches `ENVIRONMENT_FALLBACK_PATTERNS` (`:162-188`), a 20-pattern list that includes entirely legitimate build failures such as `"non-resolvable parent pom"`, `"could not resolve dependencies"`, and `"unresolvablemodelexception"`.
- `docker_service.check_docker_daemon`-style exceptions are swallowed at `:91-92` and treated as "daemon down".

Consequence: `sandbox_node`'s `result.is_success` (`:31`) is `True` under all those conditions, so it returns `build_success=True` / `status=COMPLETED` (`:40-46`), `_route_after_sandbox` (`graph.py:18-19`) routes to `END`, and the repair loop never executes. The offline-fallback path is the expected state in CI and in any environment without a warm `~/.m2` and a pre-pulled image.

**Second defect — fabricated metrics.** `sandbox_node.py:33-39` hardcodes `totalTests=5, passedTests=5, failedTests=0`; the failure branch `:50-56` hardcodes `totalTests=5, passedTests=4, failedTests=1`. These numbers are never parsed from Maven's report. They are what `routes_session.py:185-188` broadcasts to the UI, and they are the numeric foundation of the "100% test pass rate" claims in `README.md:39`. `reports/009-historical-baseline.md:35` counts `VERIFIED` sessions as "passed 100% tests & quality gates" on this basis.

**Diagnostic parsing** (only reached if the fallback does not fire): `parse_maven_errors(result.stdout + "\n" + result.stderr)` at `sandbox_node.py:49`, implemented at `repair.py:11-83` — compilation-error regex `:16-42`, Surefire failure regex `:45-74`, generic fallback `:77-83`.

**Unused cache module:** [`backend/app/sandbox/verify_cache.py`](backend/app/sandbox/verify_cache.py) (63 lines) exists but nothing in `backend/app` imports it.

### 3.2 Where the constitutional validators are implemented

The constitution itself: [`.specify/memory/constitution.md`](.specify/memory/constitution.md) — six principles, headings at `:18`, `:28`, `:37`, `:46`, `:54`, `:63`.

There are **four distinct validator implementations**, in two families, with two incompatible return types.

**Family A — orchestrator blueprint validator** (not constitutional despite the name):

- `validator_node`, `validator_node.py:5-28`. Checks only that `blueprint["entities"]` is non-empty (`:16-22`). Returns a node-output dict with `current_phase`, `status`, `error`, `logs` (`:17-22` and `:25-28`). Enforces **no** constitution principle.
- `backend/app/services/spec_service.py:152` — `"Validates structural and constitutional integrity of blueprint."` (string only; not a CLI/API entry point).

**Family B — static code validators** (the real constitutional enforcement):

**(B1) `TestAnalysisService.analyze_code_compliance`** — `backend/app/services/test_analysis_service.py:50-110`.

- Signature: `-> Tuple[bool, List[FailureDiagnostic]]` (`:50`).
- Return statement: `return is_compliant, diagnostics` (`:110`).
- Checks: Principle I — controller importing/injecting a Repository (`:63-76`); Principle II — request/response DTO declared as `class` instead of `record` (`:78-93`); Lombok `@Data` prohibition (`:95-107`).
- Note it emits `DiagnosticCategory.CONSTITUTIONAL_VIOLATION` (`:69`, `:86`, `:100`) with severities `BLOCKING` / `HIGH` / `MEDIUM`.

**(B2) `security_service.scan_architecture_compliance`** — `backend/app/services/security_service.py:318-418`.

- Signature: `-> List[StandardsComplianceViolation]` (`:318`).
- Return: `return violations` (`:418`).
- Checks: Principle I — controller imports `.repository.` or `Repository;` (`:331-347`); Principle III — ad-hoc try/catch with `ResponseEntity.status(`/`HttpStatus.` in a controller (`:349-363`); Principle II — DTO `public class` without `public record` (`:365-382`); Lombok stack restriction for `@Data`, `@Value`, `@SneakyThrows` (`:384-399`); Principle III global — missing `@RestControllerAdvice` anywhere in the file set (`:401-416`).

**(B3) `security_service.evaluate_quality_gate`** — `security_service.py:517-564`.

- Signature: `(vulnerabilities, violations, metrics) -> QualityGateVerdict` (`:517-521`).
- Return object: `QualityGateVerdict(status=..., score=..., criticalCount=..., highCount=..., mediumCount=..., lowCount=..., canExport=..., summaryMessage=...)` (`:555-564`).
- Scoring: `penalty = critical*30 + high*15 + medium*5 + low*2`, plus `min(methodsExceedingThreshold * 3, 15)`; `score = max(0, 100 - penalty)` (`:537-540`).
- Gate: any `CRITICAL` or `HIGH` → `BLOCKED` and `canExport=False` (`:542-545`); any `MEDIUM`/`LOW`/complexity excess → `WARNING` (`:546-549`); else `PASS` (`:550-553`).

**Supporting implementations in the same file:** SAST scanner (`security_service.py:~140-250`), secret-leak detector (`:39-135`, offline entropy rules), offline CVE/SCA loader (`:22-36`, `:258-312`, backed by `backend/app/resources/cve_database.json`), `calculate_code_metrics` (`:424-511`), `apply_surgical_remediation` (`:570-619`, with the unified diff at `:611-618`).

**Orchestration of B2/B3 in the pipeline:** `audit_workspace` (`security_service.py`, entry used at `pipeline_runner.py:376`) yields a `SecurityQualityAuditReport`; `pipeline_runner.py:377-388` blocks the run when `audit.qualityGate.status == "BLOCKED"`.

### 3.3 What the validators return

| Validator | Return type | Boolean? | Score? | Violation list? |
|---|---|---|---|---|
| `validator_node` | node-output `Dict[str, Any]` | indirectly (`status == "FAILED"`) | no | no — single `error` string |
| `analyze_code_compliance` (`test_analysis_service.py:50`) | `Tuple[bool, List[FailureDiagnostic]]` | **yes** (`is_compliant`) | no | **yes** (`FailureDiagnostic` with `category`, `severity`, `filePath`, `errorSummary`, `suggestedFix`, `rawStackTrace`) |
| `scan_architecture_compliance` (`security_service.py:318`) | `List[StandardsComplianceViolation]` | no (empty list ⇒ compliant) | no | **yes** (`id`, `principle`, `severity`, `filePath`, `offendingElement`, `ruleDescription`, `suggestedFix`, `autoFixAvailable`) |
| `evaluate_quality_gate` (`security_service.py:517`) | `QualityGateVerdict` | **yes** (`canExport`) | **yes** (`score` 0–100) | counts only (`criticalCount`…`lowCount`) |

Type definitions: `StandardsComplianceViolation` — `backend/app/models/security_quality.py:54-62`; `QualityGateVerdict` — `:76-84`; `ConstitutionPrinciple` enum — `:29-36` (7 members, including `STACK_LOMBOK_RESTRICTION`); `FailureDiagnostic` — `backend/app/models/test_analysis.py:54-67`; `DiagnosticCategory` — `:11-15`.

**Design smell worth flagging:** families B1 and B2 independently re-implement the *same* constitutional rules (Principle I, Principle II, Lombok) with different signatures, different finding models, different severities for the same violation, and different import-detection regexes (`test_analysis_service.py:65` uses `import\s+.*\.repository\..*Repository;`; `security_service.py:334` uses a substring test). Any new validator must be added twice to be consistent, or these two must be unified first.

---

## 4. PERSISTENCE

### 4.1 Full schema of `studio.db`

**Location:** `backend/studio.db` (28,672 bytes). Configured at `backend/app/config.py:65-69`:

```python
DATABASE_URL: str = Field(
    default_factory=lambda: f"sqlite:///{(Path(__file__).resolve().parent.parent / 'studio.db').as_posix()}",
    description="Database connection URL (PostgreSQL in production or SQLite for local development)")
```

Engine and session factory: `backend/app/models/session.py:13-14`.

**There is exactly one table.** Verified directly against the file:

```
TABLES: ['generation_sessions']
```

**On-disk DDL (verbatim):**

```sql
CREATE TABLE generation_sessions (
    id VARCHAR(36) PRIMARY KEY,
    spec_id VARCHAR(36),
    spec_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    phase VARCHAR(30) NOT NULL,
    queue_position INTEGER DEFAULT 0,
    repair_attempts INTEGER DEFAULT 0,
    current_lifecycle_phase VARCHAR(50) DEFAULT 'INITIAL',
    lifecycle_mode VARCHAR(50) DEFAULT 'GUIDED_STEP',
    phase_progress_json TEXT,
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
)
```

**Indexes:** only `sqlite_autoindex_generation_sessions_1` (implicit, from `PRIMARY KEY`). **No explicit indexes, no views, no triggers, no foreign keys, no unique constraints beyond the PK.**

**Column semantics and where each is written:**

| Column | ORM declaration | Written at |
|---|---|---|
| `id` VARCHAR(36) PK | `session.py:39` (`uuid4` default) | on insert |
| `spec_id` VARCHAR(36) | `session.py:40` (`nullable=False`) | `routes_session.py:294`, `:340`; `routes_orchestrator.py:92` |
| `spec_name` VARCHAR(100) NOT NULL | `session.py:41` | same inserts |
| `status` VARCHAR(20) NOT NULL | `session.py:42` — `SQLEnum(SessionStatus)` | `routes_session.py:78,177,195,212,247,296,342,414`; `pipeline_runner.py:104,119,152,426,453,500` |
| `phase` VARCHAR(30) NOT NULL | `session.py:43` — `SQLEnum(SessionPhase)` | `routes_session.py:79,178,196,248,297,343`; `pipeline_runner.py:427` |
| `queue_position` INTEGER DEFAULT 0 | `session.py:44` | `routes_session.py:81`; `queue_service` |
| `repair_attempts` INTEGER DEFAULT 0 | `session.py:45` | **insert only** — see §4.3 |
| `current_lifecycle_phase` VARCHAR(50) | `session.py:46` | `routes_session.py:249,298`; `pipeline_runner.py:428`; `lifecycle_service` |
| `lifecycle_mode` VARCHAR(50) | `session.py:47` | `routes_session.py:299`; `pipeline_runner.py:105,120,499` |
| `phase_progress_json` TEXT | `session.py:48` | `lifecycle_service.py:345,360,471,494` |
| `created_at` TIMESTAMP NOT NULL | `session.py:49` | ORM default |
| `started_at` TIMESTAMP | `session.py:50` | `routes_session.py:80`; `pipeline_runner.py:502` |
| `completed_at` TIMESTAMP | `session.py:51` | `routes_session.py:179,198`; `pipeline_runner.py:429` |
| `error_message` TEXT | `session.py:52` | `routes_session.py:197,213`; `pipeline_runner.py:454` |

**Schema-vs-ORM drift:** on disk `spec_id` is nullable, but the ORM declares `nullable=False` (`session.py:40`). The shipped `studio.db` was therefore produced by the fixture builder, not solely by `Base.metadata.create_all(bind=engine)` (`session.py:54`). The `Enum` columns are stored as plain `VARCHAR` with **no `CHECK` constraint**, so SQLAlchemy persists enum *names*, and nothing at the storage layer prevents an invalid status string.

**Runtime incremental migration:** `_ensure_sqlite_lifecycle_columns`, `session.py:56-73` — a hand-rolled `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` shim for the three lifecycle columns, wrapped in a bare `except Exception: pass` (`:70-71`). It is invoked at import time (`:73`). This is the only migration mechanism; there is no Alembic.

**No table exists for:** skills, skill versions, injections, artifacts, repair history, quality audits, or per-attempt diagnostics. Everything in that list lives in process memory or on the filesystem (`settings.WORKSPACE_DIR`).

### 4.2 Table contents — the data is synthetic

```
status distribution:  BLOCKED=20, COMPLETED=28, RUNNING=2        (total 50)
phase distribution:   VERIFIED=28, SELF_REPAIR_LOOP=16, FAILED=4, CODE_GENERATION=2
repair_attempts:      0→18, 1→12, 2→4, 3→16
```

Row names are `"Running Spec 1"`, `"Blocked Spec 16"`, `"Failed Spec 4"` — generated labels. Confirmed source: [`backend/scripts/seed_historical_baseline.py:28`](backend/scripts/seed_historical_baseline.py) calls `create_fixture_database(target_db, session_count=50)` from `backend/tests/fixtures/baseline_fixture_db.py` (195 lines), whose docstring at `:3` reads *"Seed script for populating studio.db with representative historical AgentIA generation sessions."*

**This matters for the skill pilot.** `reports/009-historical-baseline.md:13` reports "Total Sessions Queried: 50" and derives its entire five-domain triage (`:19-27`) and its constitutional-violation frequencies (`:74-85`) from this table. Those numbers are fixture constants, not observed outcomes. A related internal inconsistency: `reports/009-historical-baseline.md:35` presents `VERIFIED` as a *status*, but `SessionStatus` (`session.py:16-22`) has no `VERIFIED` member — it is a `SessionPhase` (`session.py:33`). Likewise `FAILED` appears in the DB `phase` column but is not a `SessionStatus` either.

### 4.3 Where `generation_sessions` is written and updated

**`backend/app/api/routes_session.py`** — the LangGraph path:

| Operation | Lines |
|---|---|
| **INSERT** (quick-start) — `status=QUEUED`, `phase=INITIALIZATION`, `current_lifecycle_phase="REQUIREMENTS"`, `lifecycle_mode=AUTO_PILOT|GUIDED_STEP`, `repair_attempts=0` | `:292-303` |
| **INSERT** (`POST /sessions`) — `status=QUEUED`, `phase=INITIALIZATION`, `repair_attempts=0` | `:338-347` |
| **UPDATE** → `RUNNING`, `phase=INITIALIZATION`, `started_at=now`, `queue_position=0` | `:76-82` |
| **UPDATE** → `COMPLETED`, `phase=VERIFIED`, `completed_at=now` | `:172-180` |
| **UPDATE** → `BLOCKED`, `phase=FAILED`, `error_message`, `completed_at` | `:194-199` |
| **UPDATE** → `BLOCKED`, `error_message` (exception handler) | `:209-214` |
| **UPDATE** side-effect inside a GET — `list_sessions` promotes status to `COMPLETED`/`VERIFIED`/`"COMPLETED"` when `completion_percentage >= 100` | `:247-250` |
| **UPDATE** → `CANCELLED` (`DELETE /sessions/{id}`) | `:411-415` |

**`backend/app/services/pipeline_runner.py`** — the Auto-Pilot path:

| Operation | Lines |
|---|---|
| Read `spec_name` | `:263-268` |
| **UPDATE** → `PAUSED` + `lifecycle_mode=GUIDED_STEP` | `:100-109` |
| **UPDATE** → `RUNNING` + `lifecycle_mode=AUTO_PILOT` | `:115-123` |
| **UPDATE** → `CANCELLED` | `:148-155` |
| **UPDATE** → `COMPLETED`, `phase=VERIFIED`, `current_lifecycle_phase="COMPLETED"`, `completed_at` | `:422-432` |
| **UPDATE** → `BLOCKED`, `error_message` | `:449-457` |
| **UPDATE** → `lifecycle_mode=AUTO_PILOT`, `status=RUNNING`, `started_at` (first run) | `:495-505` |

**`backend/app/api/routes_orchestrator.py`:** **INSERT** when `session_id == "new"` — `:88-103`; read-only existence check `:37-45`.

**`backend/app/services/lifecycle_service.py`:** owns `phase_progress_json` read/write at `:93-95`, `:338-345`, `:356-360`, `:462-471`, `:487-494`; also reads `repair_attempts` at `:172` (`if sess.repair_attempts >= 3`) — a **hardcoded 3** that contradicts `config.MAX_REPAIR_ATTEMPTS = 5`.

**Persistence gaps that matter for any injection feature:**

- **`repair_attempts` is never updated after insert.** No code path assigns `sess.repair_attempts = <n>`. The column is written only by the `default=0` at insert time (`session.py:45`) and by the fixture seed. `repair_node.py:72,104` returns the counter in graph state only.
- **`generated_files` is never persisted.** The full artifact map lives in `SESSION_GENERATION_STATE` (`routes_session.py:32`, populated at `:169`) — a plain module-level `Dict` — and on disk under `settings.WORKSPACE_DIR`. It is lost on process restart. `routes_artifact.py:96` and `routes_tests.py:229-230` read from it.
- **Repair history is in-memory.** `REPAIR_HISTORIES_STORE` and `BLOCKED_SESSIONS_STORE` are module-level dicts in `backend/app/api/routes_tests.py` (imported by `repair_node.py:16`).
- **`SESSION_EVENT_HISTORY` / `SESSION_EVENT_SUBSCRIBERS`** (`routes_session.py:30-31`) are likewise in-memory, so SSE replay (`:441-443`) is lost on restart.

---

## 5. INJECTION POINTS

### 5.0 The blocking fact, stated plainly

The prompt-injection model described in `docs/notes.tex:114` (*"At deployment, skills are prepended to the generation prompt"*) and in `specs/010-skill-injection/plan.md:16-18` (`layer_architecture` as "Task-level rules"; `mockito_tests` as "Event-driven rules" injected "when test failures are detected") **has no corresponding code path today.**

For each of `scaffolder`, `domain`, `service`, `controller`, `test`:

- there is **no prompt**;
- there is **no LLM client** in the module;
- the emitted Java is a compile-time-constant f-string whose only variables are blueprint field values.

Prepending skill text to these functions would require **first introducing an LLM call** — a design change well beyond injecting a string. The tables below therefore mark two kinds of anchor: the **literal template line** (where text would go if the function ever became prompt-driven) and the **function entry point** (where a `state["skills"]` read would be added).

### 5.1 `scaffolder` — [`backend/app/orchestrator/nodes/scaffolder_node.py`](backend/app/orchestrator/nodes/scaffolder_node.py)

**Function:** `scaffolder_node(state: GenerationAgentState) -> Dict[str, Any]`, `def` at **`:11`**.

| Anchor | Line | Role |
|---|---|---|
| Node entry — where a skill lookup would be read from `state` | **`:11-17`** | reads `blueprint`, `service_name`, `package_name`, `workspace_path`, `generated_files`, `logs` |
| Last derived variable before templating | `:21` (`pkg_path = package_name.replace(".", "/")`) | |
| **`pom_xml` f-string begins** | **`:24`** | Maven POM (Java 21, Spring Boot 3.2.3, H2, surefire) |
| `app_yml` f-string begins | `:94` | `application.yml` |
| `app_java` f-string begins | `:112` | `@SpringBootApplication` main class |
| Files written to disk | `:130-134` | |

> **Skill-prepend line: `scaffolder_node.py:24`** (immediately before the `pom_xml` template), with the state read at `:16` (`generated_files = state.get(...)`) as the natural place to also read `state.get("injected_skills")`. Relevant skill domain: `maven_pom` — but `specs/010-skill-injection/research.md:18` triages `maven_pom` to a **deterministic fixer, not a skill**, so this node is the wrong target for the surviving skill set.

### 5.2 `domain` — [`backend/app/orchestrator/nodes/domain_node.py`](backend/app/orchestrator/nodes/domain_node.py)

**Function:** `domain_node(state) -> Dict[str, Any]`, `def` at **`:25`**. Helper `_map_java_type` at `:5-23` (blueprint type → Java type).

| Anchor | Line | Role |
|---|---|---|
| Node entry — state reads | `:26-30` | `blueprint`, `package_name`, `workspace_path`, `generated_files`, `logs` |
| Per-entity loop begins | `:37` | iterates `blueprint["entities"]` |
| `logs.append("[DOMAIN] ...")` | `:35` | natural place to append an injection log line |
| **JPA `entity_src` f-string begins** | **`:80`** | `@Entity` + fields + getters/setters + `equals`/`hashCode` |
| **`create_dto_src` f-string begins** (Record, Principle II) | **`:122`** | `public record Create{Ent}Request(...)` |
| **`resp_dto_src` f-string begins** | **`:145`** | `public record {Ent}Response(...)` + `fromEntity` |
| Files written to disk | `:171-175` | |

> **Skill-prepend lines: `domain_node.py:80`, `:122`, `:145`.** Primary target for the `layer_architecture` skill (immutable Record DTOs, Principle II) — though note the node already emits `record` by construction (`:126`, `:149`), so a "DTOs must be Records" skill would be describing behaviour the generator already guarantees.

### 5.3 `service` — [`backend/app/orchestrator/nodes/service_node.py`](backend/app/orchestrator/nodes/service_node.py)

**Function:** `service_node(state) -> Dict[str, Any]`, `def` at **`:5`**.

| Anchor | Line | Role |
|---|---|---|
| Node entry — state reads | `:6-10` | `blueprint`, `package_name`, `workspace_path`, `generated_files`, `logs` |
| `base_dir` resolved | `:14` | |
| **`not_found_ex` f-string begins** | **`:17`** | `ResourceNotFoundException extends RuntimeException` |
| Per-entity loop begins | `:31` | |
| **`repo_src` f-string begins** | **`:37`** | `interface {Ent}Repository extends JpaRepository<{Ent}, Long>` |
| **`service_iface` f-string begins** | **`:51`** | `interface {Ent}Service` with `create`/`findById`/`findAll`/`delete` |
| Setter mapping built | `:69-75` | DTO → entity setters |
| **`service_impl` f-string begins** | **`:77`** | `@Service @Transactional class {Ent}ServiceImpl` |
| Files written to disk | `:138-141` | |

> **Skill-prepend lines: `service_node.py:17`, `:37`, `:51`, `:77`.** Primary target for the `layer_architecture` skill — this is the node that enforces controller→service→repository separation, and the only node that constructs the layer boundary the skill describes.

### 5.4 `controller` — [`backend/app/orchestrator/nodes/controller_node.py`](backend/app/orchestrator/nodes/controller_node.py)

**Function:** `controller_node(state) -> Dict[str, Any]`, `def` at **`:5`**.

| Anchor | Line | Role |
|---|---|---|
| Node entry — state reads | `:6-11` | `blueprint`, `service_name`, `package_name`, `workspace_path`, `generated_files`, `logs` |
| **`handler_src` f-string begins** (`@RestControllerAdvice`, Principle III) | **`:18`** | `GlobalExceptionHandler` with 4 `@ExceptionHandler` methods |
| `handler` written | `:83-85` | |
| Endpoint index built from entities | `:88-100` | |
| **`home_src` f-string begins** (`@GetMapping("/")` HTML+JSON catalog) | **`:102`** | embeds an inline HTML/CSS dashboard |
| `home` written | `:182-185` | |
| Per-entity loop begins | `:189` | |
| **`ctrl_src` f-string begins** | **`:193`** | `@RestController @RequestMapping("/api/v1/{plural}")` with POST/GET/GET-by-id/DELETE |
| `ctrl` written | `:241-245` | |

> **Skill-prepend lines: `controller_node.py:18`, `:102`, `:193`.** Primary target for the `exception_handling` skill (`@RestControllerAdvice`, Principle III) — again noting the node already emits `@RestControllerAdvice` at `:34-35` unconditionally.

### 5.5 `test` — [`backend/app/orchestrator/nodes/test_node.py`](backend/app/orchestrator/nodes/test_node.py)

**Function:** `test_node(state) -> Dict[str, Any]`, `def` at **`:12`**. Module guard `__test__ = False` at `:6` (prevents pytest collecting the node as a test).

| Anchor | Line | Role |
|---|---|---|
| Node entry — state reads | `:13-18` | `blueprint`, `package_name`, `service_name`, `workspace_path`, `generated_files`, `logs` |
| `base_dir` resolved | `:23` | |
| **`app_test` f-string begins** | **`:26`** | `{Pascal}ApplicationTests` with a trivial `assertTrue(true)` |
| Per-entity loop begins | `:46` | |
| Dummy-argument synthesis | `:51-74` | type-driven literals for the record constructor |
| **`test_src` f-string begins** (Mockito) | **`:76`** | `@ExtendWith(MockitoExtension.class)`, 5 test methods, `@Mock`/`@InjectMocks` |
| Test file written | `:167-171` | |
| Node sets `current_phase = TEST_SYNTHESIS` | `:176` | |

> **Skill-prepend lines: `test_node.py:26` and `:76`.** This is the only node whose target skill (`mockito_tests`, granularity `event-driven` per `research.md:25`) maps to a genuine generation concern. The 5 hardcoded test methods (`shouldCreate…`, `shouldFind…ByIdSuccessfully`, `shouldThrowExceptionWhen…NotFound`, `shouldFindAll…s`, `shouldDelete…Successfully`) are at `:115-164`; a stubbing-correctness skill would need to influence precisely this template.

### 5.6 The two injection points that *do* exist today

If the goal is to influence an LLM that is actually running, only these matter:

| Rank | Seam | File:line | Why it works |
|---|---|---|---|
| 1 | **`format_repair_prompt(diag, context=None)`** | `backend/app/orchestrator/repair.py:85`, usable text at `:102` | Purpose-built guidance-injection function with an **already-present, unused `context` parameter**. Currently uncalled (see §2.2). Wiring a skill string here requires only a caller. |
| 2 | **`transform_requirements` system prompt** | `backend/app/services/requirements_service.py:243-259` | A real LLM call (`:272`) with a long, rule-dense system prompt — the natural home for a `layer_architecture`-style specification skill. |
| 3 | **`design_architecture` system prompt** | `backend/app/services/architecture_service.py:432-444` | A real LLM call (`:458`); the prompt already enumerates the 4-layer topology rules that `layer_architecture.md` would restate. |
| 4 | **New `skill_injection_node` before `validator`** | insert at `graph.py:37` + `graph.py:47` | The design named in `docs/notes.tex:223`. Inert on its own — a node that injects into a state field nothing reads changes no behaviour. |

**Bottom line for §5:** of the five generation nodes named in the brief, **none has a prompt**, so the "exact line where skill content would need to be prepended" is a *future* LLM-call site, not an existing one. The only functional prepend targets in the current code are `repair.py:102` and the two real system prompts in `requirements_service.py:243` / `architecture_service.py:432`.

---

## 6. GAPS AND RISKS

### 6.1 What is unclear from the code alone

1. **Which execution path is the product.** Two disjoint paths exist — `POST /sessions` → `generation_graph.stream` (`routes_session.py:112`, all 8 nodes) and `/orchestrator/pipeline/run` + `quick-start autoRun` → `pipeline_runner._execute_pipeline_steps` (`pipeline_runner.py:240-464`, 5 nodes, no sandbox, no repair). Neither is marked canonical. `README.md:111` documents the quick-start card; `README.md:136` credits the LangGraph graph. Reconciling them is a prerequisite for any injection work, because a skill injected in the graph would be invisible on the Auto-Pilot path.
2. **Whether the repair loop has ever executed.** Given §3.1, `build_success` is `True` whenever Docker is unavailable or the `.m2` cache is cold. There is no counter, no metric, and no persisted flag distinguishing "verified by real Maven" from "hermetic fallback returned success". `repair_attempts` is never written (§4.3), so the DB cannot answer this either.
3. **The real repair cap.** `config.py:60` = 5; `.env.example:25` = 3; `.specify/memory/constitution.md:58-59` = 3; `README.md:27,40` = 3; `reports/009-historical-baseline.md:46` = 3; `repair.py:4` default = 5; `repair_node.py:30` default = 5; `models/test_analysis.py:79,126` `le=5`; `routes_tests.py:125` enforces `> 5`; `lifecycle_service.py:172` hardcodes `>= 3`. There is **no `.env` file in the repo**, so the effective value is **5**. `reports/009-historical-baseline.md:48-56`'s attempt histogram is only self-consistent under a 3-cap.
4. **What `status` values are legal.** `SessionStatus` (`session.py:16-22`) = QUEUED/RUNNING/PAUSED/COMPLETED/BLOCKED/CANCELLED. Yet `validator_node.py:19` and `_route_after_validator` (`graph.py:13`) use the literal string `"FAILED"`, and `sandbox_node.py:42` writes `SessionStatus.COMPLETED.value`. `reports/009-historical-baseline.md:35` reports `VERIFIED` as a status. The `status` column has no CHECK constraint, so all of this "works".
5. **Whether `model_sql_service`'s LLM call is a bug or a deliberate stub.** `model_sql_service.py:502` constructs a chat model and `:509` discards it. The comment at `:508` (`# Deterministic generator provides full compliant models; fallback or mock if LLM is None`) reads as intentional, but the dead construction remains.
6. **Whether `verify_cache.py` is dead.** `backend/app/sandbox/verify_cache.py` (63 lines) has no importer in `backend/app`.
7. **Why two Maven-diagnostic parsers exist.** `orchestrator/repair.py:11-83` and `services/repair_parser.py` (`parse_granular_diagnostics`) overlap substantially; only the former is used by `sandbox_node`.
8. **Provenance of `studio.db`.** 50 rows with generated labels, produced by `backend/scripts/seed_historical_baseline.py::main` (`:28`). Whether a real production DB was ever captured is not answerable from the repository.

### 6.2 What needs modification that isn't obvious from the docs

| # | Needed change | Why the docs don't reveal it |
|---|---|---|
| 1 | **Introduce an LLM call into the generation nodes (or accept that skills cannot apply there)** | `docs/notes.tex:114` assumes prompts exist; every spec assumes injection is a string prepend. In reality the nodes are deterministic emitters (§2.1). This is the largest unbudgeted work item. |
| 2 | **Unify the two generation paths** | Docs describe one pipeline (`README.md:138`). Code has two with different node coverage (`pipeline_runner.py:364-368` vs `routes_session.py:112`). |
| 3 | **Persist `repair_attempts` and `generated_files`** | Not mentioned anywhere. Without `repair_attempts` being written, the pilot's "re-inject on every repair attempt" (`docs/notes.tex:227`) is unobservable in the DB; without `generated_files` persistence, an exported bundle can silently diverge from what a session generated. |
| 4 | **Add a `skills` table + an injection-log table** | `docs/notes.tex:223-226` names them (`skills`; log of `session_id`/`skill_ids`/`versions`/`injection_point`) but `specs/010-skill-injection/spec.md:104` (FR-011) explicitly forbids schema changes in that task, and no later spec defines them. The log requirement (the A/B pilot needs per-session condition assignment, `docs/notes.tex:260-263`) is easy to miss. |
| 5 | **Make the sandbox verifier honest, or record the fallback** | A skill pilot's primary metric is `mvn test -o` pass rate (`docs/notes.tex:231`). If the harness returns synthetic success, the metric is unmeasurable. `docker_runner.py:94-95,132-134,146-149,185-188` must at minimum surface a `fallback_used` flag into `VerificationMetrics`. |
| 6 | **Add a `diff_summary` field to `GenerationAgentState`** | Undeclared write at `repair_node.py:76,106`; only detectable by reading the TypedDict. |
| 7 | **Fix the `skill_injection_node` position semantics** | `docs/notes.tex:223` says "before `validator_node`". But `validator_node` only checks non-empty entities (`validator_node.py:16-22`) and is a *gate*, not a generation step. A skill node placed there is upstream of every generation node — good for `task-level` skills, useless for the `event-driven` `mockito_tests` skill (`research.md:25`), which needs to fire after a sandbox failure. Two insertion points are needed, not one. |
| 8 | **Deduplicate the constitutional validators** | §3.3. A skill asserting "controllers must not inject repositories" will be checked by two implementations with different regexes (`test_analysis_service.py:65` vs `security_service.py:334`) and can produce contradictory verdicts. |
| 9 | **Reconcile the `reports/009` triage with the generator's actual behaviour** | The report triages `jakarta_namespace` to a fixer, but `scaffolder_node.py:125-127` emits only `jakarta.*` by construction and `repair.py:106` already hardcodes "Jakarta EE, not javax". The failure mode the fixer addresses cannot be produced by this generator. Similarly, `layer_architecture` (skill) and `exception_handling` (skill) target code the nodes already emit correctly (`controller_node.py:34` always emits `@RestControllerAdvice`; `domain_node.py:126,149` always emit `record`). The surviving skill set may be aimed at failures the current generator cannot make. |
| 10 | **Resolve the fixer-ID scheme conflict** | `data-model.md:94` says `FIX-JAKARTA-NAMESPACE`/`FIX-POM-OFFLINE-DEPS`; `contracts/fixer-spec-contract.md:20` says `FIX-JAKARTA-001`/`FIX-POM-001`. |

### 6.3 Empty deliverables committed in HEAD (blockers for reusing prior work)

Commit `4518576` ("feat(skill-injection): Finalize skill domain set and author seed skill documents") committed these as **0-byte blobs** — verified via working-tree size and `git log` (all attributed to that commit, working tree clean):

| Path | Size | Spec reference |
|---|---|---|
| `backend/app/resources/skills/layer_architecture.md` | 0 B | FR-003, `spec.md:96` |
| `backend/app/resources/skills/exception_handling.md` | 0 B | FR-003, `spec.md:96` |
| `backend/app/resources/skills/mockito_tests.md` | 0 B | FR-003, `spec.md:96` |
| `backend/scripts/validate_seed_skills.py` | 0 B | `plan.md:21`, `:104` |
| `backend/tests/test_seed_skills.py` | 0 B | `plan.md:21`, `:106` |
| `specs/010-skill-injection/domains.md` | 0 B | FR-001, `spec.md:94` |
| `specs/010-skill-injection/fixers.md` | 0 B | FR-009, `spec.md:102` |
| `specs/010-skill-injection/task1-summary.md` | 0 B | FR-010, `spec.md:103` |
| `specs/010-skill-injection/tasks.md` | 0 B | `plan.md:139` |
| `specs/009-historical-baseline-analysis/spec.md` | 0 B | — |

`__pycache__` artifacts exist for the two empty Python files (`backend/tests/__pycache__/test_seed_skills.cpython-312-pytest-9.1.1.pyc`, `backend/scripts/__pycache__/validate_seed_skills.cpython-312.pyc`), i.e. pytest has already imported the empty test module and collected zero tests. `plan.md:139-147` (Phase 2) lists all seven items as unchecked; Phase 0/1 (`:126-136`) are checked and genuinely present.

**Do not assume seed skills exist.** The directory `backend/app/resources/skills/` exists with the correct three filenames, matching `plan.md:100-102` — and nothing in `backend/app` references that directory.

### 6.4 Existing hooks for external guidance or config to reuse

**Content-loading precedent (the pattern to copy):**

- `backend/app/services/security_service.py:24`:
  ```python
  _CVE_DB_PATH = Path(__file__).resolve().parent.parent / "resources" / "cve_database.json"
  ```
  loaded by `load_offline_cve_database()` (`:26-36`), consumed at `:265` and `:605`. This is the only existing resource-file loader, and `specs/010-skill-injection/plan.md:109` names it explicitly as the model for skills: *"placed in `backend/app/resources/skills/` to sit alongside existing offline assets (`cve_database.json`) where future injection nodes can read them directly."* The directory and filenames already exist; only the loader and the content are missing.

**Config / env surface to extend** — `backend/app/config.py`, Pydantic `BaseSettings` (`:12-13`), multi-path `.env` loading at `:8-10` (cwd, `backend/.env`, repo root):

| Knob | Line | Default | Relevance |
|---|---|---|---|
| `MAX_REPAIR_ATTEMPTS` | `:60` | **5** | bounds the repair loop the skills must survive |
| `ALLOW_OFFLINE_MOCK` | `:63` | `False` | mock-LLM escape hatch; note `routes_requirements.py:59-62` resolves it from `os.environ` **first** and only then falls back to `settings`, so the two sources can disagree — a duplicated config surface |
| `WORKSPACE_DIR` | `:54-57` | `backend/workspaces` | per-session artifact root; the natural place to persist skill-injection metadata |
| `DOCKER_IMAGE` | `:46-49` | `maven:3.9-eclipse-temurin-21` | verifier identity — must be frozen for a valid A/B comparison |
| `MAVEN_CACHE_DIR` | `:50-53` | `~/.m2/repository` | read-only mount; a cold cache triggers the fake-success fallback |
| `MAX_CONCURRENT_SESSIONS` | `:43` | `2` | pilot throughput ceiling |
| `DATABASE_URL` | `:66-69` | `sqlite:///backend/studio.db` | where a `skills` table and injection log would go |

**State and in-memory stores to reuse or replace:**

| Hook | Location | Note |
|---|---|---|
| `GenerationAgentState` | `state.py:3-16` | the injection carrier — currently has no skill/guidance field |
| `state["logs"]` | every node | append-only; the cheapest injection audit trail (`docs/notes.tex:224` wants every injection logged) |
| `REPAIR_HISTORIES_STORE` | `backend/app/api/routes_tests.py` (imported `repair_node.py:16`) | per-session repair records — in-memory only |
| `BLOCKED_SESSIONS_STORE` | same | written `repair_node.py:67-70` |
| `SESSION_GENERATION_STATE` | `routes_session.py:32`, `:169` | full final graph state — in-memory only |
| `phase_progress_json` column | `session.py:48`; used `lifecycle_service.py:345,360,471,494` | the one existing free-form JSON persistence slot |
| `PipelineProgressEvent` + SSE | `pipeline_runner.py:59-86`, `:517-538`; `routes_session.py:37-66`, `:422-459` | two parallel event buses already exist — a place to surface injection events to the UI |

**The one genuine guidance-injection seam already in the code:** `format_repair_prompt(diag, context=None)` at **`backend/app/orchestrator/repair.py:85`**. Its `context` parameter is accepted, documented implicitly by the prompt body (`:101-102` interpolates it as `Context:`), and never supplied — `repair_node.py:100` calls `format_repair_prompt(diag)` with one argument and uses the result only as a `diff_summary` fallback string. Passing skill text into that parameter is the lowest-friction, highest-fidelity injection experiment available today, because it requires **no new LLM call** (the string still has no consumer) *or*, if `repair_node` is upgraded to invoke an LLM, exactly one new call site at a place the repair loop already visits on every attempt.

---

## Appendix — verification commands used

All read-only; no source file was modified.

```bash
cd /home/gjanampa/Projects/AI_AGENTS/agentIA
git log --oneline -12 && git status --short
git show --stat HEAD
wc -c backend/app/resources/skills/*.md backend/scripts/validate_seed_skills.py \
      backend/tests/test_seed_skills.py specs/010-skill-injection/{domains,fixers,tasks,task1-summary}.md
python3 -c "import sqlite3;c=sqlite3.connect('backend/studio.db');print(c.execute(
  \"select sql from sqlite_master where name='generation_sessions'\").fetchone()[0])"
grep -rn "generation_graph|create_generation_graph|sandbox_node|repair_node|validator_node" backend/app
grep -rn "\.invoke\(|\.ainvoke\(|with_structured_output" backend/app
grep -rn "repair_attempts" backend/app | grep -v "state.get\|max_repair"
find . -iname "*skill*" -not -path "./.git/*"
```

**Uncertainties in this report, stated explicitly:** (a) the `.env` file is absent from the repository, so runtime knob values are inferred from `config.py` defaults — if a deployment provides `MAX_REPAIR_ATTEMPTS=3`, §1.5's bound arithmetic becomes 3 rather than 5; (b) `studio.db` in the working tree may not be the file a given deployment uses (`DATABASE_URL` is overridable); (c) no test suite, Maven run, or Docker command was executed, so all statements about runtime behaviour are static-analysis conclusions.
