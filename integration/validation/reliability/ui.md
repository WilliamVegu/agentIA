# Evidencia de interfaz

Validación local con Vitest y builds TypeScript/Vite de los dos frontends. No se presenta como una revisión visual manual de todas las pantallas ni como prueba de navegador contra un proveedor IA.

| Panel | Contrato comprobado |
|---|---|
| Overview | Estado/evidencia reales y separación de fuente, verificación y runtime |
| Especificación | Entrada y sesión propias, sin sustituir requisitos guardados |
| Requisitos | Guardar/aprobar revisión exacta, conflicto, invalidación y regeneración explícita |
| Arquitectura | Artefactos y progreso ligados a sesión |
| Modelos/SQL | Draft/configuración de motor y artefactos de la sesión |
| Generación | Eventos aislados, cierre de suscriptores, replay/resync y estados terminales |
| Explorador | Archivos de la sesión y acceso controlado |
| Seguridad/calidad | Score null, métricas cero, hallazgos canónicos, auditoría sin fuentes |
| DevOps | Modo explícito, estado observado, stop y confirmación de cleanup |
| Export/publicación | Gate, entrega de fuentes/verified y error Git |

Pruebas: `reliability_views`, `reliability_services`, `requirements_revision`, `session_sse_isolation`, suites `views_*`, `services` y journeys de interfaz. Los informes `frontend-*-acceptance-tests.log` contienen 113 tests Spring y 76 Quarkus. Tras alinear los fixtures con el contrato canónico, `frontend-*-contract-final.log` registra 23/25 tests aprobados. Ambos `frontend-*-acceptance-build.log` finalizaron correctamente; Vite informa un aviso de tamaño de bundle, sin error de compilación.
