import base64
import os
import re

# Read current HTML to preserve the exact base64 TCS logo
with open('docs/agentia_deck.html', 'r', encoding='utf-8') as f:
    current_html = f.read()

# Extract TCS logo
tcs_logo_match = re.search(r'src="(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAbAAAACBCAYAAAChH\+\+W[^"]+)"', current_html)
tcs_logo_b64 = tcs_logo_match.group(1) if tcs_logo_match else ""

with open('docs/fig/how_it_works.svg', 'r', encoding='utf-8') as f:
    how_it_works_svg = f.read()
how_it_works_b64 = "data:image/svg+xml;base64," + base64.b64encode(how_it_works_svg.encode('utf-8')).decode('ascii')

with open('docs/fig/cost_by_scope.svg', 'r', encoding='utf-8') as f:
    cost_by_scope_svg = f.read()
cost_by_scope_b64 = "data:image/svg+xml;base64," + base64.b64encode(cost_by_scope_svg.encode('utf-8')).decode('ascii')

with open('docs/fig/workflow_interactive.svg', 'r', encoding='utf-8') as f:
    workflow_svg = f.read()

header_bar = f'''<div class="bar"><img alt="TCS" src="{tcs_logo_b64}"/><span class="tag">Microservice Code Studio · <b>Executive Summary</b></span></div>'''

slides = []

# ==============================================================================
# SLIDE 1: Portada Ejecutiva
# ==============================================================================
slides.append(f'''<section class="slide hero">
<div class="inner">
<img alt="TCS" class="logo" src="{tcs_logo_b64}"/>
<h1>Generación autónoma<br/>de microservicios</h1>
<div class="sub">Del dolor a la verificación real: arquitectura Spec-Driven, orquestación de agentes y propuesta SOTA de auto-mejora</div>
<div class="rule"></div>
</div>
<div class="foot">Microservice Code Studio · Enterprise Architecture · TCS 2026</div>
</section>''')

# ==============================================================================
# SLIDE 2: 1. El Problema (El dolor y la realidad de la industria)
# ==============================================================================
slides.append(f'''<section class="slide">
{header_bar}
<div class="body">
<h1>1. El Problema: 0 de 15 verificadas y la ilusión de la IA<span class="dot">.</span></h1>
<div class="rule"></div>
<p class="lede">La adopción masiva de asistentes de código acelera la escritura de sintaxis, pero traslada el 76% del tiempo a depuración y genera deuda técnica acelerada.</p>
<div class="grid3">
<div class="card mag">
<span class="tag-lbl">El Dolor Real</span>
<h3>0 de 15 Verificadas</h3>
<ul>
<li>El sistema generaba código con apariencia limpia y profesional.</li>
<li>Al ejecutar pruebas herméticas, <b>ningún servicio compilaba</b>.</li>
<li>Bloqueo real: defecto de montaje Docker y dependencias sin aislar.</li>
</ul>
</div>
<div class="card navy">
<span class="tag-lbl">La Ilusión de los Asistentes</span>
<h3>Fragmentación Ciega</h3>
<ul>
<li>Copilot y Cursor asisten a nivel de archivo o función aislada.</li>
<li>Nadie gobierna la coherencia entre capas, contratos ni dependencias.</li>
<li><b>76% del tiempo de ingeniería</b> se gasta en depurar y parchar.</li>
</ul>
</div>
<div class="card">
<span class="tag-lbl">La Causa Raíz</span>
<h3>Falta de Gobernanza</h3>
<ul>
<li>Generar código sin compuertas herméticas acumula deuda técnica.</li>
<li>No falta capacidad en el LLM; falta <b>diseño por especificación</b>.</li>
<li>La solución exige que la especificación mande y verifique antes de entregar.</li>
</ul>
</div>
</div>
<div class="alert" style="margin-top:20px"><b>Principio rector:</b> La promesa de la IA no es generar más líneas por minuto, sino entregar software corporativo verificado, auditable y listo para producción.</div>
</div>
</section>''')

# ==============================================================================
# SLIDE 3: 2. La Solución y Alcance: Spec-Driven Design
# ==============================================================================
slides.append(f'''<section class="slide">
{header_bar}
<div class="body">
<h1>2. Solución y Alcance: Spec-Driven Design<span class="dot">.</span></h1>
<div class="rule"></div>
<p class="lede">El modelo no inventa la arquitectura: la especificación formal es la única fuente de verdad inmutable.</p>
<div class="cols">
<div>
<table class="spec">
<tr><th>Nivel de Especificación</th><th>Prescripción Contractual</th></tr>
<tr><td><b>Constitution (4 capas)</b></td><td>Dominio, Servicio, Infraestructura, API. Prohibición estricta de acoplamiento cruzado y llamadas circulares.</td></tr>
<tr><td><b>19 Contratos OpenAPI & BDD</b></td><td>Esquemas canónicos de datos, DTOs inmutables (records), códigos HTTP y escenarios Given-When-Then.</td></tr>
<tr><td><b>Lista blanca de dependencias</b></td><td>Librerías corporativas homologadas y versiones congeladas en POM raíz. Cero dependencias sorpresa.</td></tr>
<tr><td><b>Alcance tecnológico</b></td><td>Microservicios Java 21 LTS, Spring Boot 3.x, Spring Data JPA, Mockito, perfil hermético offline.</td></tr>
</table>
</div>
<div>
<div class="card navy">
<span class="tag-lbl">Arquitectura Desacoplada</span>
<h3>5 Subsistemas Modulares</h3>
<ul style="margin-top:6px">
<li><b>1. Web Studio (React/Vite):</b> 10 fases del ciclo de vida y streaming SSE en vivo.</li>
<li><b>2. API Gateway (FastAPI):</b> Gestión de sesiones, persistencia y control de ejecución.</li>
<li><b>3. Motor Agéntico (LangGraph):</b> Grafo coordinado de 8 agentes especializados con memoria.</li>
<li><b>4. Sandbox Hermético (Docker):</b> <code>mvn test -o --network none</code> (contenedor sellado).</li>
<li><b>5. Observabilidad:</b> Registro forense de costes y tokens en SQLite y MLflow.</li>
</ul>
</div>
</div>
</div>
<div class="alert" style="margin-top:16px"><b>Garantía innegociable:</b> El LLM actúa estrictamente como un compilador de especificación a código Java ejecutable. Si no compila en sandbox, <b>no se entrega</b>.</div>
</div>
</section>''')

# ==============================================================================
# SLIDE 4: 3. Diagrama de Funcionamiento: Orquestación de Agentes
# ==============================================================================
slides.append(f'''<section class="slide">
{header_bar}
<div class="body">
<h1>3. Funcionamiento: Orquestación LangGraph<span class="dot">.</span></h1>
<div class="rule"></div>
<p class="lede">Grafo coordinado de 8 agentes con segregación de responsabilidades, compuertas deterministas y ciclo de reparación reflexivo acotado.</p>
<!-- Diagrama vectorial interactivo del flujo de nodos -->
{workflow_svg}
<div class="grid2" style="margin-top:12px;">
<div class="card navy">
<span class="tag-lbl">5 Agentes Especializados LLM</span>
<h3>Especialistas de Dominio Técnico</h3>
<ul style="margin-top:4px">
<li><b>1. Scaffolder:</b> Estructura Maven y dependencias de lista blanca.</li>
<li><b>2. Dominio:</b> Entidades JPA, records inmutables, repositorios.</li>
<li><b>3. Servicio:</b> Lógica transaccional y reglas de negocio BDD.</li>
<li><b>4. Controlador:</b> Endpoints REST y <code>@RestControllerAdvice</code>.</li>
<li><b>5. Test:</b> Cobertura unitaria y de integración mapeada a BDD.</li>
</ul>
</div>
<div class="card mag">
<span class="tag-lbl">3 Agentes Deterministas / Guardas</span>
<h3>Gobernanza y Verificación Hermética</h3>
<ul style="margin-top:4px">
<li><b>6. Validador estático (Zero-LLM):</b> Valida sintaxis y esquemas antes de compilar.</li>
<li><b>7. Sandbox Docker:</b> Ejecuta <code>mvn test -o</code> en contenedor sellado sin red.</li>
<li><b>8. Reparación reflexiva:</b> Analiza traza de error y reintenta con límite estricto de <b>máx. 3 iteraciones</b> antes de escalar a humano (<code>BLOQUEADO</code>).</li>
</ul>
</div>
</div>
</div>
</section>''')

# ==============================================================================
# SLIDE 5: 4. Métricas, Resultados y Costes Reales
# ==============================================================================
slides.append(f'''<section class="slide">
{header_bar}
<div class="body">
<h1>4. Métricas, Calidad y Costes de Producción<span class="dot">.</span></h1>
<div class="rule"></div>
<p class="lede">De «no podía verificar su propia salida» a un pipeline de $0.06 por microservicio verificado y auditable.</p>
<div class="cols">
<div class="fig">
<img alt="cost_by_scope" src="{cost_by_scope_b64}" style="width:100%;max-height:46vh;object-fit:contain"/>
</div>
<div>
<div class="grid2" style="margin-top:0;">
<div class="card navy">
<div class="big">$0.06 <span class="small">USD</span></div>
<p><b>Por microservicio individual</b> generado y verificado (5 etapas LLM).</p>
</div>
<div class="card mag">
<div class="big mag">$0.20 <span class="small">USD</span></div>
<p><b>Con selección de 3 candidatos</b> compitiendo; se elige el que compila y pasa pruebas.</p>
</div>
</div>
<div class="card" style="margin-top:12px;">
<span class="tag-lbl">Estado Actual de Verificación</span>
<ul style="margin-top:4px">
<li><b>100% compilación verificada:</b> Primera build pasando en sandbox hermético sin red.</li>
<li><b>Paridad de rutas:</b> Flujo secuencial y grafo LangGraph comparten el mismo estándar.</li>
<li><b>Consumo de tokens:</b> 78K tokens por servicio; 2.2M ahorrados desde caché.</li>
<li><b>Trazabilidad MLflow:</b> Registro forense de cada llamada, latencia y coste en SQLite.</li>
<li><b>Punto abierto:</b> 33% intermitencia bajo carga por reetiquetado SELinux <code>:Z</code> (en resolución).</li>
</ul>
</div>
</div>
</div>
</div>
</section>''')

# ==============================================================================
# SLIDE 6: 5. Próximos Pasos: Auto-Mejora con SkillOpt (SOTA)
# ==============================================================================
slides.append(f'''<section class="slide">
{header_bar}
<div class="body">
<h1>5. Próximos Pasos: Auto-Mejora con SkillOpt (SOTA)<span class="dot">.</span></h1>
<div class="rule"></div>
<p class="lede">Aprender de los diagnósticos de fallo para refinar automáticamente las políticas de generación bajo 4 controles formales de fiabilidad.</p>
<div class="cols">
<div>
<div class="card navy" style="margin-bottom:12px;">
<span class="tag-lbl">Propuesta SOTA en Espacio de Texto</span>
<h3>Los 4 Controles de Fiabilidad</h3>
<ul style="margin-top:4px;font-size:15px;">
<li><b>1. Presupuesto acotado (&le; L<sub>t</sub> = 4):</b> Decaimiento coseno de ediciones permitidas; previene reescrituras caóticas.</li>
<li><b>2. Held-out Validation Gate:</b> Solo se acepta una regla si mejora estrictamente en tareas no vistas (empates rechazados).</li>
<li><b>3. Búfer de rechazos:</b> Propuestas fallidas se realimentan como contraejemplos negativos para evitar ciclos.</li>
<li><b>4. Actualización lenta por época:</b> Consolida aprendizajes globales; sin ella, el sistema <b>colapsa en -22.5 pts</b>.</li>
<li><b>Evidencia SOTA:</b> 52 de 52 celdas ganadas/empatadas (+23.5 pts en GPT-5.5, +24.8 pts en Codex).</li>
</ul>
</div>
</div>
<div>
<table class="path" style="font-size:15px;">
<tr><th>Paso</th><th>Objetivo técnico</th><th>Esfuerzo / Coste</th></tr>
<tr><td><b>1</b></td><td><b>Verificador determinista:</b> aislamiento SELinux <code>:Z</code> en volumen Docker</td><td>Corto (1–2 días)</td></tr>
<tr><td><b>2</b></td><td><b>Diagnóstico rico:</b> minería estructurada de fallos en trazas Surefire</td><td>Corto</td></tr>
<tr><td><b>3</b></td><td><b>Inyección baseline:</b> medir impacto del manual Java/Maven inicial</td><td>$3–$5 en inferencia</td></tr>
<tr><td><b>4</b></td><td><b>Bucle cerrado SkillOpt:</b> optimización reflexiva gobernada por los 4 controles</td><td>Condicionado a 1-3</td></tr>
</table>
<div class="alert" style="margin-top:14px;font-size:15px;padding:12px 16px;">
<b>Visión de producto:</b> Un sistema que genera, compila y verifica microservicios por $0.07, y que perfecciona sus propias reglas de forma continua y gobernada.
</div>
</div>
</div>
</div>
</section>''')

# Assemble full HTML
head_part = current_html[:current_html.find('<div class="deck">')]
deck_open = '<div class="deck">\n'
slides_part = '\n'.join(slides)
tail_part = '''\n</div>
<div class="counter" id="cnt"></div>
<div class="nav"><button onclick="show(i-1)">←</button><button onclick="show(i+1)">→</button></div>
<script>
const s=Array.from(document.querySelectorAll('.slide'));let i=0;
function show(n){i=(n+s.length)%s.length;s.forEach((x,k)=>x.classList.toggle('active',k===i));
document.getElementById('cnt').textContent=(i+1)+' / '+s.length;}
document.addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key===' ')show(i+1);if(e.key==='ArrowLeft')show(i-1);});
document.addEventListener('click',e=>{if(e.clientX>window.innerWidth*0.75)show(i+1);else if(e.clientX<window.innerWidth*0.25)show(i-1);});
show(0);
</script>
</body></html>'''

full_html = head_part + deck_open + slides_part + tail_part

with open('docs/agentia_deck.html', 'w', encoding='utf-8') as f:
    f.write(full_html)

print(f'Successfully built docs/agentia_deck.html with {len(slides)} executive slides!')
