# Validación local — 7 de octubre de 2026

La validación completa NO está aprobada: la suite backend tiene fallos. La aplicación local sí responde y el frontend supera sus pruebas, compilación y comprobaciones de navegador.

| Comprobación | Resultado |
|---|---|
| backend | 1396 aprobadas; 67 fallidas; 0 errores; 42 omitidas |
| frontend | 105 aprobadas; 0 fallidas; 0 errores; 0 omitidas |
| Compilación frontend (TypeScript + Vite) | Aprobada; advertencia de bundle JS de 577,20 kB |
| HTTP y navegador real (development) | 34 aprobadas; 0 fallidas |
| HTTP y navegador real (production) | 34 aprobadas; 0 fallidas |

## Alcance

HTTP contra backend :8000 y proxy frontend :3000; navegador Microsoft Edge headless contra desarrollo :3000 y producción :3001. Acceso local MVP, rechazo de origen externo y clientes sin sesión, consulta de sesiones, 404, validación de payload, logout y revocación. Navegación por las diez pestañas sin sesión de proyecto seleccionada, recarga autenticada, ausencia de excepciones JavaScript y HTTP 5xx. Sin interceptar ni simular las respuestas del servidor en estas comprobaciones.

Las suites automatizadas incluyen pruebas unitarias e integraciones con dobles de proveedores externos. Un resultado aprobado de estas suites no acredita una llamada a IA, publicación Git, compilación Java ni despliegue Docker reales.

## Límites del entorno

- Docker CLI no disponible en PATH ni en la ubicación habitual; Docker SDK no logra conectar al motor (named pipe inexistente). No se realizaron nuevas pruebas reales de contenedores, SQL en contenedor ni Kubernetes.
- MLflow :5000 no está disponible; /healthz declara tracing=false y registra el error. La API sigue UP.
- No se realizaron llamadas pagadas a proveedores IA ni publicaciones Git remotas.
- Los conteos omitidos son casos no ejecutados, no aprobaciones.

## Diagnóstico y prioridades

1. Revisar los 500 del endpoint de reparación: `test_quickstart_feature_005_e2e` y `test_repair_endpoint_success_and_boundary`. Estos resultados requieren diagnóstico; las comprobaciones HTTP sanas no cubren esa operación.
2. Revisar generación, cola, pausa/reanudación, SSE y estados persistidos: varios tests dejan sesiones QUEUED o no reciben los eventos previstos. No atribuir todos estos fallos a fixtures sin reproducir cada caso.
3. Actualizar o corregir contratos de autenticación y evidencia de entrega. Hay casos que esperan 200/201 y reciben 401/403. El ejemplo de publicación reproducido crea una sesión COMPLETED/VERIFIED sin evidencia suficiente; la política actual exige evidencia. Mantener los controles mientras se determina el contrato correcto.
4. Revisar fixtures Git: seis tests intentan push y fallan porque origin no es un repositorio válido; no hubo publicación exitosa.
5. Revisar diferencias de OpenAPI, modo SOURCE_ONLY/Docker, recuperación de identidad, generación DevOps, guards de especificación y límite de reparación histórico de cinco intentos.

No se cambiaron controles ni código de aplicación para forzar resultados verdes. Se conservó el cambio preexistente de `frontend/package-lock.json`; se revirtió únicamente la regeneración incidental de un informe histórico producida por la suite.

## Fallos por módulo

| Módulo | Fallos/errores |
|---|---|
| `backend.tests.test_qe_session_surface` | 15 |
| `backend.tests.test_qe_pipeline_autopilot` | 9 |
| `backend.tests.test_qe_publish_git` | 6 |
| `backend.tests.test_qe_lifecycle_rules` | 5 |
| `backend.tests.test_app_examples` | 4 |
| `backend.tests.test_qe_deployment_identity` | 4 |
| `backend.tests.test_sessions_api` | 4 |
| `backend.tests.test_e2e_flow` | 3 |
| `backend.tests.test_artifact_retrieval` | 2 |
| `backend.tests.test_code_generation_module` | 2 |
| `backend.tests.test_qe_injection_guard` | 2 |
| `backend.tests.test_routes_tests` | 2 |
| `backend.tests.test_devops_contract` | 1 |
| `backend.tests.test_diagnostic_record` | 1 |
| `backend.tests.test_entry_point_parity` | 1 |
| `backend.tests.test_generation_stages_model` | 1 |
| `backend.tests.test_qe_deploy_docker` | 1 |
| `backend.tests.test_qe_specification_persistence` | 1 |
| `backend.tests.test_routes_devops` | 1 |
| `backend.tests.test_routes_security` | 1 |
| `backend.tests.test_test_analysis_service` | 1 |

## Fallos individuales

- `backend.tests.test_app_examples::test_example_publish_to_git_with_mocked_boundary`: assert 403 == 200  +  where 403 = <Response [403 Forbidden]>.status_code
- `backend.tests.test_app_examples::test_example_export_blocked_when_quality_gate_fails`: AssertionError: assert 'Quality Gate is BLOCKED' in 'Source delivery requires completed generation and current verification or explicit unexecuted tests in no-Docker mode.'
- `backend.tests.test_app_examples::test_example_export_returns_a_zip_when_gate_passes`: assert 403 == 200  +  where 403 = <Response [403 Forbidden]>.status_code
- `backend.tests.test_app_examples::test_example_pipeline_stops_at_blocked_quality_gate`: AssertionError: assert not True  +  where True = exists()  +    where exists = ((WindowsPath('C:/Users/GenAIAUGPERUSR2/AppData/Local/Temp/pytest-of-GenAIAUGPERUSR2/pytest-19/test_example_pipeline_stops_at0') / 'example-runner-session') / 'docker-compose.yml').exists
- `backend.tests.test_artifact_retrieval::test_architecture_design_save_and_retrieve`: assert 404 == 200  +  where 404 = <Response [404 Not Found]>.status_code
- `backend.tests.test_artifact_retrieval::test_models_design_save_and_retrieve`: assert 404 == 200  +  where 404 = <Response [404 Not Found]>.status_code
- `backend.tests.test_code_generation_module::test_complete_langgraph_generation_graph`: AssertionError: assert 'COMPLETED' == 'BLOCKED'      - BLOCKED   + COMPLETED
- `backend.tests.test_code_generation_module::test_api_artifact_listing_and_export_zip`: assert 403 == 200  +  where 403 = <Response [403 Forbidden]>.status_code
- `backend.tests.test_devops_contract::test_published_contract_matches_actual_routes_and_models`: AssertionError: assert {'openapi': '...}}, ...}, ...} == {'openapi': '...}}, ...}, ...}      Omitting 4 identical items, use -vv to show   Differing items:   {'components': {'securitySchemes': {'StudioSession': {'type': 'apiKey', 'in': 'cookie', 'name': 'agentia_session'}}, '... ['SKIPPED_BY_CHOICE', 'DEGRADED', 'IDLE', 'BUILDING', 'RUNNING', 'HEALTHY', ...], 'title': 'DeploymentStatus'}, ...}}} != {'components': {'securitySchemes': {'StudioSession': {'type': 'apiKey', 'in': 'cookie', 'name': 'agentia_session'}}, '... ['SKIPPED_BY_CHOICE', 'DEGRADED', 'IDLE', 'BUILDING', 'RUNNING', 'HEALTHY', 
- `backend.tests.test_diagnostic_record::test_the_sequential_pipeline_terminates_and_records_a_stage_exhaustion`: AssertionError: assert <SessionPhase...ITIALIZATION'> == <SessionPhase...LED: 'FAILED'>      - FAILED   + INITIALIZATION
- `backend.tests.test_e2e_flow::test_scenario_2_autonomous_generation_and_export`: assert 403 == 200  +  where 403 = <Response [403 Forbidden]>.status_code
- `backend.tests.test_e2e_flow::test_quickstart_feature_005_e2e`: assert 500 == 200  +  where 500 = <Response [500 Internal Server Error]>.status_code
- `backend.tests.test_e2e_flow::test_full_unified_orchestration_e2e`: assert 403 == 200  +  where 403 = <Response [403 Forbidden]>.status_code
- `backend.tests.test_entry_point_parity::test_the_worker_decides_the_mode_with_the_credentials_and_states_the_key`: KeyError: 'api_key'
- `backend.tests.test_generation_stages_model::test_paired_blueprints_produce_differing_requests`: AssertionError: assert '@NotBlank' not in '# Domain mo...that file.\n'      '@NotBlank' is contained here:   ?           ^^^^^      @Length, @NotBlank, and @Pattern MUST ONLY be applied to String and Collection types. NEVER place @Size, @NotBlank, or @Pattern on UUID, Long, Integer, Double, Boolean, or Date/Time fields, as Hibernate Validator will throw UnexpectedTypeException HV000030.   ?           ^^^^^^^^^^^^^^          ## Untrusted input...      ...Full output truncated (79 lines hidden), use '-vv' to show
- `backend.tests.test_qe_deploy_docker::test_a_successful_deploy_is_only_called_healthy_after_actuator_says_up`: AssertionError: assert ['docker', 'c...ose.yml', ...] == ['docker', 'c...p', '-d', ...]      At index 4 diff: '-f' != 'up'   Left contains 4 more items, first extra item: 'never'   Use -v to get more diff
- `backend.tests.test_qe_deployment_identity::test_a_session_with_no_container_is_not_reported_healthy`: AssertionError: assert <DeploymentSt...ED_BY_CHOICE'> == <DeploymentSt....IDLE: 'IDLE'>      - IDLE   + SKIPPED_BY_CHOICE
- `backend.tests.test_qe_deployment_identity::test_an_existing_record_is_probed_on_its_own_port`: AssertionError: assert <DeploymentSt...ED_BY_CHOICE'> == <DeploymentSt...HY: 'HEALTHY'>      - HEALTHY   + SKIPPED_BY_CHOICE
- `backend.tests.test_qe_deployment_identity::test_state_is_recovered_from_the_compose_project_label`: AssertionError: the app container, not the database assert None == 'app111'  +  where None = LocalDeploymentSession(sessionId='session-x', dbEngine=None, containerId=None, databaseContainerId=None, sourceSnapsho...=None, operationId=None, operationKind=None, operationPhase=None, finishedAt=None, cancelRequested=False, message=None).containerId
- `backend.tests.test_qe_deployment_identity::test_the_database_container_is_never_mistaken_for_the_service`: AssertionError: assert <DeploymentSt...ED_BY_CHOICE'> == <DeploymentSt....IDLE: 'IDLE'>      - IDLE   + SKIPPED_BY_CHOICE
- `backend.tests.test_qe_injection_guard::test_the_transform_endpoint_refuses_an_injected_narrative`: assert 401 == 400  +  where 401 = <Response [401 Unauthorized]>.status_code
- `backend.tests.test_qe_injection_guard::test_the_specification_ingestion_path_is_guarded`: AssertionError: an instruction-shaped validation rule was accepted into a blueprint; it reaches the same models the requirements guard already protects assert 401 == 400  +  where 401 = <Response [401 Unauthorized]>.status_code
- `backend.tests.test_qe_lifecycle_rules::test_two_failed_repairs_do_not_block_phase_five`: AssertionError: assert <PhaseStatus....'IN_PROGRESS'> == <PhaseStatus....: 'COMPLETED'>      - COMPLETED   + IN_PROGRESS
- `backend.tests.test_qe_lifecycle_rules::test_a_blocked_quality_gate_blocks_phase_six_and_reports_why`: AssertionError: assert <PhaseStatus....'NOT_STARTED'> == <PhaseStatus....ED: 'BLOCKED'>      - BLOCKED   + NOT_STARTED
- `backend.tests.test_qe_lifecycle_rules::test_the_quality_gate_verdict_and_finding_count_reach_the_summary`: KeyError: 'qualityGate'
- `backend.tests.test_qe_lifecycle_rules::test_a_compose_file_completes_phase_seven_and_surfaces_the_deploy_status`: AssertionError: assert <PhaseStatus....'IN_PROGRESS'> == <PhaseStatus....: 'COMPLETED'>      - COMPLETED   + IN_PROGRESS
- `backend.tests.test_qe_lifecycle_rules::test_a_fully_complete_session_reports_completion`: AssertionError: assert 57.1 == 100.0  +  where 57.1 = LifecycleState(session_id='qe-lifecycle-session', current_phase=<LifecyclePhase.INITIAL: 'INITIAL'>, completion_percen...PipelineExecutionMode.GUIDED_STEP: 'GUIDED_STEP'>, is_outdated=False, pipeline_status=<PipelineRunStatus.IDLE: 'IDLE'>).completion_percentage
- `backend.tests.test_qe_pipeline_autopilot::test_pausing_after_a_step_stops_before_the_next_one[SECURITY_AUDIT]`: AssertionError: the step after SECURITY_AUDIT ran despite the pause assert not True  +  where True = exists()  +    where exists = (WindowsPath('C:/Users/GenAIAUGPERUSR2/AppData/Local/Temp/pytest-of-GenAIAUGPERUSR2/pytest-19/test_pausing_after_a_step_stop5/qe-autopilot-session') / 'docker-compose.yml').exists
- `backend.tests.test_qe_pipeline_autopilot::test_pause_switches_the_session_to_guided_step`: AssertionError: assert False is True  +  where False = <function pause_pipeline at 0x00000213E5AE2FC0>('qe-autopilot-session')  +    where <function pause_pipeline at 0x00000213E5AE2FC0> = pr.pause_pipeline
- `backend.tests.test_qe_pipeline_autopilot::test_pausing_a_session_that_was_never_started_reports_whether_it_is_paused`: AssertionError: assert False is True  +  where False = <function pause_pipeline at 0x00000213E5AE2FC0>('qe-orphan')  +    where <function pause_pipeline at 0x00000213E5AE2FC0> = pr.pause_pipeline
- `backend.tests.test_qe_pipeline_autopilot::test_resume_replays_the_session_credentials_and_waits_for_the_old_thread`: AssertionError: assert False is True  +  where False = <function resume_pipeline at 0x00000213E5AE3060>('qe-autopilot-session')  +    where <function resume_pipeline at 0x00000213E5AE3060> = pr.resume_pipeline
- `backend.tests.test_qe_pipeline_autopilot::test_force_starts_a_run_even_while_another_is_alive`: AssertionError: assert False is True  +  where False = <function run_pipeline at 0x00000213E5AE3560>('qe-autopilot-session', force=True)  +    where <function run_pipeline at 0x00000213E5AE3560> = pr.run_pipeline
- `backend.tests.test_qe_pipeline_autopilot::test_a_failed_schema_synthesis_falls_back_to_this_blueprints_own_ddl`: AssertionError: the run died in the fallback instead of falling back assert <PipelineRunS...LED: 'FAILED'> == <PipelineRunS...: 'COMPLETED'>      - COMPLETED   + FAILED
- `backend.tests.test_qe_pipeline_autopilot::test_auto_deploy_asks_for_the_local_deployment`: AssertionError: assert [] == [('qe-autopil...lot-session')]      Right contains one more item: ('qe-autopilot-session', 'C:\\Users\\GenAIAUGPERUSR2\\AppData\\Local\\Temp\\pytest-of-GenAIAUGPERUSR2\\pytest-19\\test_auto_deploy_asks_for_the_0\\qe-autopilot-session')   Use -v to get more diff
- `backend.tests.test_qe_pipeline_autopilot::test_a_blocking_quality_gate_stops_before_devops_even_with_auto_deploy`: AssertionError: assert not True  +  where True = exists()  +    where exists = (WindowsPath('C:/Users/GenAIAUGPERUSR2/AppData/Local/Temp/pytest-of-GenAIAUGPERUSR2/pytest-19/test_a_blocking_quality_gate_s0/qe-autopilot-session') / 'docker-compose.yml').exists
- `backend.tests.test_qe_pipeline_autopilot::test_an_entity_without_a_primary_key_gets_one`: app.services.specification_guard.UnlikelySpecificationError: spec does not look like a specification: it names no entities, operations or fields, and has no structure (headings, lists, Given/When/Then); it is 1 word(s) long
- `backend.tests.test_qe_publish_git::test_a_successful_publish_returns_the_branch_urls_and_a_commit`: RuntimeError: Git push failed to https://github.com/corp/orders.git: Cmd('git') failed due to: exit code(128)   cmdline: git push origin feature/001-order-service:feature/001-order-service   stderr: 'fatal: 'origin' does not appear to be a git repository fatal: Could not read from remote repository.  Please make sure you have the correct access rights and the repository exists.'
- `backend.tests.test_qe_publish_git::test_the_token_reaches_the_remote_during_the_push`: RuntimeError: Git push failed to https://github.com/corp/orders.git: Cmd('git') failed due to: exit code(128)   cmdline: git push origin feature/001-order-service:feature/001-order-service   stderr: 'fatal: 'origin' does not appear to be a git repository fatal: Could not read from remote repository.  Please make sure you have the correct access rights and the repository exists.'
- `backend.tests.test_qe_publish_git::test_the_token_is_scrubbed_from_the_remote_after_a_successful_publish`: RuntimeError: Git push failed to https://github.com/corp/orders.git: Cmd('git') failed due to: exit code(128)   cmdline: git push origin feature/001-order-service:feature/001-order-service   stderr: 'fatal: 'origin' does not appear to be a git repository fatal: Could not read from remote repository.  Please make sure you have the correct access rights and the repository exists.'
- `backend.tests.test_qe_publish_git::test_a_new_remote_is_created_with_the_authenticated_url`: RuntimeError: Git push failed to https://github.com/corp/orders.git: Cmd('git') failed due to: exit code(128)   cmdline: git push origin feature/001:feature/001   stderr: 'fatal: 'origin' does not appear to be a git repository fatal: Could not read from remote repository.  Please make sure you have the correct access rights and the repository exists.'
- `backend.tests.test_qe_publish_git::test_the_committer_identity_is_recorded`: RuntimeError: Git push failed to https://github.com/corp/orders.git: Cmd('git') failed due to: exit code(128)   cmdline: git push origin feature/001-order-service:feature/001-order-service   stderr: 'fatal: 'origin' does not appear to be a git repository fatal: Could not read from remote repository.  Please make sure you have the correct access rights and the repository exists.'
- `backend.tests.test_qe_publish_git::test_publishing_to_an_existing_repository_does_not_reinitialize`: RuntimeError: Git push failed to https://github.com/corp/orders.git: Cmd('git') failed due to: exit code(128)   cmdline: git push origin feature/001-order-service:feature/001-order-service   stderr: 'fatal: 'origin' does not appear to be a git repository fatal: Could not read from remote repository.  Please make sure you have the correct access rights and the repository exists.'
- `backend.tests.test_qe_session_surface::test_a_completed_session_is_listed_at_one_hundred_percent`: AssertionError: assert 0.0 == 100.0  +  where 0.0 = GenerationSessionListItem(session_id='qe-session-surface', spec_id='spec-qe', spec_name='OrderService', status=<Sessio...lifecycle_mode='GUIDED_STEP', completion_percentage=0.0, created_at=datetime.datetime(2026, 10, 7, 15, 47, 49, 235075)).completion_percentage
- `backend.tests.test_qe_session_surface::test_a_session_whose_lifecycle_is_complete_is_promoted_to_completed`: AssertionError: assert 57.1 == 100.0  +  where 57.1 = GenerationSessionListItem(session_id='qe-session-surface', spec_id='spec-qe', spec_name='OrderService', status=<Sessio...ifecycle_mode='GUIDED_STEP', completion_percentage=57.1, created_at=datetime.datetime(2026, 10, 7, 15, 47, 49, 356787)).completion_percentage
- `backend.tests.test_qe_session_surface::test_quick_start_without_a_name_uses_a_stable_default`: fastapi.exceptions.HTTPException: 400: {'error': 'UNLIKELY_SPECIFICATION', 'field': 'prompt', 'message': 'La solicitud no describe un requerimiento de microservicio o arquitectura de software válido. Por favor, describa un objetivo de negocio o funcionalidad backend (ej. gestión de pedidos, clientes, inventario, procesamiento de pagos o catálogo de productos). Motivo detectado: it names no entities, operations or fields, and has no structure (headings, lists, Given/When/Then); it is 1 word(s) long.', 'detailMessage': 'prompt does not look like a specification: it names no entities, operations 
- `backend.tests.test_qe_session_surface::test_cancelling_a_session_marks_it_cancelled_and_frees_its_slot`: AssertionError: a cancelled session must not hold a worker slot assert [] == ['qe-session-surface']      Right contains one more item: 'qe-session-surface'   Use -v to get more diff
- `backend.tests.test_qe_session_surface::test_a_completed_run_records_verified_and_reports_the_substituted_verification`: AssertionError: assert <SessionStatu...UED: 'QUEUED'> == <SessionStatu...: 'COMPLETED'>      - COMPLETED   + QUEUED
- `backend.tests.test_qe_session_surface::test_a_completed_run_with_a_real_verification_reports_no_fallback`: AssertionError: no session_completed event was broadcast
- `backend.tests.test_qe_session_surface::test_the_pipeline_streams_phase_transitions_logs_and_verification`: AssertionError: assert 0 >= 4  +  where 0 = <built-in method count of list object at 0x00000213EAE35800>('phase_transition')  +    where <built-in method count of list object at 0x00000213EAE35800> = [].count
- `backend.tests.test_qe_session_surface::test_the_test_node_announces_test_synthesis`: KeyError: 'qe-session-surface'
- `backend.tests.test_qe_session_surface::test_a_repair_beyond_the_limit_is_reported_as_blocked`: AssertionError: no repair_iteration event was broadcast
- `backend.tests.test_qe_session_surface::test_a_blocked_run_is_persisted_and_diagnosed`: AssertionError: assert <SessionStatu...UED: 'QUEUED'> == <SessionStatu...ED: 'BLOCKED'>      - BLOCKED   + QUEUED
- `backend.tests.test_qe_session_surface::test_a_crash_inside_the_graph_still_terminates_the_session`: AssertionError: assert <SessionStatu...UED: 'QUEUED'> == <SessionStatu...ED: 'BLOCKED'>      - BLOCKED   + QUEUED
- `backend.tests.test_qe_session_surface::test_the_instruction_revision_is_recorded_when_the_set_loads`: KeyError: 'qe-session-surface'
- `backend.tests.test_qe_session_surface::test_an_unloadable_instruction_set_does_not_break_the_offline_path`: KeyError: 'qe-session-surface'
- `backend.tests.test_qe_session_surface::test_the_worker_slot_is_released_even_when_the_run_crashes`: AssertionError: assert [] == ['qe-session-surface']      Right contains one more item: 'qe-session-surface'   Use -v to get more diff
- `backend.tests.test_qe_session_surface::test_the_generation_state_is_kept_for_inspection`: KeyError: 'qe-session-surface'
- `backend.tests.test_qe_specification_persistence::test_the_uploaded_document_survives_and_keeps_its_content`: assert 401 == 201  +  where 401 = <Response [401 Unauthorized]>.status_code
- `backend.tests.test_routes_devops::test_generate_devops_manifests_success`: assert 'postgres:16-alpine' in "services:\n  order-service:\n    image: ${COMPOSE_PROJECT_NAME}-order-service:local\n    pull_policy: never\n    buil... volumes:\n    - appdata:/app/data\n    network_mode: none\n    restart: 'no'\nvolumes:\n  appdata: {}\n  dbdata: {}\n"
- `backend.tests.test_routes_security::test_session_audit_and_export_blocking`: AssertionError: assert 'Quality Gate is BLOCKED' in 'Source delivery requires completed generation and current verification or explicit unexecuted tests in no-Docker mode.'
- `backend.tests.test_routes_tests::test_repair_endpoint_success_and_boundary`: assert 500 == 200  +  where 500 = <Response [500 Internal Server Error]>.status_code
- `backend.tests.test_routes_tests::test_get_repairs_and_manual_override`: assert 404 == 200  +  where 404 = <Response [404 Not Found]>.status_code
- `backend.tests.test_sessions_api::test_list_sessions_endpoint`: assert 401 == 200  +  where 401 = <Response [401 Unauthorized]>.status_code
- `backend.tests.test_sessions_api::test_quick_start_session_endpoint`: assert 401 == 201  +  where 401 = <Response [401 Unauthorized]>.status_code
- `backend.tests.test_sessions_api::test_quick_start_session_default_name`: assert 401 == 201  +  where 401 = <Response [401 Unauthorized]>.status_code
- `backend.tests.test_sessions_api::test_quick_start_session_with_auto_run`: assert 401 == 201  +  where 401 = <Response [401 Unauthorized]>.status_code
- `backend.tests.test_test_analysis_service::test_execute_repair_iteration_and_cap_at_5`: AssertionError: assert <RepairOutcom...LED_CONTINUE'> == <RepairOutcom...SS: 'SUCCESS'>      - SUCCESS   + FAILED_CONTINUE

## Evidencia y reproducción

- `backend.log`, `backend.xml`, `frontend-tests.log`, `frontend.xml`, `frontend-build.log`.
- `development-smoke.json`, `production-smoke.json`, `local_smoke.py`, capturas y textos del navegador.
- `failures.json` contiene trazas completas; `skipped.json` conserva motivos de omisión.

```powershell
python -m pytest backend/tests -q --tb=short --junitxml=reports/validation-20261007/backend.xml
cd frontend
npm.cmd test
npm.cmd run build
```

Versiones: Python 3.12.8; Node 22.15.1; npm 10.9.2; FastAPI 0.115.9; Pydantic 2.13.5; pytest 9.1.1; Playwright 1.52.0.
