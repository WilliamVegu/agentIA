import pptx
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
import os
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

TEMPLATE_PATH = r"C:\Users\willi\Downloads\PPT_EJEMPL.pptx"
OUT_PATH_DOWNLOADS = r"C:\Users\willi\Downloads\Microservice_Code_Studio_Presentacion.pptx"
OUT_PATH_LOCAL = r"c:\Users\willi\Downloads\agentIA\Microservice_Code_Studio_Presentacion.pptx"

IMG_STUDIO = r"c:\Users\willi\Downloads\agentIA\assets_ppt\slide5_studio.png"
IMG_SECURITY = r"c:\Users\willi\Downloads\agentIA\assets_ppt\slide5_security.png"

prs = pptx.Presentation(TEMPLATE_PATH)

def set_p_text(p, text, font_name="Century Gothic", size=None, bold=None, color=None, align=None):
    if p.runs:
        r = p.runs[0]
        r.text = text
        for extra in p.runs[1:]:
            extra.text = ""
    else:
        r = p.add_run()
        r.text = text
        
    if font_name:
        r.font.name = font_name
    if size is not None:
        r.font.size = Pt(size)
    if bold is not None:
        r.font.bold = bold
    if color:
        r.font.color.rgb = RGBColor.from_string(color)
    if align is not None:
        p.alignment = align

def clean_paragraph_indent(p):
    pPr = p._p.get_or_add_pPr()
    for attr in ["marL", "indent", "lvl"]:
        if attr in pPr.attrib:
            del pPr.attrib[attr]
    for child in list(pPr):
        if "bu" in child.tag:
            pPr.remove(child)
    buNone = OxmlElement("a:buNone")
    pPr.append(buNone)

def update_shape_paragraphs(shape, items):
    tf = shape.text_frame
    for i, item in enumerate(items):
        if i < len(tf.paragraphs):
            p = tf.paragraphs[i]
        else:
            p = tf.add_paragraph()
        set_p_text(
            p,
            text=item.get("text", ""),
            font_name=item.get("font", "Century Gothic"),
            size=item.get("size", None),
            bold=item.get("bold", None),
            color=item.get("color", None),
            align=item.get("align", None)
        )
    for extra_p in tf.paragraphs[len(items):]:
        extra_p.text = ""

def find_shape(slide, name, shape_id=None, min_left=None):
    for s in slide.shapes:
        if shape_id is not None and s.shape_id == shape_id:
            return s
        if min_left is not None and s.name == name and s.left / 914400 >= min_left:
            return s
        if shape_id is None and min_left is None and s.name == name:
            return s
    return None

# =========================================================================
# SLIDE 1: PORTADA
# =========================================================================
s1 = prs.slides[0]

sh = find_shape(s1, "Text 3")
if sh:
    update_shape_paragraphs(sh, [{"text": "AI LAB PERÚ · TATA CONSULTANCY SERVICES", "size": 10.3, "bold": True, "color": "00D7FF"}])

sh = find_shape(s1, "Text 4")
if sh:
    sh.width = Inches(7.5)
    update_shape_paragraphs(sh, [
        {"text": "Microservice Code Studio", "size": 40.0, "bold": True, "color": "F7FAFC"},
        {"text": "Arquitectura & Java 21 Autónomo", "size": 32.0, "bold": True, "color": "F7FAFC"}
    ])

sh = find_shape(s1, "Text 5")
if sh:
    update_shape_paragraphs(sh, [{"text": "De especificaciones formales BDD a microservicios Java 21 / Spring Boot 3 con sandbox hermético, auto-reparación y control de calidad.", "size": 14.5, "color": "F7FAFC"}])

sh = find_shape(s1, "Text 16")
if sh:
    update_shape_paragraphs(sh, [{"text": "RETO TÉCNICO", "size": 10.0, "bold": True, "color": "FF8A3D"}])

sh = find_shape(s1, "Text 17")
if sh:
    update_shape_paragraphs(sh, [{"text": "Negocio + IA + Evidencia", "size": 22.0, "bold": True, "color": "F7FAFC"}])

sh = find_shape(s1, "Text 20")
if sh: update_shape_paragraphs(sh, [{"text": "Ingestar", "size": 6.8, "color": "AEB8C7"}])

sh = find_shape(s1, "Text 23")
if sh: update_shape_paragraphs(sh, [{"text": "Diseñar", "size": 6.8, "color": "AEB8C7"}])

sh = find_shape(s1, "Text 26")
if sh: update_shape_paragraphs(sh, [{"text": "Verificar", "size": 6.8, "color": "AEB8C7"}])

sh = find_shape(s1, "Text 28")
if sh: update_shape_paragraphs(sh, [{"text": "Publicar", "size": 6.8, "color": "AEB8C7"}])

sh = find_shape(s1, "Text 29")
if sh:
    update_shape_paragraphs(sh, [{"text": "La propuesta no busca solo 'escribir código'. Construye microservicios Java 21 herméticamente probados, alineados a la Constitución y listos para producción.", "size": 11.2, "color": "F7FAFC"}])

sh = find_shape(s1, "Text 31")
if sh:
    update_shape_paragraphs(sh, [{"text": "AI Lab Perú · TCS Microservice Code Studio", "size": 8.5, "color": "AEB8C7"}])

# =========================================================================
# SLIDE 2: DOLOR Y OPORTUNIDAD
# =========================================================================
s2 = prs.slides[1]

sh = find_shape(s2, "Text 4")
if sh:
    update_shape_paragraphs(sh, [{"text": "Dolor y oportunidad", "size": 32.0, "bold": True, "color": "F7FAFC"}])

sh = find_shape(s2, "Text 10")
if sh:
    update_shape_paragraphs(sh, [{"text": "Desarrollo manual repetitivo (días por servicio): Escribir boilerplate de controladores, servicios, repositorios, entidades JPA y DTOs consume 70% del tiempo de sprint.", "size": 10.2, "bold": True, "color": "00D7FF"}])

sh = find_shape(s2, "Text 15")
if sh:
    update_shape_paragraphs(sh, [{"text": "Código alucinado y sin verificación real: LLMs convencionales generan dependencias incompatibles, fallos de tipado y código que no compila sin un entorno de pruebas hermético.", "size": 10.2, "bold": True, "color": "34D399"}])

sh = find_shape(s2, "Text 20")
if sh:
    update_shape_paragraphs(sh, [{"text": "Brecha entre requerimientos BDD y código Java: Desconexión entre criterios Given/When/Then, contratos REST OpenAPI, esquemas SQL y pruebas unitarias Mockito.", "size": 10.2, "bold": True, "color": "9B5CFF"}])

sh = find_shape(s2, "Text 25")
if sh:
    update_shape_paragraphs(sh, [{"text": "Ausencia de gobierno, SAST y despliegue: Riesgo de secretos persistidos en disco/BD, sin compuertas de calidad (Quality Gate) ni contenedores Docker/K8s listos para producción.", "size": 10.2, "bold": True, "color": "FF8A3D"}])

sh = find_shape(s2, "Text 27")
if sh:
    update_shape_paragraphs(sh, [{"text": "Tesis para el jurado: No generamos código por generar; construimos un estudio autónomo con Spec-Driven Development (SDD), compilación hermética (--network none) y auto-reparación acotada para garantizar microservicios Java 21 certificados.", "size": 10.8, "color": "F7FAFC"}])

sh = find_shape(s2, "Text 28")
if sh:
    update_shape_paragraphs(sh, [{"text": "AI Lab Perú · TCS Microservice Code Studio", "size": 8.5, "color": "AEB8C7"}])

# =========================================================================
# SLIDE 3: MÉTODO DE TRABAJO
# =========================================================================
s3 = prs.slides[2]

sh = find_shape(s3, "Text 3"); sh and update_shape_paragraphs(sh, [{"text": "MÉTODO DE TRABAJO", "size": 10.5, "bold": True, "color": "00D7FF"}])
sh = find_shape(s3, "Text 4"); sh and update_shape_paragraphs(sh, [{"text": "De la idea al impacto", "size": 29.0, "bold": True, "color": "F7FAFC"}])
sh = find_shape(s3, "Text 5"); sh and update_shape_paragraphs(sh, [{"text": "Mantenemos el esquema del reto: cuatro fases centradas en valor, usuario y evidencia.", "size": 12.2, "color": "AEB8C7"}])

# Phase 1: DISCOVERY
sh = find_shape(s3, "Text 7");  sh and update_shape_paragraphs(sh, [{"text": "1", "size": 18.0, "bold": True, "color": "2F80FF"}])
sh = find_shape(s3, "Text 8");  sh and update_shape_paragraphs(sh, [{"text": "DISCOVERY", "size": 9.6, "bold": True, "color": "2F80FF"}])
sh = find_shape(s3, "Text 10"); sh and update_shape_paragraphs(sh, [{"text": "Entender el problema", "size": 14.1, "bold": True, "color": "F7FAFC"}])
sh = find_shape(s3, "Text 11"); sh and update_shape_paragraphs(sh, [{"text": "Levantamiento de fricciones en ingeniería de microservicios, definición de historias BDD Given/When/Then y catálogo de requerimientos formales.", "size": 9.5, "color": "AEB8C7"}])
sh = find_shape(s3, "Text 12"); sh and update_shape_paragraphs(sh, [{"text": "Entregables: spec.md (Spec Kit), matriz de requerimientos funcionales/no funcionales y criterios de aceptación tipados.", "size": 9.0, "color": "F7FAFC"}])

# Phase 2: IDEACIÓN
sh = find_shape(s3, "Text 15"); sh and update_shape_paragraphs(sh, [{"text": "2", "size": 18.0, "bold": True, "color": "34D399"}])
sh = find_shape(s3, "Text 16"); sh and update_shape_paragraphs(sh, [{"text": "IDEACIÓN", "size": 9.6, "bold": True, "color": "34D399"}])
sh = find_shape(s3, "Text 18"); sh and update_shape_paragraphs(sh, [{"text": "Diseñar la solución", "size": 14.1, "bold": True, "color": "F7FAFC"}])
sh = find_shape(s3, "Text 19"); sh and update_shape_paragraphs(sh, [{"text": "Arquitectura en 4 capas estrictas (Controller ➔ Service ➔ Repository ➔ Model), contratos REST con Java Records inmutables y esquema relacional JPA.", "size": 9.5, "color": "AEB8C7"}])
sh = find_shape(s3, "Text 20"); sh and update_shape_paragraphs(sh, [{"text": "Entregables: plan.md, data-model.md, diagramas Mermaid (arquitectura y ERD) y especificación OpenAPI.", "size": 9.0, "color": "F7FAFC"}])

# Phase 3: BUILDING
sh = find_shape(s3, "Text 23"); sh and update_shape_paragraphs(sh, [{"text": "3", "size": 18.0, "bold": True, "color": "9B5CFF"}])
sh = find_shape(s3, "Text 24"); sh and update_shape_paragraphs(sh, [{"text": "BUILDING", "size": 9.6, "bold": True, "color": "9B5CFF"}])
sh = find_shape(s3, "Text 26"); sh and update_shape_paragraphs(sh, [{"text": "Construir con IA", "size": 14.1, "bold": True, "color": "F7FAFC"}])
sh = find_shape(s3, "Text 27"); sh and update_shape_paragraphs(sh, [{"text": "Orquestación LangGraph, backend FastAPI, sandbox Docker hermético (mvn test -o), motor de auto-reparación (máx. 3 intentos) y UI Streamlit.", "size": 9.5, "color": "AEB8C7"}])
sh = find_shape(s3, "Text 28"); sh and update_shape_paragraphs(sh, [{"text": "Entregables: Microservice Studio funcional, 125 pruebas automatizadas al 100%, streaming SSE y auto-remediación SAST.", "size": 9.0, "color": "F7FAFC"}])

# Phase 4: DEMO
sh = find_shape(s3, "Text 31"); sh and update_shape_paragraphs(sh, [{"text": "4", "size": 18.0, "bold": True, "color": "FF8A3D"}])
sh = find_shape(s3, "Text 32"); sh and update_shape_paragraphs(sh, [{"text": "DEMO", "size": 9.6, "bold": True, "color": "FF8A3D"}])
sh = find_shape(s3, "Text 34"); sh and update_shape_paragraphs(sh, [{"text": "Mostrar y aprender", "size": 14.1, "bold": True, "color": "F7FAFC"}])
sh = find_shape(s3, "Text 35"); sh and update_shape_paragraphs(sh, [{"text": "Flujo E2E Auto-Pilot: desde prompt/spec.md hasta microservicio Java 21 compilado, verificado en sandbox, auditado en Quality Gate y exportado en ZIP/Git.", "size": 9.5, "color": "AEB8C7"}])
sh = find_shape(s3, "Text 36"); sh and update_shape_paragraphs(sh, [{"text": "Entregables: Web Studio con 10 pestañas en vivo, suite de 125 tests verdes, pipeline Auto-Pilot y manifiestos DevOps (K8s/CI-CD).", "size": 9.0, "color": "F7FAFC"}])

# Bottom principles
sh = find_shape(s3, "Text 37"); sh and update_shape_paragraphs(sh, [{"text": "Principios que elevaron la calidad", "size": 12.5, "bold": True, "color": "F7FAFC"}])
sh = find_shape(s3, "Text 38"); sh and update_shape_paragraphs(sh, [{"text": "Usuario", "size": 9.3, "bold": True, "color": "00D7FF"}])
sh = find_shape(s3, "Text 40"); sh and update_shape_paragraphs(sh, [{"text": "Datos", "size": 9.3, "bold": True, "color": "34D399"}])
sh = find_shape(s3, "Text 42"); sh and update_shape_paragraphs(sh, [{"text": "IA responsable", "size": 9.3, "bold": True, "color": "9B5CFF"}])
sh = find_shape(s3, "Text 44"); sh and update_shape_paragraphs(sh, [{"text": "Evidencia", "size": 9.3, "bold": True, "color": "FF8A3D"}])

sh = find_shape(s3, "Text 46"); sh and update_shape_paragraphs(sh, [{"text": "AI Lab Perú · TCS Microservice Code Studio", "size": 8.5, "color": "AEB8C7"}])

# =========================================================================
# SLIDE 4: CONSTRUCCIÓN DE LA SOLUCIÓN
# =========================================================================
s4 = prs.slides[3]

sh = find_shape(s4, "Text 3"); sh and update_shape_paragraphs(sh, [{"text": "CONSTRUCCIÓN DE LA SOLUCIÓN", "size": 10.5, "bold": True, "color": "00D7FF"}])
sh = find_shape(s4, "Text 4"); sh and update_shape_paragraphs(sh, [{"text": "IA guiada por especificaciones", "size": 29.0, "bold": True, "color": "F7FAFC"}])
sh = find_shape(s4, "Text 5"); sh and update_shape_paragraphs(sh, [{"text": "El valor no vino de una sola herramienta: vino de orquestar personas, specs, modelos y validación hermética.", "size": 12.2, "color": "AEB8C7"}])

# Left card - Spec Driven Development
sh = find_shape(s4, "Text 7"); sh and update_shape_paragraphs(sh, [{"text": "Spec Driven Development", "size": 16.0, "bold": True, "color": "F7FAFC"}])
sh = find_shape(s4, "Text 8"); sh and update_shape_paragraphs(sh, [{"text": "•", "size": 12.5, "bold": True, "color": "00D7FF"}])
sh = find_shape(s4, "Text 9", min_left=1.0); sh and update_shape_paragraphs(sh, [{"text": "Specify / Spec Kit: Formalización de la Constitución v1.1.0, historias de usuario BDD y especificaciones ejecutables (spec.md, plan.md, tasks.md).", "size": 9.8, "color": "F7FAFC"}])
sh = find_shape(s4, "Text 10"); sh and update_shape_paragraphs(sh, [{"text": "•", "size": 12.5, "bold": True, "color": "34D399"}])
sh = find_shape(s4, "Text 11"); sh and update_shape_paragraphs(sh, [{"text": "LangGraph Orchestration: Grafo de estados con nodos especializados (Scaffolding, Modelos JPA, DTOs Records, Servicios, Controllers y Tests Mockito).", "size": 9.8, "color": "F7FAFC"}])
sh = find_shape(s4, "Text 12"); sh and update_shape_paragraphs(sh, [{"text": "•", "size": 12.5, "bold": True, "color": "FF8A3D"}])
sh = find_shape(s4, "Text 13"); sh and update_shape_paragraphs(sh, [{"text": "Hermetic Docker Sandbox: Aislamiento estricto con --network none y compilación offline (mvn test -o) contra repositorio Maven local de solo lectura.", "size": 9.8, "color": "F7FAFC"}])
sh = find_shape(s4, "Text 14"); sh and update_shape_paragraphs(sh, [{"text": "•", "size": 12.5, "bold": True, "color": "9B5CFF"}])
sh = find_shape(s4, "Text 15"); sh and update_shape_paragraphs(sh, [{"text": "Self-Repair & Pytest Suite: Máquina de auto-reparación acotada (máx 3 intentos) + suite de 125 tests automatizados pasando al 100%.", "size": 9.8, "color": "F7FAFC"}])

sh = find_shape(s4, "Text 16"); sh and update_shape_paragraphs(sh, [{"text": "Modelo y runtime usados", "size": 11.2, "bold": True, "color": "00D7FF"}])
sh = find_shape(s4, "Text 17"); sh and update_shape_paragraphs(sh, [{"text": "Google Gemini 2.5 Flash / Groq · Python 3.12 · FastAPI · LangGraph · Streamlit · Docker · Java 21 LTS · Spring Boot 3.2 · Maven · PostgreSQL / SQLite", "size": 9.0, "color": "AEB8C7"}])

# Right card - Header: Microservice Code Studio
# Reposition cleanly so there is NO overlap with the body text
sh_title = find_shape(s4, "Text 19")
if sh_title:
    sh_title.left = Inches(6.85)
    sh_title.top = Inches(2.20)
    sh_title.width = Inches(4.25)
    sh_title.height = Inches(0.35)
    update_shape_paragraphs(sh_title, [{"text": "Microservice Code Studio", "size": 15.5, "bold": True, "color": "F7FAFC"}])

right_box = find_shape(s4, "Text 9", shape_id=54)
if not right_box:
    right_box = find_shape(s4, "Text 9", min_left=6.0)

if right_box:
    right_box.left = Inches(6.85)
    right_box.top = Inches(2.62)
    right_box.width = Inches(4.20)
    right_box.height = Inches(3.45)
    tf = right_box.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.0)
    tf.margin_right = Inches(0.0)
    tf.margin_top = Inches(0.0)
    tf.margin_bottom = Inches(0.0)
    tf.vertical_anchor = MSO_ANCHOR.TOP
    
    bodyPr = right_box.text_frame._bodyPr
    for child in list(bodyPr):
        if "Autofit" in child.tag or "autofit" in child.tag.lower():
            bodyPr.remove(child)
    noAutofit = OxmlElement("a:noAutofit")
    bodyPr.append(noAutofit)
    bodyPr.set("anchor", "t")

    feature_items = [
        ("• Inicio Rápido & Auto-Pilot: ", "Síntesis autónoma 1-Click o modo asistido con controles hot-pause, resume y cancel en caliente."),
        ("• Ingesta Dual BDD (Spec Kit): ", "Carga de spec.md o JSON blueprint con validación formal de criterios Given/When/Then."),
        ("• Arquitectura 4 Capas & JPA: ", "Topología limpia (Controller➔Service➔Repo➔Model), DTOs Java Records inmutables y scripts SQL sincronizados."),
        ("• Sandbox Hermético Offline: ", "Compilación y pruebas Mockito con --network none contra caché .m2 de solo lectura inmutable."),
        ("• Auto-Reparación Acotada (3x): ", "Diagnóstico automático de trazas Maven con auto-parcheo de código antes de escalar a HITL."),
        ("• Quality Gate SAST & DevOps: ", "Cero secretos persistidos, reporte estático 100/100, Dockerfile multi-stage, Compose y K8s.")
    ]
    
    while len(tf.paragraphs) > len(feature_items):
        p_extra = tf.paragraphs[-1]
        p_extra._p.getparent().remove(p_extra._p)
        
    for i, (title_text, desc_text) in enumerate(feature_items):
        if i < len(tf.paragraphs):
            p = tf.paragraphs[i]
        else:
            p = tf.add_paragraph()
        clean_paragraph_indent(p)
        p.space_before = Pt(5)
        p.space_after = Pt(2)
        
        # Clear existing runs
        for r in p.runs:
            r.text = ""
            
        # Run 1: Bold title
        r1 = p.add_run() if not p.runs else p.runs[0]
        r1.text = title_text
        r1.font.name = "Century Gothic"
        r1.font.size = Pt(10.0)
        r1.font.bold = True
        r1.font.color.rgb = RGBColor.from_string("F7FAFC")
        
        # Run 2: Description
        r2 = p.add_run()
        r2.text = desc_text
        r2.font.name = "Century Gothic"
        r2.font.size = Pt(9.5)
        r2.font.bold = False
        r2.font.color.rgb = RGBColor.from_string("D1D5DB")

# Update 4 badges on the right with clean typography and vertical centering
badge_configs = {
    "Grupo 40": ("Text 21", "Ingesta BDD &\nAuto-Pilot"),
    "Grupo 37": ("Text 24", "Sandbox Docker\nHermético"),
    "Grupo 39": ("Text 27", "Auto-Reparación\nAcotada (3x)"),
    "Grupo 38": ("Text 30", "Quality Gate &\nDevOps K8s")
}

for s in s4.shapes:
    if s.name in badge_configs:
        target_sub, target_text = badge_configs[s.name]
        for sub in s.shapes:
            if sub.has_text_frame and sub.name == target_sub:
                sub.text_frame.word_wrap = True
                sub.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                update_shape_paragraphs(sub, [{
                    "text": target_text,
                    "size": 8.0,
                    "bold": True,
                    "color": "F7FAFC",
                    "align": PP_ALIGN.CENTER
                }])

sh = find_shape(s4, "Text 32"); sh and update_shape_paragraphs(sh, [{"text": "AI Lab Perú · TCS Microservice Code Studio", "size": 8.5, "color": "AEB8C7"}])

# =========================================================================
# SLIDE 5: CIERRE GANADOR
# =========================================================================
s5 = prs.slides[4]

sh = find_shape(s5, "Text 3"); sh and update_shape_paragraphs(sh, [{"text": "CIERRE GANADOR", "size": 10.5, "bold": True, "color": "00D7FF"}])
sh = find_shape(s5, "Text 4"); sh and update_shape_paragraphs(sh, [{"text": "Evidencia, impacto y escalabilidad", "size": 29.0, "bold": True, "color": "F7FAFC"}])
sh = find_shape(s5, "Text 5"); sh and update_shape_paragraphs(sh, [{"text": "Una solución técnica real convertida en activo estratégico para la aceleración del ciclo de software.", "size": 12.2, "color": "AEB8C7"}])

# Replace images with authentic high-res project UI captures
for s in s5.shapes:
    if s.name == "Imagen 36" and os.path.exists(IMG_STUDIO):
        rId = s._element.xpath('.//a:blip')[0].attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed']
        img_part = s5.part.related_part(rId)
        with open(IMG_STUDIO, "rb") as f_img:
            img_part._blob = f_img.read()
    elif s.name == "Imagen 40" and os.path.exists(IMG_SECURITY):
        rId = s._element.xpath('.//a:blip')[0].attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed']
        img_part = s5.part.related_part(rId)
        with open(IMG_SECURITY, "rb") as f_img:
            img_part._blob = f_img.read()

sh = find_shape(s5, "Text 17"); sh and update_shape_paragraphs(sh, [{"text": "Highlights", "size": 18.0, "bold": True, "color": "F7FAFC"}])

# Highlights 3 cards
sh = find_shape(s5, "Text 19"); sh and update_shape_paragraphs(sh, [{"text": "Impacto de negocio", "size": 13.0, "bold": True, "color": "00D7FF"}])
sh = find_shape(s5, "Text 20"); sh and update_shape_paragraphs(sh, [{"text": "Reduce el tiempo de creación de microservicios de semanas a menos de 2 minutos, elimina el 100% de errores de boilerplate y estandariza arquitectura Java 21 sin deuda técnica.", "size": 9.3, "color": "F7FAFC"}])

sh = find_shape(s5, "Text 22"); sh and update_shape_paragraphs(sh, [{"text": "Solidez técnica", "size": 13.0, "bold": True, "color": "9B5CFF"}])
sh = find_shape(s5, "Text 23"); sh and update_shape_paragraphs(sh, [{"text": "No es un generador alucinado: cuenta con sandbox Docker hermético (--network none), 125 tests automatizados al 100%, compilación Maven real y auto-reparación acotada.", "size": 9.3, "color": "F7FAFC"}])

sh = find_shape(s5, "Text 25"); sh and update_shape_paragraphs(sh, [{"text": "Escala responsable", "size": 13.0, "bold": True, "color": "34D399"}])
sh = find_shape(s5, "Text 26"); sh and update_shape_paragraphs(sh, [{"text": "Cumplimiento de la Constitución v1.1.0: cero secretos persistidos, compuertas de calidad (Quality Gate), auditoría SAST con auto-parcheo y control humano innegociable (HITL).", "size": 9.3, "color": "F7FAFC"}])

sh = find_shape(s5, "Text 28"); sh and update_shape_paragraphs(sh, [{"text": "Siguiente paso ejecutivo: Desplegar piloto en equipos de desarrollo corporativo, integrar con el catálogo central de APIs y habilitar plantillas de microservicios cloud-native.", "size": 10.5, "bold": True, "color": "F7FAFC"}])

sh = find_shape(s5, "Text 29"); sh and update_shape_paragraphs(sh, [{"text": "AI Lab Perú · TCS Microservice Code Studio", "size": 8.5, "color": "AEB8C7"}])

prs.save(OUT_PATH_DOWNLOADS)
prs.save(OUT_PATH_LOCAL)
print("=================================================================")
print("Presentación generada con éxito en:")
print(f"  -> {OUT_PATH_DOWNLOADS}")
print(f"  -> {OUT_PATH_LOCAL}")
print("=================================================================")
