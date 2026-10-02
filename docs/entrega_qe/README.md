# Entrega QE — Flujos y Casos de Prueba

Paquete de aseguramiento de calidad del **Microservice Code Studio (AgentIA)**: los flujos del
sistema documentados, cómo se probaron, y el resultado de cada caso ejecutado.

---

## Qué contiene

| Archivo | Qué es | Para quién |
| --- | --- | --- |
| **`informe_qe.pdf`** | El informe formal: los 14 flujos con su ficha, la estrategia de prueba, los casos ejecutados y validados, la trazabilidad y los defectos encontrados | Revisión / dirección |
| **`plantilla_presentacion.pptx`** | 15 diapositivas con notas del orador en cada una | Exposición |
| **`matriz_casos_de_prueba.csv`** | Un caso por fila: identificador, flujo, suite, archivo, nombre, resultado, duración y motivo si falló | Verificación caso por caso |
| **`anexo_snippets.md`** | Fragmentos de código comentados, por tipo de prueba | Equipo técnico |
| **`resumen_ejecucion.json`** | Totales por flujo y por resultado | Automatización |

La **evidencia cruda** (salida completa de ambas suites e informes JUnit de origen) está en
`reports/qe/entrega/`.

---

## Cómo leer la matriz de casos

Cada caso tiene un identificador estable por flujo: `F6-014` es el caso 14 del flujo 6. Los
flujos son:

| Código | Flujo |
| --- | --- |
| F0 | Autenticación y sesión de operador |
| F1 | Ingesta y validación de especificación (blueprints) |
| F2 | Requisitos → Historias BDD |
| F3 | Diseño arquitectónico |
| F4 | Modelos de dominio y esquema SQL |
| F5 | Generación de código y síntesis de pruebas |
| F6 | Sandbox hermético y auto-reparación acotada |
| F7 | Auditoría de seguridad y Quality Gate |
| F8 | DevOps: manifiestos, contenedores y despliegue local |
| F9 | Exportación, artefactos y publicación Git |
| F10 | Orquestación Auto-Pilot y ciclo de vida de la sesión |
| F11 | Trazabilidad de costos y telemetría |
| F12 | Playground de API en vivo |
| FT | Transversal: interfaz, tema, contratos de servicio |

**Un caso está validado cuando la suite lo reporta como `PASS`.** Un caso en `FAIL` no se
oculta: aparece en el informe con el motivo que reportó el ejecutor, y se explica en la sección
de limitaciones. Los `SKIP` son omisiones deliberadas y también se declaran.

---

## Reproducir los resultados

```bash
# Backend: suite completa, cobertura e informe JUnit
.venv/bin/python -m pytest -q --cov=backend/app --cov-report=term-missing \
  --junitxml=reports/qe/entrega/junit-backend.xml

# Frontend: suite completa e informe JUnit
cd frontend && npx vitest run --reporter=default --reporter=junit \
  --outputFile.junit=../reports/qe/entrega/junit-frontend.xml

# Regenerar la matriz, las métricas y las tablas del informe
.venv/bin/python docs/entrega_qe/build_matriz.py
cd docs/entrega_qe && pdflatex informe_qe.tex && pdflatex informe_qe.tex

# Regenerar la presentación con las cifras nuevas
.venv/bin/python docs/entrega_qe/build_presentacion.py
```

Las cifras del informe **no están escritas a mano**: `build_matriz.py` las extrae de los
informes JUnit y genera `metricas_generadas.tex` y `resultados_generados.tex`, que el informe
incorpora. Si un caso cambia de resultado, la tabla cambia sola.

---

## La idea que sostiene todo el paquete

**Cobertura no es corrección.** La cobertura mide qué se ejecutó, no qué es verdad. Y en este
producto hay una brecha que conviene tener presente: la plataforma escribe las pruebas
Mockito del código que ella misma genera y luego las ejecuta, de modo que un build en verde
demuestra que el código cumple *sus* pruebas, no los escenarios de aceptación del blueprint.
Cerrar esa brecha —pruebas de aceptación HTTP independientes contra el servicio desplegado— es
el siguiente entregable de mayor valor y está fuera del alcance de este trabajo.
