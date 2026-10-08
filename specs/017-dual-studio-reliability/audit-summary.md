# Base de evidencia y trazabilidad

Origen: análisis solicitado por el usuario sobre dual-systems-selector, commit cd50688c8188b47ba789ec30683a50eabc7bd593, realizado el 7/8 de octubre de 2026. Informe local: [ANALISIS_COMPLETO.md](C:/Users/willi/.codex/visualizations/2026/10/08/01a1195c-48aa-7440-9a3d-2d365be579b1/audit/ANALISIS_COMPLETO.md).

Esta síntesis permite ejecutar el plan aunque no esté disponible el artefacto local completo. Es evidencia histórica, no resultados de la futura corrección.

| Hallazgo | Evidencia de partida | Cierre previsto |
|---|---|---|
| H01 | Quarkus leyó/modificó un sentinel fuera del workspace mediante HTTP | US1: resolver estricto y tests de rutas |
| H02 | Draft LedgerEntry aprobado acabó como Order/Pedido; Quarkus perdió paquete/puerto al GET | US2: revisiones autoritativas |
| H03 | Quarkus PASS sobre vacío, VERIFIED para sesión inexistente y UI aprobada con 0 tests | US3 + US6: evidencia y tarjetas |
| H04 | Ambos Java aceptaron correo inválido e importe -10 con 201 | US4: restricciones y pruebas negativas |
| H05 | Quarkus COMPLETED antes de Compose fallar por 8080 ocupado; salud atribuida a otro servicio | US5 + US3: propiedad y resultado final |
| H06 | stop usa compose down -v y silencia errores; no ejecutado por seguridad | US1 + US5: stop/cleanup distintos |
| H07 | remote autenticado en config, force=True; revisión estática | US1: Git temporal seguro |
| H08 | UI database=H2 quedó POSTGRESQL; alias canonical funcionó | US4 + US6: configuración/contratos |
| H09 | Quarkus DDL PostgreSQL/H2 montado como init MySQL; generación confirmada | US4: dialectos y DB real |
| H10 | Quarkus ignoró target, aceptó pausa terminal; ambos cancelaron COMPLETED; gate no persistido | US3: transiciones/checkpoints |
| H11 | UUID Spring se volvió Long; fechas Quarkus se volvieron String | US4: descriptor común por backend |
| H12 | SAST ambos mostró 284/12/2.2 para cero; texto decía desplegado al omitir | US6: ceros/null y textos |
| H13 | Quarkus anuncia re-verificación sin ejecutarla; promptHint/guidanceHint difieren | US3 + US6: reparación real |
| H14 | CI SAST/secretos Quarkus sólo echo; Trivy sí existía | US8: auditoría ejecutable |
| O01 | Entorno Quarkus incompleto, alias Python no funcional, pip ausente | Setup/US8 |
| O02 | Cola SSE consumida por cliente; inspección estática | US7 |
| O03 | Operaciones/historial en memoria y telemetría degradada | US3/US7 |
| O04 | Falta matriz completa DB/modos/arquitecturas, IA real y CI remoto | US8 y límites explícitos |
| O05 | Hashes originales impiden fixes legítimos si se reescribe baseline sin trazabilidad | Cierre: manifest de revisiones |
| O06 | Constituciones limitan reparaciones a 3; código/UI usa 5 | US3: constante y tests |
| O07 | Primera prueba de rutas largas falló sólo en clon profundo; pasó en copia corta | Setup: reproducción antes de fix |

## Resultados históricos

- Spring Python: 1464 passed, 3 failed, 42 skipped.
- Quarkus Python: 534 passed, 3 skipped.
- Spring frontend: 105 passed; Quarkus frontend: 65 passed; ambos builds correctos.
- Launcher: 6 passed.
- Java H2: Spring 9 passed, Quarkus 6 passed; salud/alta/lista/consulta/baja correctas.
- 2090 archivos versionados intactos; 1446/573 hashes de snapshots verificados.
- Ninguna API key empleada; cero llamadas IA reales.

Las tres aserciones Spring no son tres defectos independientes: rutas profundas del clon (repetición corta pasó), diferencia ValidationError input/ctx por FastAPI instalado 0.142.2 vs constraint 0.115.9, y fixture DOCKER con expectativa SOURCE_ONLY. Resolver por su causa; no modificar gates para conseguir verde.

