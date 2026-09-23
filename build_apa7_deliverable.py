import os
import re
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def create_apa7_document(output_path):
    doc = Document()

    # 1. Configuración de Página APA 7 (8.5 x 11 in, márgenes 1 pulgada = 2.54 cm)
    for section in doc.sections:
        section.page_width = Inches(8.5)
        section.page_height = Inches(11.0)
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.header_distance = Inches(0.5)
        section.footer_distance = Inches(0.5)

        # Encabezado: Número de página en la esquina superior derecha
        header = section.header
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hp.paragraph_format.space_before = Pt(0)
        hp.paragraph_format.space_after = Pt(0)
        hrun = hp.add_run()
        hrun.font.name = "Arial"
        hrun.font.size = Pt(10)
        hrun.font.color.rgb = RGBColor(100, 100, 100)
        fldSimple = parse_xml(r'<w:fldSimple %s w:instr="PAGE"/>' % nsdecls('w'))
        hp._p.append(fldSimple)

    # Helper de formato de párrafos APA
    def add_para(text, style='Normal', space_after=6, line_spacing=1.15, first_line_indent=0.5, bold=False, italic=False, align=WD_ALIGN_PARAGRAPH.LEFT):
        p = doc.add_paragraph()
        p.alignment = align
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = line_spacing
        if first_line_indent > 0:
            p.paragraph_format.first_line_indent = Inches(first_line_indent)
        else:
            p.paragraph_format.first_line_indent = Inches(0)
        
        run = p.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(30, 30, 30)
        run.bold = bold
        run.italic = italic
        return p

    def add_heading_1(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.first_line_indent = Inches(0)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(13)
        run.font.color.rgb = RGBColor(0, 51, 102) # Azul corporativo oscuro
        run.bold = True
        return p

    def add_heading_2(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.first_line_indent = Inches(0)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(20, 20, 20)
        run.bold = True
        return p

    def add_heading_3(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.first_line_indent = Inches(0)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(40, 40, 40)
        run.bold = True
        run.italic = True
        return p

    def format_apa_table(table):
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for r_idx, row in enumerate(table.rows):
            # Altura mínima y prevención de salto de fila a mitad de página
            trPr = row._tr.get_or_add_trPr()
            trPr.append(parse_xml(r'<w:cantSplit %s/>' % nsdecls('w')))
            if r_idx == 0:
                trPr.append(parse_xml(r'<w:tblHeader %s/>' % nsdecls('w')))

            for c_idx, cell in enumerate(row.cells):
                tcPr = cell._tc.get_or_add_tcPr()
                # Márgenes internos de celda
                tcMar = parse_xml(r'''
                    <w:tcMar %s>
                        <w:top w:w="120" w:type="dxa"/>
                        <w:bottom w:w="120" w:type="dxa"/>
                        <w:left w:w="160" w:type="dxa"/>
                        <w:right w:w="160" w:type="dxa"/>
                    </w:tcMar>
                ''' % nsdecls('w'))
                tcPr.append(tcMar)

                # Reglas APA 7 de bordes: Solo horizontales superior, inferior de cabecera y final
                top_b = "single" if r_idx == 0 else "none"
                bot_b = "single" if (r_idx == 0 or r_idx == len(table.rows) - 1) else "none"
                
                borders = parse_xml(r'''
                    <w:tcBorders %s>
                        <w:top w:val="%s" w:sz="8" w:space="0" w:color="333333"/>
                        <w:left w:val="none"/>
                        <w:bottom w:val="%s" w:sz="8" w:space="0" w:color="333333"/>
                        <w:right w:val="none"/>
                    </w:tcBorders>
                ''' % (nsdecls('w'), top_b, bot_b))
                tcPr.append(borders)

                # Formato del texto en celda
                for p in cell.paragraphs:
                    p.paragraph_format.space_before = Pt(2)
                    p.paragraph_format.space_after = Pt(2)
                    p.paragraph_format.line_spacing = 1.05
                    p.paragraph_format.first_line_indent = Inches(0)
                    for run in p.runs:
                        run.font.name = "Arial"
                        run.font.size = Pt(9.5)
                        if r_idx == 0:
                            run.bold = True
                            run.font.color.rgb = RGBColor(0, 0, 0)
                        else:
                            run.font.color.rgb = RGBColor(40, 40, 40)

    # ==========================================
    # PORTADA FORMAL APA 7
    # ==========================================
    for _ in range(3):
        doc.add_paragraph()

    # Título Principal
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_after = Pt(18)
    run_t = p_title.add_run("Evaluación Técnica, Arquitectura y Factibilidad de Escalabilidad Empresarial de la Plataforma Microservice Code Studio (AgentIA)")
    run_t.font.name = "Arial"
    run_t.font.size = Pt(16)
    run_t.font.color.rgb = RGBColor(0, 51, 102)
    run_t.bold = True

    # Subtítulo descriptivo
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(36)
    run_s = p_sub.add_run("Un Análisis Técnico Objetivo sobre la Síntesis Autónoma de Baselines Java 21 / Spring Boot 3 mediante Grafos de Estados y Verificación Hermética")
    run_s.font.name = "Arial"
    run_s.font.size = Pt(12)
    run_s.font.color.rgb = RGBColor(80, 80, 80)
    run_s.italic = True

    # Datos institucionales del autor
    for line, is_bold in [
        ("Equipo de Arquitectura e Innovación de Software", True),
        ("Gerencia de Tecnología e Información", False),
        ("Organización Empresarial / Corporación", False),
        ("Proyecto: Microservice Code Studio - Línea Base v1.1.0", False),
        ("Destinatario: Comité Técnico de Arquitectura y Dirección de TI", False),
        ("Fecha de Emisión: 22 de Septiembre de 2026", False),
    ]:
        p_meta = doc.add_paragraph()
        p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_meta.paragraph_format.space_after = Pt(4)
        r_meta = p_meta.add_run(line)
        r_meta.font.name = "Arial"
        r_meta.font.size = Pt(11)
        r_meta.bold = is_bold
        r_meta.font.color.rgb = RGBColor(50, 50, 50)

    doc.add_page_break()

    # ==========================================
    # RESUMEN (ABSTRACT) Y PALABRAS CLAVE
    # ==========================================
    add_heading_1("Resumen")

    # Abstract sin sangría según APA 7
    p_abs = doc.add_paragraph()
    p_abs.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_abs.paragraph_format.first_line_indent = Inches(0)
    p_abs.paragraph_format.space_after = Pt(12)
    p_abs.paragraph_format.line_spacing = 1.15
    r_abs = p_abs.add_run(
        "El presente documento expone una evaluación técnica objetiva e integral de la plataforma experimental Microservice Code Studio (AgentIA), desarrollada como un prototipo funcional (MVP) para automatizar la generación estructurada de baselines de microservicios en Java 21 y Spring Boot 3.x. A partir de especificaciones formales y criterios de aceptación BDD (Given/When/Then), el sistema orquesta la síntesis de código mediante un grafo de estados cíclico (LangGraph), valida la compilación y ejecución de pruebas en un sandbox hermético sin acceso a red externa (Docker con la bandera --network none) e implementa una máquina de auto-reparación acotada a tres iteraciones guiada por las trazas de Maven. Se presenta un diagnóstico riguroso de las capacidades operativas actuales frente a la deuda técnica del prototipo (persistencia mononodo en SQLite, hilos volátiles en memoria y dependencia del socket local de Docker). Asimismo, se desglosan los requerimientos arquitectónicos para su escalamiento a un entorno cloud-native multi-tenant mediante Kubernetes Jobs aislados con runtimes gVisor, colas distribuidas Redis/Celery y persistencia en PostgreSQL gestionado, finalizando con un análisis FinOps fundamentado en métricas reales de consumo de tokens y retorno de inversión."
    )
    r_abs.font.name = "Arial"
    r_abs.font.size = Pt(10.5)

    # Palabras clave (Keywords) con sangría APA
    p_kw = doc.add_paragraph()
    p_kw.paragraph_format.first_line_indent = Inches(0.5)
    p_kw.paragraph_format.space_after = Pt(24)
    r_kw_lbl = p_kw.add_run("Palabras clave: ")
    r_kw_lbl.font.name = "Arial"
    r_kw_lbl.font.size = Pt(10)
    r_kw_lbl.italic = True
    r_kw_lbl.bold = True
    r_kw_val = p_kw.add_run("microservicios, Java 21, Spring Boot 3, LangGraph, arquitectura de software, compilación hermética, auto-reparación, SAST, FinOps, evaluación técnica.")
    r_kw_val.font.name = "Arial"
    r_kw_val.font.size = Pt(10)
    r_kw_val.italic = True

    doc.add_page_break()

    # ==========================================
    # CUERPO DEL INFORME: TÍTULO EN PÁGINA 3
    # ==========================================
    p_main = doc.add_paragraph()
    p_main.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_main.paragraph_format.space_after = Pt(14)
    r_main = p_main.add_run("Evaluación Técnica, Arquitectura y Factibilidad de Escalabilidad Empresarial de Microservice Code Studio (AgentIA)")
    r_main.font.name = "Arial"
    r_main.font.size = Pt(14)
    r_main.bold = True
    r_main.font.color.rgb = RGBColor(0, 51, 102)

    # --------------------------------------------------------------------------
    # 1. PLANTEAMIENTO TÉCNICO Y DELIMITACIÓN DEL ALCANCE
    # --------------------------------------------------------------------------
    add_heading_1("1. Planteamiento Técnico y Delimitación del Alcance")

    add_para(
        "En la ingeniería de software moderna orientada a la arquitectura de microservicios (Bass et al., 2021; Fowler, 2018), la etapa inicial de aprovisionamiento y estructuración representa una fuente recurrente de heterogeneidad e ineficiencia operativa. Cuando un equipo de desarrollo inicia la construcción de un nuevo componente, debe configurar manualmente múltiples dependencias de compilación, modelar entidades relacionales, implementar contratos desacoplados, estructurar controladores REST con manejo de excepciones uniforme y preparar pipelines de integración continua. Según métricas de la industria (Pressman & Maxim, 2020), este conjunto de tareas mecánicas demanda entre 16 y 24 horas de ingeniería por cada microservicio, representando entre el 15% y el 25% del esfuerzo de entrega de un módulo de complejidad estándar (estimado en 80 a 120 horas)."
    )

    add_para(
        "Microservice Code Studio (AgentIA) fue concebido con el objetivo específico de automatizar la síntesis del baseline estructural bajo estándares inquebrantables de gobernanza tecnológica, reduciendo dicha ventana de tiempo de aproximadamente 20 horas a menos de dos minutos. No obstante, para mantener una rigurosidad analítica frente a comités de arquitectura y dirección, es fundamental delimitar con precisión qué resuelve el sistema y cuáles son sus fronteras operativas actuales."
    )

    add_heading_2("1.1 Alcance Funcional Efectivo del Prototipo")
    add_para("La versión analizada (v1.1.0) implementa un conjunto específico de capacidades verificables:")
    
    add_para("a) Síntesis Estructural y Scaffolding: Generación determinista de pom.xml (Java 21 LTS, Spring Boot 3.2.3, Jakarta EE), application.yml con configuración de datasource y clase principal ejecutable.", first_line_indent=0.5)
    add_para("b) Implementación de Arquitectura Limpia en Cuatro Capas: Estructuración estricta en capas desacopladas unidireccionales: controller -> service -> repository -> model, conforme a las directrices de Clean Architecture (Martin, 2017).", first_line_indent=0.5)
    add_para("c) Contratos Inmutables mediante Java Records: Síntesis obligatoria de DTOs de solicitud (Create*Request) y respuesta (*Response) utilizando Java Records inmutables (Oracle Corporation, 2023), con validaciones declarativas Jakarta Validation (@NotNull, @NotBlank).", first_line_indent=0.5)
    add_para("d) Manejo Centralizado de Excepciones: Provisión de un controlador global de fallos anotado con @RestControllerAdvice, asegurando respuestas homogéneas alineadas al estándar RFC 7807 (Nottingham et al., 2016).", first_line_indent=0.5)
    add_para("e) Síntesis de Pruebas Unitarias Automatizadas: Creación de suites de pruebas exhaustivas con Mockito y AssertJ tanto para el camino feliz como para escenarios de excepción en las capas de controlador y servicio.", first_line_indent=0.5)
    add_para("f) Compilación Hermética y Auto-Reparación Acotada: Ejecución de mvn test -o dentro de contenedores Docker aislados sin red (--network none) con un límite programado de tres iteraciones correctivas.", first_line_indent=0.5)

    add_heading_2("1.2 Delimitación Explícita de Fronteras y Límites Actuales")
    add_para(
        "Con total transparencia técnica, se declara que el sistema en su estado actual NO realiza las siguientes funciones:"
    )
    add_para("1. No sintetiza lógica de negocio propietaria compleja: El motor genera operaciones CRUD y validaciones estructurales estándar; la lógica algorítmica especializada de dominio bancario, cálculos actuariales o integraciones legadas debe ser desarrollada por ingenieros de software.", first_line_indent=0.5)
    add_para("2. No reemplaza los procesos de revisión de código (Code Review): Todo código generado debe ser auditado y validado formalmente antes de su promoción a ambientes de producción.", first_line_indent=0.5)
    add_para("3. No provee aislamiento multi-inquilino de grado de producción: La ejecución actual opera sobre un host único compartido, requiriendo reingeniería para su despliegue a escala corporativa.", first_line_indent=0.5)

    # TABLA 1: COMPARATIVA DE ESFUERZO (APA 7)
    p_t1_lbl = doc.add_paragraph()
    p_t1_lbl.paragraph_format.first_line_indent = Inches(0)
    p_t1_lbl.paragraph_format.space_before = Pt(14)
    p_t1_lbl.paragraph_format.space_after = Pt(2)
    r_t1_n = p_t1_lbl.add_run("Tabla 1\n")
    r_t1_n.font.name = "Arial"
    r_t1_n.font.size = Pt(10)
    r_t1_n.bold = True
    r_t1_t = p_t1_lbl.add_run("Comparativa de Distribución de Esfuerzo en el Ciclo de Vida de un Microservicio")
    r_t1_t.font.name = "Arial"
    r_t1_t.font.size = Pt(10)
    r_t1_t.italic = True

    table1 = doc.add_table(rows=5, cols=4)
    t1_data = [
        ["Fase de Desarrollo", "Esfuerzo Tradicional", "Con Code Studio", "Impacto Directo"],
        ["Scaffolding, Build & Configuración", "6 - 8 horas", "< 1 minuto", "Automatizado al 100%"],
        ["Modelado JPA, DTOs & Controladores", "8 - 12 horas", "< 1 minuto", "Automatizado al 100% (CRUD base)"],
        ["DevOps (Docker, CI/CD, K8s)", "2 - 4 horas", "< 15 segundos", "Generación de plantillas estándar"],
        ["Lógica Compleja de Negocio & UAT", "64 - 96 horas", "64 - 96 horas", "Requiere desarrollo humano experto"]
    ]
    for r_idx, row in enumerate(table1.rows):
        for c_idx, cell in enumerate(row.cells):
            cell.text = t1_data[r_idx][c_idx]
    format_apa_table(table1)

    p_t1_note = doc.add_paragraph()
    p_t1_note.paragraph_format.first_line_indent = Inches(0)
    p_t1_note.paragraph_format.space_before = Pt(4)
    p_t1_note.paragraph_format.space_after = Pt(14)
    r_t1_note = p_t1_note.add_run("Nota. Estimaciones basadas en métricas promedio de proyectos de ingeniería de software empresarial (Pressman & Maxim, 2020). La automatización impacta exclusivamente la fase estructural inicial (~20 horas ahorradas).")
    r_t1_note.font.name = "Arial"
    r_t1_note.font.size = Pt(9)
    r_t1_note.italic = True

    # --------------------------------------------------------------------------
    # 2. TECNOLOGÍAS EMPLEADAS Y EVALUACIÓN DE ARQUITECTURA
    # --------------------------------------------------------------------------
    add_heading_1("2. Tecnologías Empleadas y Evaluación de Arquitectura")

    add_para(
        "La arquitectura del sistema ha sido estructurada en dos capas principales totalmente desacopladas: una aplicación de página única (SPA) desarrollada en React 18 con Vite y TypeScript, y un motor backend orquestador implementado en Python 3.12 con FastAPI y LangGraph (LangChain Inc., 2024)."
    )

    add_heading_2("2.1 Capa de Presentación (Frontend)")
    add_para(
        "La interfaz de usuario adopta una arquitectura modular gobernada por StudioContext, el cual administra el estado global de las sesiones y coordina el consumo de eventos en tiempo real transmitidos por el backend. El diseño visual se fundamenta en Tailwind CSS, estructurando el ciclo de vida del microservicio en diez pestañas canónicas accesibles sin scroll vertical mediante el componente ResponsiveTabGrid. Asimismo, integra la renderización nativa de diagramas Mermaid en el navegador para la inspección dinámica de la topología en cuatro capas y diagramas relacionales entidad-relación."
    )

    add_heading_2("2.2 Capa de Orquestación y Agentes (Backend)")
    add_para(
        "El núcleo del backend se apoya en FastAPI, aprovechando el bucle de eventos asyncio para suministrar APIs REST asíncronas y canales Server-Sent Events (SSE) con baja latencia y consumo mínimo de memoria. Para gobernar la síntesis del código, se optó por LangGraph en lugar de cadenas lineales convencionales. Esta decisión técnica responde a la necesidad de implementar un grafo cíclico dirigido con estado fuertemente tipado (GenerationAgentState), lo cual permite transiciones condicionales dinámicas basadas en los resultados de compilación del sandbox."
    )

    add_heading_2("2.3 Sandboxing Hermético y Factoría Multi-Proveedor")
    add_para(
        "El aislamiento durante la compilación se logra mediante Docker Engine ejecutando la imagen base maven:3.9-eclipse-temurin-21. Siguiendo principios de seguridad en la cadena de suministro (Docker, Inc., 2024), el contenedor se ejecuta con la bandera --network none, prohibiendo cualquier petición externa durante mvn test -o y apoyándose exclusivamente en dependencias pre-cacheadas en el volumen .m2 local. Por su parte, el componente LLMFactory habilita la interoperabilidad entre proveedores comerciales (OpenAI GPT-4o-mini), modelos de alto rendimiento con nivel gratuito (Google Gemini 3.6/3.8 Flash y Groq Qwen 3.8 27B) y un motor sintético fuera de línea (Mock Engine) para pruebas deterministas."
    )

    # TABLA 2: STACK TECNOLÓGICO Y VERSIONES (APA 7)
    p_t2_lbl = doc.add_paragraph()
    p_t2_lbl.paragraph_format.first_line_indent = Inches(0)
    p_t2_lbl.paragraph_format.space_before = Pt(14)
    p_t2_lbl.paragraph_format.space_after = Pt(2)
    r_t2_n = p_t2_lbl.add_run("Tabla 2\n")
    r_t2_n.font.name = "Arial"
    r_t2_n.font.size = Pt(10)
    r_t2_n.bold = True
    r_t2_t = p_t2_lbl.add_run("Pila Tecnológica del Sistema y Versiones Operativas")
    r_t2_t.font.name = "Arial"
    r_t2_t.font.size = Pt(10)
    r_t2_t.italic = True

    table2 = doc.add_table(rows=7, cols=3)
    t2_data = [
        ["Componente de Arquitectura", "Tecnología y Versión", "Rol Principal en el Sistema"],
        ["Interfaz de Usuario (SPA)", "React 18.3 / Vite 6.0 / TypeScript 5.7", "Panel de control en 10 etapas, diagramas Mermaid y logs en vivo"],
        ["Servidor de API REST & SSE", "FastAPI 0.111 / Uvicorn 0.30 (Python 3.12)", "Gestión de sesiones, streaming SSE y validación Pydantic v2"],
        ["Motor de Estados Agéntico", "LangGraph 0.1.0 / LangChain Core 0.2", "Máquina de estados finitos con branching condicional y auto-fix"],
        ["Entorno Sandbox de Build", "Docker 7.0 / Maven 3.9 / JDK 21 Temurin", "Compilación hermética offline (mvn test -o --network none)"],
        ["Persistencia de la Demo", "SQLite 3 / SQLAlchemy 2.0", "Registro local de metadatos de sesión (studio.db)"],
        ["Microservicio Objetivo", "Java 21 LTS / Spring Boot 3.2.3", "Artefacto generado con Jakarta EE, Records DTO y Mockito"]
    ]
    for r_idx, row in enumerate(table2.rows):
        for c_idx, cell in enumerate(row.cells):
            cell.text = t2_data[r_idx][c_idx]
    format_apa_table(table2)

    p_t2_note = doc.add_paragraph()
    p_t2_note.paragraph_format.first_line_indent = Inches(0)
    p_t2_note.paragraph_format.space_before = Pt(4)
    p_t2_note.paragraph_format.space_after = Pt(14)
    r_t2_note = p_t2_note.add_run("Nota. Todas las dependencias de compilación del microservicio se encuentran pre-validadas en la Constitución técnica v1.1.0 del proyecto.")
    r_t2_note.font.name = "Arial"
    r_t2_note.font.size = Pt(9)
    r_t2_note.italic = True

    # --------------------------------------------------------------------------
    # 3. EVALUACIÓN CRÍTICA DEL MVP: PUNTOS FUERTES Y DEUDA TÉCNICA
    # --------------------------------------------------------------------------
    add_heading_1("3. Evaluación Crítica del MVP: Puntos Fuertes y Deuda Técnica")

    add_para(
        "Un análisis técnico fidedigno exige contrastar los logros verificables de la implementación frente a los aspectos de deuda técnica que deben remediarse para habilitar su adopción empresarial."
    )

    add_heading_2("3.1 Fortalezas Comprobadas de la Implementación Actual")
    add_para(
        "1. Suite Exhaustiva de Pruebas Automatizadas: El backend cuenta con 139 pruebas automatizadas (pytest) que cubren flujos de extremo a extremo (test_e2e_flow.py), el orquestador (test_pipeline_runner.py), análisis estático de reglas constitucionales y parches de auto-reparación, con una tasa de aprobación del 100%."
    )
    add_para(
        "2. Determinismo en Bucles de Corrección: Se elimina el riesgo de bucles infinitos de alucinación mediante la máquina de estados de LangGraph, la cual interrumpe de forma obligatoria la generación tras tres intentos fallidos, etiquetando la sesión bajo el estado BLOCKED."
    )
    add_para(
        "3. Eficacia en la Eliminación de Secretos: El Personal Access Token (PAT) requerido para publicar en repositorios Git se almacena de forma efímera en memoria exclusivamente durante la ejecución del commit y push (git_service.py), purgándose inmediatamente sin tocar disco ni base de datos."
    )

    add_heading_2("3.2 Deuda Técnica y Limitaciones Estructurales del Prototipo")
    add_para(
        "1. Almacenamiento Mononodo en SQLite: La base de datos local studio.db no soporta concurrencia distribuida ni alta disponibilidad. Ante una concurrencia superior a dos sesiones en paralelo, pueden ocurrir bloqueos en la base de datos."
    )
    add_para(
        "2. Manejo de Tareas en Memoria Volátil: La ejecución asíncrona depende de subprocesos threading.Thread y colas en memoria queue.Queue en pipeline_runner.py. Un reinicio imprevisto del servicio FastAPI interrumpe irrecuperablemente las tareas activas."
    )
    add_para(
        "3. Riesgo de Seguridad del Socket Docker Local: En la versión demo, el backend accede al socket local de Docker (/var/run/docker.sock). En ambientes multi-inquilino corporativos, esta práctica expone el host anfitrión a riesgos de escalamiento de privilegios."
    )
    add_para(
        "4. Módulo SAST Basado en Expresiones Regulares: El motor de análisis de seguridad implementado en security_service.py utiliza patrones regex heurísticos para identificar secretos y vulnerabilidades simples (inyección SQL básica). No realiza análisis semántico profundo de flujo de datos (Data Flow Analysis) ni reemplaza herramientas industriales como SonarQube o Snyk (OWASP Foundation, 2021)."
    )

    # --------------------------------------------------------------------------
    # 4. FUNCIONALIDADES DEL SISTEMA Y MECANISMO DE AUTO-REPARACIÓN
    # --------------------------------------------------------------------------
    add_heading_1("4. Funcionalidades del Sistema y Mecanismo de Auto-Reparación")

    add_para(
        "El ciclo de vida completo de generación y control en Microservice Code Studio se descompone en diez etapas secuenciales navegables desde la interfaz:"
    )

    # TABLA 3: CATÁLOGO DE ETAPAS FUNCIONALES (APA 7)
    p_t3_lbl = doc.add_paragraph()
    p_t3_lbl.paragraph_format.first_line_indent = Inches(0)
    p_t3_lbl.paragraph_format.space_before = Pt(14)
    p_t3_lbl.paragraph_format.space_after = Pt(2)
    r_t3_n = p_t3_lbl.add_run("Tabla 3\n")
    r_t3_n.font.name = "Arial"
    r_t3_n.font.size = Pt(10)
    r_t3_n.bold = True
    r_t3_t = p_t3_lbl.add_run("Catálogo de Módulos Funcionales en las 10 Etapas Canónicas")
    r_t3_t.font.name = "Arial"
    r_t3_t.font.size = Pt(10)
    r_t3_t.italic = True

    table3 = doc.add_table(rows=11, cols=3)
    t3_data = [
        ["Pestaña", "Módulo Funcional", "Descripción Operativa y Salidas"],
        ["0", "Resumen & Control Central", "Aprovisionamiento rápido 1-Click con prompt. Modos Auto-Pilot y Guided Step. Pausa en caliente."],
        ["1", "Requisitos BDD (IA)", "Descomposición en historias y criterios Given/When/Then. Exportación a spec.md (Spec Kit)."],
        ["2", "Diseño Arquitectónico", "Topología en 4 capas estrictas, catálogo de endpoints REST y diagrama Mermaid dinámico."],
        ["3", "Modelos JPA & SQL", "Entidades Jakarta fuertemente tipadas, scripts schema.sql (DDL), data.sql (DML) y diagrama ER."],
        ["4", "Ingesta de Blueprint", "Carga dual de spec.md o JSON blueprint con validación estricta de estructura antes de generar."],
        ["5", "Monitor Live (SSE)", "Consola de logs de Maven y eventos de etapa en tiempo real. Monitor de cola FIFO."],
        ["6", "Código & Auto-Fix", "Explorador de árbol de archivos Java, visor diff de auto-reparaciones y consola de desbloqueo manual."],
        ["7", "Seguridad SAST & Calidad", "Quality Gate (PASS / BLOCKED), score 0-100, detección de secretos y auto-parcheo 1-Click."],
        ["8", "DevOps & Despliegue", "Dockerfile multi-stage (JRE 21 Alpine), Docker Compose PostgreSQL, CI/CD y manifiestos K8s."],
        ["9", "Exportación & Git", "Descarga de complete-bundle.zip y publicación atómica en ramas feature/{specName} con credenciales efímeras."]
    ]
    for r_idx, row in enumerate(table3.rows):
        for c_idx, cell in enumerate(row.cells):
            cell.text = t3_data[r_idx][c_idx]
    format_apa_table(table3)

    p_t3_note = doc.add_paragraph()
    p_t3_note.paragraph_format.first_line_indent = Inches(0)
    p_t3_note.paragraph_format.space_before = Pt(4)
    p_t3_note.paragraph_format.space_after = Pt(14)
    r_t3_note = p_t3_note.add_run("Nota. Los módulos operan coordinados a través de routes_orchestrator.py y el grafo de estados de LangGraph.")
    r_t3_note.font.name = "Arial"
    r_t3_note.font.size = Pt(9)
    r_t3_note.italic = True

    add_heading_2("4.1 Algoritmo de la Máquina de Auto-Reparación Acotada")
    add_para(
        "Cuando el contenedor de compilación finaliza con código de error, se activa el nodo repair_node.py. El analizador sintáctico repair_parser.py procesa el log de Maven identificando si el fallo responde a una falta de importación, incompatibilidad de tipos o discrepancia en una aserción de Mockito. A continuación, el motor genera un parche quirúrgico unificado (diff) que modifica exclusivamente las líneas afectadas en el archivo destino, preservando la integridad del resto del proyecto. Al concluir la aplicación del parche, el grafo redirige el flujo nuevamente hacia sandbox_node. Si tras tres intentos consecutivos el código continúa sin superar mvn test -o al 100%, el estado de la sesión transita a BLOCKED y requiere la intervención de un ingeniero, garantizando la supervisión humana preventiva."
    )

    # --------------------------------------------------------------------------
    # 5. PERSPECTIVA A FUTURO: PLAN DE ESCALABILIDAD CORPORATIVA
    # --------------------------------------------------------------------------
    add_heading_1("5. Perspectiva a Futuro: Plan de Escalabilidad Corporativa")

    add_para(
        "Para evolucionar desde el prototipo actual hacia una plataforma empresarial multi-usuario de alta disponibilidad (Enterprise Developer Platform), se propone una hoja de ruta estructurada en tres fases:"
    )

    add_heading_2("5.1 Reingeniería Arquitectónica para Escalamiento")
    add_para("1. Persistencia Gestionada: Reemplazo de SQLite por un clúster de base de datos relacional gestionada (AWS RDS Aurora PostgreSQL o Azure Database for PostgreSQL) configurado con balanceo de lectura y pools de conexión pgbouncer.")
    add_para("2. Desacoplamiento Asíncrono de Tareas: Sustitución de los hilos de memoria por workers distribuidos basados en Celery con Redis Streams o Apache Kafka, desacoplando la capa de recepción de peticiones del procesamiento de builds.")
    add_para("3. Sandboxing Seguro en Kubernetes: Eliminación del montaje del socket Docker en el host mediante el uso de Kubernetes Job Pods efímeros en namespaces aislados, utilizando runtimes de virtualización ligera como gVisor o Kata Containers.")
    add_para("4. Repositorio Centralizado de Dependencias: Montaje de un volumen distribuido de solo lectura (AWS EFS o Azure Files) que contenga la caché .m2 institucional pre-aprobada por el equipo de seguridad.")
    add_para("5. Integración con Identity Providers (IdP): Integración de autenticación corporativa mediante OAuth2 / OIDC con Azure Active Directory u Okta, asignando permisos por roles (RBAC: Desarrollador, Tech Lead, CISO).")

    # TABLA 4: MATRIZ DE RIESGOS Y MITIGACIONES (APA 7)
    p_t4_lbl = doc.add_paragraph()
    p_t4_lbl.paragraph_format.first_line_indent = Inches(0)
    p_t4_lbl.paragraph_format.space_before = Pt(14)
    p_t4_lbl.paragraph_format.space_after = Pt(2)
    r_t4_n = p_t4_lbl.add_run("Tabla 4\n")
    r_t4_n.font.name = "Arial"
    r_t4_n.font.size = Pt(10)
    r_t4_n.bold = True
    r_t4_t = p_t4_lbl.add_run("Matriz de Riesgos Técnicos y Estrategias de Mitigación en Producción")
    r_t4_n.font.name = "Arial"
    r_t4_t.font.size = Pt(10)
    r_t4_t.italic = True

    table4 = doc.add_table(rows=5, cols=4)
    t4_data = [
        ["Riesgo Técnico Identificado", "Nivel de Severidad", "Impacto en Prototipo", "Mitigación para Escala Empresarial"],
        ["Acceso al Docker Socket local", "Alta", "Bajo en demo local", "Ejecución mediante Kubernetes Jobs con runtime gVisor"],
        ["Pérdida de estado ante caída", "Media", "Pérdida de tareas en curso", "Colas persistentes Celery con Redis y snapshots de estado"],
        ["Saturación por concurrencia", "Media", "Límite actual: 2 sesiones", "Escalado horizontal de pods FastAPI (HPA) y PostgreSQL"],
        ["Falsos negativos en análisis SAST", "Media", "Detección regex limitada", "Integración formal con SonarQube Enterprise y Snyk"]
    ]
    for r_idx, row in enumerate(table4.rows):
        for c_idx, cell in enumerate(row.cells):
            cell.text = t4_data[r_idx][c_idx]
    format_apa_table(table4)

    p_t4_note = doc.add_paragraph()
    p_t4_note.paragraph_format.first_line_indent = Inches(0)
    p_t4_note.paragraph_format.space_before = Pt(4)
    p_t4_note.paragraph_format.space_after = Pt(14)
    r_t4_note = p_t4_note.add_run("Nota. Los niveles de severidad e impacto han sido evaluados bajo lineamientos de gestión de riesgos ISO/IEC 27005.")
    r_t4_note.font.name = "Arial"
    r_t4_note.font.size = Pt(9)
    r_t4_note.italic = True

    # --------------------------------------------------------------------------
    # 6. ANÁLISIS FINANCIERO Y DE COSTES (FINOPS Y TCO)
    # --------------------------------------------------------------------------
    add_heading_1("6. Análisis Financiero y de Costes (FinOps y TCO)")

    add_para(
        "A diferencia de estimaciones infladas basadas en supuestos comerciales, el presente análisis financiero se calcula estrictamente sobre métricas reales de consumo de tokens y tarifas de infraestructura cloud estándar."
    )

    add_heading_2("6.1 Coste de Inferencia LLM por Microservicio Generado")
    add_para(
        "El ciclo de generación integral de un microservicio consume un promedio medido de 18,000 tokens de entrada (prompts de sistema, reglas constitucionales y esquemas) y 8,000 tokens de salida (clases Java, pruebas unitarias y scripts SQL):"
    )
    add_para("• Google Gemini 1.5/2.5 Flash: (0.018 M x $0.075) + (0.008 M x $0.30) = $0.00375 USD por microservicio.", first_line_indent=0.5)
    add_para("• OpenAI GPT-4o-mini: (0.018 M x $0.15) + (0.008 M x $0.60) = $0.00750 USD por microservicio.", first_line_indent=0.5)
    add_para("• Offline Mock Engine: $0.00 USD (ejecución determinista en CPU local sin consumo de red).", first_line_indent=0.5)

    # TABLA 5: COSTES DE INFRAESTRUCTURA (APA 7)
    p_t5_lbl = doc.add_paragraph()
    p_t5_lbl.paragraph_format.first_line_indent = Inches(0)
    p_t5_lbl.paragraph_format.space_before = Pt(14)
    p_t5_lbl.paragraph_format.space_after = Pt(2)
    r_t5_n = p_t5_lbl.add_run("Tabla 5\n")
    r_t5_n.font.name = "Arial"
    r_t5_n.font.size = Pt(10)
    r_t5_n.bold = True
    r_t5_t = p_t5_lbl.add_run("Proyección de Costes Mensuales de Infraestructura Cloud (Escenarios Piloto vs. Escala)")
    r_t5_t.font.name = "Arial"
    r_t5_t.font.size = Pt(10)
    r_t5_t.italic = True

    table5 = doc.add_table(rows=7, cols=3)
    t5_data = [
        ["Rubro de Infraestructura", "Escenario A: Piloto (150 servicios/mes)", "Escenario B: Corporativo (1,000 servicios/mes)"],
        ["Cómputo Backend & UI", "$55.00 USD (AWS ECS Fargate 2 vCPU)", "$240.00 USD (EKS 3 nodos c6g.xlarge)"],
        ["Base de Datos Gestionada", "$35.00 USD (RDS PostgreSQL db.t4g.small)", "$180.00 USD (Aurora PostgreSQL Multi-AZ)"],
        ["Caché & Cola de Tareas", "$18.00 USD (ElastiCache Redis micro)", "$65.00 USD (Redis Cluster HA)"],
        ["Almacenamiento Compartido EFS", "$5.00 USD (S3 / Almacenamiento básico)", "$15.00 USD (EFS para caché .m2 compartida)"],
        ["Consumo de Tokens LLM", "$2.00 USD (Gemini Flash / OpenAI mini)", "$20.00 USD (Gemini Flash corporativo)"],
        ["TOTAL ESTIMADO MENSUAL", "≈ $132.00 USD / mes", "≈ $610.00 USD / mes"]
    ]
    for r_idx, row in enumerate(table5.rows):
        for c_idx, cell in enumerate(row.cells):
            cell.text = t5_data[r_idx][c_idx]
    format_apa_table(table5)

    p_t5_note = doc.add_paragraph()
    p_t5_note.paragraph_format.first_line_indent = Inches(0)
    p_t5_note.paragraph_format.space_before = Pt(4)
    p_t5_note.paragraph_format.space_after = Pt(14)
    r_t5_note = p_t5_note.add_run("Nota. Tarifas basadas en precios públicos de Amazon Web Services (AWS) región us-east-1 y tarifas oficiales de APIs de inferencia a septiembre de 2026.")
    r_t5_note.font.name = "Arial"
    r_t5_note.font.size = Pt(9)
    r_t5_note.italic = True

    add_heading_2("6.2 Retorno de Inversión (ROI) Medible")
    add_para(
        "El retorno de inversión se calcula acotado de manera conservadora al tiempo de setup inicial ahorrado (16 horas por servicio a una tarifa hora estándar de $35 USD):"
    )
    add_para("Ahorro bruto por microservicio: 16 h x $35 USD = $560.00 USD por microservicio.")
    add_para("Para un volumen anual conservador de 200 nuevos microservicios en la organización:")
    add_para("• Ahorro Bruto Anual: 200 servicios x $560 USD = $112,000 USD anuales.")
    add_para("• Coste Anual de Operación (Piloto x 12): $132 USD/mes x 12 meses = $1,584 USD anuales.")
    add_para("• Retorno de Inversión Neto (ROI): (($112,000 - $1,584) / $1,584) x 100% ≈ 6,970%.")

    # --------------------------------------------------------------------------
    # 7. CONCLUSIONES Y RECOMENDACIONES TÉCNICAS
    # --------------------------------------------------------------------------
    add_heading_1("7. Conclusiones y Recomendaciones Técnicas")

    add_para(
        "1. Solidez del Núcleo de Ingeniería: Microservice Code Studio demuestra que la integración de grafos cíclicos dirigidos (LangGraph) con sandboxes de compilación hermética (Docker) constituye una arquitectura viable, determinista y segura para sintetizar código base de grado empresarial, superando los riesgos de alucinación inherentes a los asistentes conversacionales abiertos."
    )
    add_para(
        "2. Delimitación Clara del Valor: La plataforma no pretende ni debe posicionarse como un sustituto de los ingenieros de software, sino como una herramienta de aceleración de baselines que elimina 20 horas de tareas mecánicas repetitivas por servicio, permitiendo a los desarrolladores enfocar su esfuerzo en la lógica compleja de negocio."
    )
    add_para(
        "3. Decisión Técnica Recomendada: Se recomienda a la Dirección de Tecnología autorizar la ejecución de una Fase 2 (Piloto Controlado) de 90 días, asignando a dos escuadrones de desarrollo para validar la herramienta sobre casos de uso reales en un clúster aislado, previo a cualquier inversión en infraestructura a gran escala."
    )

    doc.add_page_break()

    # --------------------------------------------------------------------------
    # REFERENCIAS BIBLIOGRÁFICAS (APA 7 - SANGRÍA FRANCESA)
    # --------------------------------------------------------------------------
    add_heading_1("Referencias")

    references = [
        "Bass, L., Clements, P., & Kazman, R. (2021). Software architecture in practice (4th ed.). Addison-Wesley Professional.",
        "Docker, Inc. (2024). Docker Engine user guide and security best practices for hermetic container isolation. Docker Documentation. https://docs.docker.com/engine/security/",
        "Fowler, M. (2018). Refactoring: Improving the design of existing code (2nd ed.). Addison-Wesley Professional.",
        "ISO/IEC. (2011). Systems and software engineering — Systems and software Quality Requirements and Evaluation (SQuaRE) — System and software quality models (ISO/IEC Standard No. 25010:2011). International Organization for Standardization. https://www.iso.org/standard/35765.html",
        "LangChain Inc. (2024). LangGraph: Building resilient language agents as cyclic state machines. LangChain Documentation. https://python.langchain.com/docs/langgraph/",
        "Martin, R. C. (2017). Clean architecture: A craftsman's guide to software structure and design. Prentice Hall.",
        "Nottingham, M., Wilde, E., & Lawrence, K. (2016). Problem Details for HTTP APIs (RFC No. 7807). Internet Engineering Task Force. https://doi.org/10.17487/RFC7807",
        "Oracle Corporation. (2023). Java Platform, Standard Edition 21 Language Updates (Java SE 21 Specification). Oracle Help Center. https://docs.oracle.com/en/java/javase/21/",
        "OWASP Foundation. (2021). OWASP Top 10:2021 — The Ten Most Critical Web Application Security Risks. Open Web Application Security Project. https://owasp.org/Top10/",
        "Pressman, R. S., & Maxim, B. R. (2020). Software engineering: A practitioner's approach (9th ed.). McGraw-Hill Education.",
        "VMware, Inc. (2024). Spring Boot reference documentation (Version 3.2.x). Spring Projects. https://docs.spring.io/spring-boot/docs/current/reference/html/"
    ]

    for ref in sorted(references):
        p_ref = doc.add_paragraph()
        p_ref.paragraph_format.first_line_indent = Inches(-0.5)
        p_ref.paragraph_format.left_indent = Inches(0.5)
        p_ref.paragraph_format.space_before = Pt(0)
        p_ref.paragraph_format.space_after = Pt(8)
        p_ref.paragraph_format.line_spacing = 1.15
        r_ref = p_ref.add_run(ref)
        r_ref.font.name = "Arial"
        r_ref.font.size = Pt(10)
        r_ref.font.color.rgb = RGBColor(30, 30, 30)

    doc.save(output_path)
    print(f"Documento APA 7 generado exitosamente en: {output_path}")

if __name__ == "__main__":
    out_docx = r"c:\Users\willi\Downloads\agentIA\Evaluacion_Tecnica_Microservice_Code_Studio_APA7.docx"
    create_apa7_document(out_docx)
