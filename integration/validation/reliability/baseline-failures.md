# Reproducción baseline

Entorno fijado: FastAPI 0.115.9, SQLAlchemy 2.0.40. Resultado: 27 passed, 1 failed en baseline-native.xml.

- test_published_contract_matches_actual_routes_and_models: pasa con las versiones fijadas; la divergencia previa provenía del entorno.
- test_atomic_asset_publish_supports_windows_long_temporary_paths: pasa en el checkout actual y temp aislado dentro del workspace; el clon profundo amplificaba MAX_PATH.
- test_deploy_devops_clean_session_behavior: reproduce 403 correcto al crear DOCKER sin suite verificada. Fixture/aserción pendiente de corregir; no se relaja gate.

Primer intento sandbox: SQLite temp de perfil restringido inaccesible; segundo con temp propio quedó interrumpido, no considerado evidencia funcional. La reproducción válida ejecutó fixtures propias fuera del sandbox, sin IA.
