#!/usr/bin/env python3
"""Generate the presentation template (PowerPoint) for the QE delivery.

Generated rather than hand-built so the numbers on the slides come from the same JSON as the
report and the case matrix: one source of truth, three artefacts.

Every slide carries **speaker notes**. The audience for this deck is a review board; the
speaker is new to QE, so the notes say what to say, not only what to show.

Usage (from the repository root):

    .venv/bin/python docs/entrega_qe/build_presentacion.py
"""

from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "entrega_qe"
SUMMARY = json.loads((OUT / "resumen_ejecucion.json").read_text(encoding="utf-8"))

ACCENT = RGBColor(0x1E, 0x50, 0x96)
DARK = RGBColor(0x1F, 0x29, 0x37)
MUTED = RGBColor(0x64, 0x74, 0x8B)
GOOD = RGBColor(0x1E, 0x78, 0x46)
WARN = RGBColor(0xA0, 0x3C, 0x28)
LIGHT = RGBColor(0xF1, 0xF5, 0xF9)
FONT = "Century Gothic"

TOTAL = SUMMARY["total"]
PASS = SUMMARY["por_resultado"].get("PASS", 0)
FAIL = SUMMARY["por_resultado"].get("FAIL", 0) + SUMMARY["por_resultado"].get("ERROR", 0)
SKIP = SUMMARY["por_resultado"].get("SKIP", 0)
BY_SUITE = SUMMARY["por_suite"]
FLOWS = SUMMARY["por_flujo"]
FLOW_COUNT = len(FLOWS)

FLOW_TITLES = {
    "F0": "Autenticación y sesión",
    "F1": "Ingesta de especificación",
    "F2": "Requisitos → Historias BDD",
    "F3": "Diseño arquitectónico",
    "F4": "Modelos y esquema SQL",
    "F5": "Generación de código y pruebas",
    "F6": "Sandbox hermético y auto-reparación",
    "F7": "Seguridad y Quality Gate",
    "F8": "DevOps y despliegue local",
    "F9": "Exportación y publicación Git",
    "F10": "Orquestación Auto-Pilot",
    "F11": "Costos y telemetría",
    "F12": "Playground de API",
    "FT": "Interfaz y flujos transversales",
}


def blank(prs: Presentation):
    return prs.slides.add_slide(prs.slide_layouts[6])


def band(slide, top=Inches(0), height=Inches(0.16), color=ACCENT):
    shape = slide.shapes.add_shape(1, Inches(0), top, prs_width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    shape.shadow.inherit = False


def text(slide, left, top, width, height, runs, align=PP_ALIGN.LEFT, spacing=1.0):
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    first = True
    for run in runs:
        para = frame.paragraphs[0] if first else frame.add_paragraph()
        first = False
        para.alignment = align
        para.line_spacing = spacing
        para.space_after = Pt(run.get("space", 6))
        piece = para.add_run()
        piece.text = run["t"]
        piece.font.size = Pt(run.get("size", 16))
        piece.font.bold = run.get("bold", False)
        piece.font.color.rgb = run.get("color", DARK)
        piece.font.name = FONT
    return box


def notes(slide, body: str):
    slide.notes_slide.notes_text_frame.text = body


def content_slide(prs, title: str, runs, note: str):
    slide = blank(prs)
    band(slide)
    text(slide, Inches(0.6), Inches(0.42), prs_width - Inches(1.2), Inches(0.8),
         [{"t": title, "size": 30, "bold": True, "color": ACCENT}])
    text(slide, Inches(0.6), Inches(1.45), prs_width - Inches(1.2), Inches(5.3), runs)
    notes(slide, note)
    return slide


prs = Presentation()
prs_width = Inches(13.333)
prs_height = Inches(7.5)
prs.slide_width = prs_width
prs.slide_height = prs_height

# ---------------------------------------------------------------- 1 portada
slide = blank(prs)
bg = slide.shapes.add_shape(1, Inches(0), Inches(0), prs_width, prs_height)
bg.fill.solid()
bg.fill.fore_color.rgb = RGBColor(0x0F, 0x1B, 0x2E)
bg.line.fill.background()
bg.shadow.inherit = False
text(slide, Inches(0.9), Inches(2.1), prs_width - Inches(1.8), Inches(3.0), [
    {"t": "Flujos del Sistema y Casos de Prueba", "size": 40, "bold": True,
     "color": RGBColor(0xFF, 0xFF, 0xFF)},
    {"t": "Ejecutados y validados", "size": 24, "color": RGBColor(0x9E, 0xC5, 0xF0)},
    {"t": "Microservice Code Studio — AgentIA", "size": 16,
     "color": RGBColor(0x94, 0xA3, 0xB8), "space": 18},
    {"t": "Equipo de Aseguramiento de Calidad (QE)  ·  2 de octubre de 2026", "size": 13,
     "color": RGBColor(0x94, 0xA3, 0xB8)},
])
notes(slide, "Abrir con el objeto: documentar los flujos, explicar cómo se probaron y exponer "
             "los casos ejecutados y validados. Una frase: no venimos a decir 'probamos mucho', "
             "venimos a mostrar qué se ejecutó y qué se encontró.")

# ---------------------------------------------------------------- 2 agenda
content_slide(prs, "Agenda", [
    {"t": "1.  Contexto y objetivo", "size": 20},
    {"t": f"2.  Alcance: {FLOW_COUNT} flujos · 62 endpoints REST", "size": 20},
    {"t": "3.  Método QE: cómo se construyó cada prueba", "size": 20},
    {"t": "4.  Tipos de prueba y fronteras sustituidas", "size": 20},
    {"t": "5.  Mapa de flujos y flujos críticos", "size": 20},
    {"t": f"6.  Casos ejecutados y validados: {TOTAL} casos", "size": 20, "bold": True,
     "color": ACCENT},
    {"t": "7.  Defectos encontrados y corregidos", "size": 20},
    {"t": "8.  Limitaciones y próximos pasos", "size": 20},
], "Anunciar la estructura y avisar de que habrá una sección de limitaciones: declarar los "
   "límites por adelantado compra credibilidad para todo lo demás.")

# ---------------------------------------------------------------- 3 objetivo
content_slide(prs, "Contexto y objetivo", [
    {"t": "El sistema genera microservicios Spring Boot 3 de forma autónoma y los verifica "
          "en un sandbox hermético.", "size": 18},
    {"t": "", "size": 8},
    {"t": "El encargo:", "size": 18, "bold": True},
    {"t": "•  Documentar los flujos del sistema, de extremo a extremo.", "size": 17},
    {"t": "•  Explicar cómo se probó cada uno y con qué tipo de prueba.", "size": 17},
    {"t": "•  Exponer los casos ejecutados y validados, con evidencia.", "size": 17},
    {"t": "", "size": 8},
    {"t": "El criterio de calidad aplicado: no basta con que una prueba pase; tiene que poder "
          "fallar, y tiene que estar verificando una afirmación del producto y no un detalle "
          "de la implementación.", "size": 16, "color": MUTED},
], "Explicar que el sistema se prueba a sí mismo, y que por eso el papel del QE aquí es "
   "verificar la verificación. No entrar todavía en el detalle técnico.")

# ---------------------------------------------------------------- 4 alcance
content_slide(prs, "Alcance", [
    {"t": f"{FLOW_COUNT} flujos funcionales", "size": 22, "bold": True, "color": ACCENT},
    {"t": "Desde la autenticación del operador hasta la publicación del microservicio "
          "generado, incluida la interfaz web.", "size": 16},
    {"t": "", "size": 6},
    {"t": "62 endpoints REST", "size": 22, "bold": True, "color": ACCENT},
    {"t": "Repartidos en 13 grupos: sesiones, especificaciones, requisitos, arquitectura, "
          "modelos, pruebas, seguridad, DevOps, orquestador, artefactos, publicación, "
          "autenticación y playground.", "size": 16},
    {"t": "", "size": 6},
    {"t": "Fuera de alcance, declarado", "size": 22, "bold": True, "color": WARN},
    {"t": "Carga y rendimiento · accesibilidad · navegador real · mutación · fuzzing.",
     "size": 16},
], "Decir lo que NO se probó antes de que lo pregunten. Es la diferencia entre un informe y "
   "un anuncio.")

# ---------------------------------------------------------------- 5 método
content_slide(prs, "Método QE: cinco pasos", [
    {"t": "1.  Medir antes de tocar nada", "size": 19, "bold": True},
    {"t": "     Sin línea base no hay mejora demostrable.", "size": 15, "color": MUTED},
    {"t": "2.  Priorizar por riesgo, no por cobertura", "size": 19, "bold": True},
    {"t": "     Primero el módulo cuya decisión duele más si es incorrecta.", "size": 15,
     "color": MUTED},
    {"t": "3.  Enunciar la afirmación del módulo", "size": 19, "bold": True},
    {"t": "     Antes de la prueba, la frase que el módulo promete.", "size": 15, "color": MUTED},
    {"t": "4.  Sustituir la frontera, nunca el sujeto", "size": 19, "bold": True},
    {"t": "     Se falsea Docker, red, hilos, LLM. Jamás lo que se está probando.", "size": 15,
     "color": MUTED},
    {"t": "5.  Ver la prueba fallar", "size": 19, "bold": True},
    {"t": "     Una prueba que nunca se vio en rojo puede estar pasando por la razón "
          "equivocada.", "size": 15, "color": MUTED},
], "El paso 5 es el más importante y el más fácil de saltarse. Contar el caso real: una prueba "
   "propia pasaba mientras cubría una rama distinta de la que su nombre decía, y fue la "
   "cobertura quien lo delató.")

# ---------------------------------------------------------------- 6 tipos
content_slide(prs, "Tipos de prueba aplicados", [
    {"t": "Unitaria  ·  Integración de módulo  ·  Contrato  ·  Extremo a extremo",
     "size": 18, "bold": True},
    {"t": "Regresión  ·  Caracterización  ·  Negativa e inyección de fallo  ·  Hermetismo",
     "size": 18, "bold": True},
    {"t": "", "size": 10},
    {"t": "Fronteras sustituidas, siempre en el mismo punto:", "size": 16, "bold": True},
    {"t": "subprocess → proceso falso      requests → respuesta falsa      "
          "Thread → ejecución en línea", "size": 15, "color": MUTED},
    {"t": "Grafo LangGraph → grafo guionado      Auditoría SAST → auditoría falsa",
     "size": 15, "color": MUTED},
    {"t": "HTTP (frontend) → backend simulado con MSW", "size": 15, "color": MUTED},
    {"t": "", "size": 10},
    {"t": f"{BY_SUITE.get('backend', 0)} casos en backend (pytest)   ·   "
          f"{BY_SUITE.get('frontend', 0)} casos en frontend (Vitest + MSW)", "size": 17,
     "bold": True, "color": ACCENT},
], "Insistir en una idea: ninguna prueba de esta campaña arranca un contenedor, abre un socket "
   "ni llama a un modelo real. Por eso son deterministas y por eso pueden correr en cada "
   "cambio.")

# ---------------------------------------------------------------- 7 mapa de flujos
rows = [{"t": "Mapa de flujos y cobertura", "size": 30, "bold": True, "color": ACCENT}]
slide = blank(prs)
band(slide)
text(slide, Inches(0.6), Inches(0.42), prs_width - Inches(1.2), Inches(0.8), rows)
top = Inches(1.5)
ordered = sorted(FLOWS.items(), key=lambda kv: (kv[0] != "FT", kv[0]))
for index, (code, data) in enumerate(ordered):
    col = index % 2
    row = index // 2
    left = Inches(0.6) + col * Inches(6.3)
    y = top + row * Inches(0.62)
    fail = data.get("FAIL", 0) + data.get("ERROR", 0)
    colour = GOOD if fail == 0 else WARN
    text(slide, left, y, Inches(6.0), Inches(0.55), [
        {"t": f"{code}   {FLOW_TITLES.get(code, data['titulo'])[:34]}", "size": 12},
        {"t": f"        {data['total']} casos   ·   {data.get('PASS', 0)} correctos"
              + (f"   ·   {fail} fallidos" if fail else ""), "size": 10, "color": colour},
    ], spacing=0.9)
notes(slide, "Este es el mapa completo. Cada flujo tiene su ficha en el informe, con propósito, "
             "pasos, artefactos y los casos que lo validan. Los que aparecen en rojo se explican "
             "en la diapositiva de resultados: no se esconden.")

# ---------------------------------------------------------------- 8 flujos críticos
content_slide(prs, "Los dos flujos de mayor riesgo", [
    {"t": "F6 — Sandbox hermético y auto-reparación acotada", "size": 20, "bold": True,
     "color": ACCENT},
    {"t": "Compila y ejecuta sin red, diagnostica y repara hasta 3 veces (Principio V). "
          "El contrato central: una verificación que no se ejecutó NO es una sesión "
          "verificada. Tres estados que nunca se confunden: verificado, verificado con "
          "hallazgos, no evaluable.", "size": 15},
    {"t": "", "size": 10},
    {"t": "F10 — Orquestación Auto-Pilot", "size": 20, "bold": True, "color": ACCENT},
    {"t": "Ejecuta la cadena completa sin intervención, con pausa, reanudación y cancelación. "
          "Es el flujo de mayor riesgo porque nadie lo vigila mientras corre: el único testigo "
          "es el estado que deja y los eventos que emite.", "size": 15},
    {"t": "", "size": 10},
    {"t": "Riesgo compartido: si reportan progreso que no hicieron, el operador toma "
          "decisiones sobre una realidad que no existe.", "size": 15, "bold": True,
     "color": WARN},
], "Aterrizar el riesgo en términos de negocio, no técnicos: un pipeline desatendido que "
   "informa mal es peor que uno que falla, porque nadie lo está mirando.")

# ---------------------------------------------------------------- 9 resultados
slide = blank(prs)
band(slide)
text(slide, Inches(0.6), Inches(0.42), prs_width - Inches(1.2), Inches(0.8),
     [{"t": "Casos ejecutados y validados", "size": 30, "bold": True, "color": ACCENT}])

stats = [
    (f"{TOTAL}", "casos ejecutados", ACCENT),
    (f"{PASS}", "correctos (PASS)", GOOD),
    (f"{FAIL}", "fallidos (FAIL)", WARN if FAIL else GOOD),
    (f"{SKIP}", "omitidos (SKIP)", MUTED),
]
for index, (value, label, colour) in enumerate(stats):
    left = Inches(0.7) + index * Inches(3.05)
    box = slide.shapes.add_shape(1, left, Inches(1.6), Inches(2.8), Inches(1.9))
    box.fill.solid()
    box.fill.fore_color.rgb = LIGHT
    box.line.color.rgb = colour
    box.shadow.inherit = False
    text(slide, left, Inches(1.85), Inches(2.8), Inches(1.5), [
        {"t": value, "size": 44, "bold": True, "color": colour},
        {"t": label, "size": 13, "color": MUTED},
    ], align=PP_ALIGN.CENTER, spacing=0.9)

text(slide, Inches(0.7), Inches(3.85), prs_width - Inches(1.4), Inches(3.0), [
    {"t": "Cómo se valida un caso", "size": 17, "bold": True},
    {"t": "•  Validado = la suite lo reporta como PASS en la ejecución más reciente.",
     "size": 15},
    {"t": "•  Un caso fallido no se oculta: aparece en la matriz con su motivo.",
     "size": 15},
    {"t": "•  Cada caso tiene identificador estable por flujo (F6-014, FT-233).",
     "size": 15},
    {"t": "", "size": 8},
    {"t": "Evidencia: matriz_casos_de_prueba.csv  ·  informes JUnit  ·  salida completa de "
          "ambas suites.", "size": 14, "color": MUTED},
], spacing=1.1)
notes(slide, "Si algún caso aparece en rojo: decirlo aquí, con la causa, antes de que lo "
             "pregunten. Un informe que reconoce sus fallos es creíble; uno que reporta 100 % "
             "siempre, no.")

# ---------------------------------------------------------------- 10 defectos
content_slide(prs, "Nueve defectos encontrados y corregidos", [
    {"t": "Ninguno se descubrió leyendo el código. Todos aparecieron porque una prueba falló, "
          "se colgó, o ejecutó por primera vez una rama nunca ejecutada.", "size": 15,
     "color": MUTED},
    {"t": "", "size": 8},
    {"t": "D-03  Crítica   El espejo de telemetría bloqueaba la ruta crítica y colgaba la suite",
     "size": 15},
    {"t": "D-05  Alta      El respaldo del esquema llamaba a un método inexistente",
     "size": 15},
    {"t": "D-04  Alta      El fallo más ruidoso escapaba del manejador de errores",
     "size": 15},
    {"t": "D-06  Alta      La autenticación de sesión invalidó 154 pruebas de golpe",
     "size": 15},
    {"t": "D-02  Alta      La razón del bloqueo se calculaba y se descartaba", "size": 15},
    {"t": "D-01  Media   Dos funciones definidas dos veces en el mismo archivo", "size": 15},
    {"t": "D-08  Alta      Un refactor revirtió el respaldo del esquema; la importación quedó sin usar", "size": 15},
    {"t": "D-07  Alta      El parámetro force de run_pipeline dejó de respetarse", "size": 15},
    {"t": "D-09  Alta      La suite no era independiente del orden: 52 casos fallaban solo en la ejecución completa", "size": 15},
    {"t": "", "size": 8},
    {"t": "Cada corrección dejó una prueba de regresión que falla si el defecto vuelve.",
     "size": 16, "bold": True, "color": GOOD},
], "No leer los seis. Elegir dos y contarlos como historia: el de la telemetría (D-03) porque "
   "explica por qué la suite no podía ni ejecutarse; y el del esquema (D-05) porque es el más "
   "instructivo: la función estaba probada, pero nadie probaba su uso.")

# ---------------------------------------------------------------- 11 D-06
content_slide(prs, "D-06 — El control de seguridad que rompió 154 pruebas", [
    {"t": "Qué pasó", "size": 18, "bold": True, "color": ACCENT},
    {"t": "Al añadirse la autenticación de sesión, 154 pruebas existentes fallaron a la vez, "
          "todas con 401, ninguna equivocada sobre lo que probaba.", "size": 15},
    {"t": "", "size": 8},
    {"t": "Por qué importa", "size": 18, "bold": True, "color": ACCENT},
    {"t": "Un control de seguridad SIN UNA SOLA PRUEBA PROPIA había cambiado el contrato de "
          "los 62 endpoints. La suite sólo podía reportarlo como un muro de fallos inconexos.",
     "size": 15},
    {"t": "", "size": 8},
    {"t": "Cómo se resolvió", "size": 18, "bold": True, "color": ACCENT},
    {"t": "•  Un cliente de prueba autenticado que entra por el endpoint real: no se desactiva "
          "el control, se ejercita.", "size": 15},
    {"t": "•  27 casos nuevos que prueban el control mismo: guarda, cookie, revocación, "
          "límite de intentos.", "size": 15},
], "Este es el hallazgo más valioso de la campaña. Explica por qué 'añadir una feature' y "
   "'tenerla probada' son dos cosas distintas, y por qué una suite que no se ejecuta deja de "
   "ser una red de seguridad.")

# ---------------------------------------------------------------- 12 cobertura
content_slide(prs, "Cobertura de los módulos priorizados", [
    {"t": "docker_service.py          52,7 %  →  100,0 %", "size": 18},
    {"t": "routes_session.py           71,3 %  →  100,0 %", "size": 18},
    {"t": "lifecycle_service.py        76,4 %  →  100,0 %", "size": 18},
    {"t": "pipeline_runner.py          82,4 %  →  100,0 %", "size": 18},
    {"t": "", "size": 10},
    {"t": "La cobertura mide qué se ejecutó, no qué es verdad.", "size": 18, "bold": True,
     "color": WARN},
    {"t": "El 100 % de líneas significa que cada línea corrió al menos una vez bajo prueba. "
          "No sustituye a la revisión ni demuestra corrección.", "size": 15, "color": MUTED},
], "Anticipar la crítica: alguien dirá 'el 100 % no significa nada'. Tener razón antes que "
   "ellos, y explicar que la cobertura se usó como detector de pruebas malas, no como meta.")

# ---------------------------------------------------------------- 13 limitaciones
content_slide(prs, "Limitaciones", [
    {"t": "1.  La verificación del código generado es autorreferencial.", "size": 18,
     "bold": True, "color": WARN},
    {"t": "      La plataforma escribe las pruebas Mockito y luego las ejecuta. Un build en "
          "verde demuestra que el código cumple SUS pruebas, no los escenarios del blueprint.",
     "size": 15},
    {"t": "2.  No hay navegador real.", "size": 18, "bold": True, "color": WARN},
    {"t": "      Los flujos de interfaz corren en jsdom contra un backend simulado.", "size": 15},
    {"t": "3.  La concurrencia no se prueba: se elimina.", "size": 18, "bold": True,
     "color": WARN},
    {"t": "      Por determinismo; las condiciones de carrera quedan sin cubrir.", "size": 15},
    {"t": "4.  Quedan módulos por debajo del 90 %.", "size": 18, "bold": True, "color": WARN},
    {"t": "      architecture_service y requirements_service: escriben archivos que nadie "
          "comprueba hasta el final.", "size": 15},
], "No saltarse esta diapositiva. Un informe de calidad sin limitaciones es un informe "
   "incompleto, y la limitación 1 es la más importante de todo el documento.")

# ---------------------------------------------------------------- 14 cierre
content_slide(prs, "Conclusiones y próximos pasos", [
    {"t": "Conclusiones", "size": 20, "bold": True, "color": ACCENT},
    {"t": f"•  {TOTAL} casos ejecutados, con resultado verificable caso por caso.",
     "size": 16},
    {"t": f"•  {FLOW_COUNT} flujos documentados de extremo a extremo.", "size": 16},
    {"t": "•  6 defectos reales encontrados y corregidos, con prueba de regresión.",
     "size": 16},
    {"t": "", "size": 10},
    {"t": "Próximos pasos, por orden de valor", "size": 20, "bold": True, "color": ACCENT},
    {"t": "1.  Pruebas de aceptación HTTP independientes contra el microservicio desplegado: "
          "cierran la brecha autorreferencial.", "size": 16},
    {"t": "2.  Subir architecture_service y requirements_service por encima del 90 %.",
     "size": 16},
    {"t": "3.  Pruebas de navegador real (Playwright) sobre los flujos de usuario.",
     "size": 16},
], "Cerrar con una decisión, no con un resumen: pedir priorización del punto 1, que es el de "
   "mayor valor y el único que cierra la limitación principal.")

# ---------------------------------------------------------------- 15 anexo
content_slide(prs, "Anexo — Reproducción y evidencias", [
    {"t": "Ejecutar el backend", "size": 16, "bold": True},
    {"t": ".venv/bin/python -m pytest -q --cov=backend/app --cov-report=term-missing",
     "size": 13, "color": MUTED},
    {"t": "Ejecutar el frontend", "size": 16, "bold": True},
    {"t": "cd frontend && npm test", "size": 13, "color": MUTED},
    {"t": "Regenerar la matriz y las tablas del informe", "size": 16, "bold": True},
    {"t": ".venv/bin/python docs/entrega_qe/build_matriz.py", "size": 13, "color": MUTED},
    {"t": "", "size": 8},
    {"t": "Paquete de entrega: informe PDF · matriz CSV · anexo de snippets · esta "
          "presentación · evidencia cruda en reports/qe/entrega/", "size": 15},
], "Dejar esta diapositiva como respaldo: si alguien duda de una cifra, se puede reproducir en "
   "vivo con estos tres comandos.")

out = OUT / "plantilla_presentacion.pptx"
prs.save(out)
print(f"escrito {out}  ({len(prs.slides.__iter__.__self__._sldIdLst)} diapositivas)")
