# Microservice Code Studio ⚡

> **Aplicación Web para la Generación Autónoma y Verificación Hermética de Microservicios Java 21 / Spring Boot 3.x**

Microservice Code Studio es una plataforma integral que ingesta especificaciones formales de microservicios (blueprints de arquitectura, entidades de dominio e historias de usuario con criterios Given/When/Then), orquesta la síntesis de código mediante un agente **LangGraph**, ejecuta compilaciones y pruebas en un sandbox **Docker hermético y fuera de línea** (`--network none`), y entrega proyectos listos para producción mediante descarga en ZIP o publicación atómica a una rama de Git.

---

## 🏛️ Arquitectura del Sistema (Opción B)

El sistema opera desacoplado en dos capas:

```
┌─────────────────────────────────────────────────────────────┐
│             React / Vite Web Studio (Frontend :3000)        │
│  - Asistente BDD, Arquitectura y Modelos Relacionales       │
│  - Ingesta de spec.md / JSON Blueprint                      │
│  - Monitor en Vivo con Server-Sent Events (SSE) y Logs      │
│  - Auditoría SAST, Calidad, DevOps y Exportación de Código  │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / SSE / REST API
┌──────────────────────────────▼──────────────────────────────┐
│             FastAPI Orchestrator Engine (Backend :8000)     │
│  - Cola FIFO de Concurrencia (Máx 2 compilaciones simult.)  │
│  - Agente Autónomo LangGraph (Scaffolder, DTOs, Servicios)  │
│  - Sandbox Docker Hermético (mvn test -o --network none)    │
│  - Máquina de Auto-Reparación Acotada (Máx 3 iteraciones)   │
│  - Base de Datos SQLite/PostgreSQL para Sesiones            │
└─────────────────────────────────────────────────────────────┘
```

---

## 📜 Cumplimiento Constitucional (Constitución v1.1.0)

1. **Principio I: Java 21 LTS y Spring Boot 3.x**: Estricto uso de Java 21 (`java.version=21`) y Spring Boot 3.2+ (Jakarta EE en lugar de `javax`).
2. **Principio II: Records para DTOs**: Todos los objetos de transferencia de datos (`Create*Request`, `*Response`) son Java Records inmutables.
3. **Principio III: `@RestControllerAdvice`**: Manejo centralizado y uniforme de errores HTTP y respuestas RFC 7807 / JSON estructurado.
4. **Principio IV: Compilación Hermética y Pruebas Unitarias al 100%**: Sandbox Docker ejecutado con `--network none` y `mvn test -o` con caché `.m2` de solo lectura. Pruebas unitarias Mockito con 100% de tasa de aprobación.
5. **Principio V: Auto-reparación Acotada (Máximo 3 Intentos)**: Si fallan pruebas o compilación, el analizador de trazas Maven diagnostica y reintenta hasta 3 veces; al fallar el tercer intento pasa a `BLOCKED` (Intervención humana requerida).
6. **Principio VI: Cero Secretos Persistidos**: Tokens de acceso personal (PAT) para Git y claves API se procesan efímeramente en memoria y jamás se persisten en disco ni en base de datos.

---

## 🚀 Requisitos Previos

- **Python**: 3.11 o 3.12 (`python --version`)
- **Docker Desktop** (opcional, para ejecución real en contenedor Docker con Java 21 / Maven 3.9 pre-cacheados)

---

## 📦 Instalación y Configuración

### 1. Clonar o acceder al repositorio
```bash
cd agentIA
```

### 2. Configurar el Backend (FastAPI + LangGraph)
```bash
# Instalar dependencias del backend
pip install -r backend/requirements.txt

# Iniciar servidor backend FastAPI en el puerto 8000
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```
*Documentación interactiva Swagger UI disponible en:* `http://localhost:8000/docs`

### 3. Configurar el Frontend (React + Vite + TypeScript)
```bash
# En una terminal separada, navegar a frontend e instalar paquetes
cd frontend
npm install

# Iniciar el servidor de desarrollo Vite en el puerto 3000
npm run dev
```
*Interfaz de usuario disponible en:* `http://localhost:3000`

---

## 🧪 Ejecución de la Suite de Pruebas Automatizadas

El proyecto cuenta con una batería completa de **125 pruebas automatizadas** (unitarias, de integración, contract tests y end-to-end), con un 100% de tasa de aprobación:

```bash
# Ejecutar todas las pruebas con pytest
python -m pytest backend/tests -o pythonpath=backend
```

Suite de pruebas principales:
- `test_e2e_flow.py`: Flujo E2E integral (Ingesta dual, pipeline Auto-Pilot, pause/resume, auditoría SAST, auto-reparación quirúrgica, DevOps y exportación).
- `test_pipeline_runner.py`: Motor de generación generativa completa (sintetiza especificación, historias BDD, arquitectura 4 capas, DDL relacional, código Java 21 LTS y pruebas Mockito).
- `test_sessions_api.py`: Gestión de sesiones, listado cronológico de sesiones y aprovisionamiento rápido 1-Click (`/api/v1/sessions/quick-start`).
- `test_routes_orchestrator.py`: Orquestador central, transiciones de fase, ejecución de pipeline Auto-Pilot, hot-pause, resume, cancel y re-sincronización forzada.
- `test_security_service.py` & `test_routes_security.py`: Auditoría estática SAST, detección de secretos hardcodeados, evaluación CVE, Compuertas de Calidad (Quality Gate) y auto-parcheo quirúrgico.
- `test_devops_service.py` & `test_routes_devops.py`: Docker multi-stage hermético, Docker Compose con PostgreSQL, pipelines de CI/CD (GitHub Actions / GitLab CI) y manifiestos de Kubernetes.
- `test_architecture_service.py` & `test_routes_architecture.py`: Topología en 4 capas estrictas, catálogo de componentes, endpoints REST y diagramas Mermaid.
- `test_model_sql_service.py` & `test_routes_models_sql.py`: Entidades JPA Jakarta Persistence, scripts relacionales DDL/DML para PostgreSQL y diagramas Mermaid `erDiagram`.
- `test_requirements_service.py` & `test_routes_requirements.py`: Asistente de requisitos BDD Given/When/Then con IA y exportación Spec Kit `spec.md`.
- `test_test_analysis_service.py`: Analizador de reglas constitucionales estáticas, diagnóstico de compilación Maven y auto-reparación acotada a 3 intentos.

---

## 🖥️ Flujo de Trabajo en la Interfaz Web (10 Pestañas Canónicas)

La interfaz web unificada en Streamlit organiza el ciclo de vida completo del microservicio en 10 etapas claras:

0. **🏠 Pestaña 0 - Resumen del Proyecto & Control Central**:
   - Tarjeta de **Inicio Rápido 1-Click** para crear nuevos microservicios a partir de un prompt en lenguaje natural.
   - Selector interactivo entre modo **🚀 Auto-Pilot** (flujo desatendido) y **👣 Modo Paso a Paso** (revisión asistida).
   - Controles de pipeline en caliente: Pausa (`⏸️ Pausar`), Reanudar (`▶️ Reanudar`) y Cancelar (`⏹️ Cancelar`).
   - Grilla de indicadores ejecutivos: Historias BDD, Entidades SQL, Suites de Pruebas, Veredicto del Quality Gate y Estado de Despliegue.
   - Descarga con 1 clic del paquete de entrega completo (`complete-bundle.zip`).

1. **📝 Pestaña 1 - Requisitos & Historias (IA)**:
   - Redacción y descomposición de requerimientos de negocio con IA.
   - Síntesis de historias de usuario canonicales y escenarios de aceptación **Given/When/Then**.
   - Detección de entidades de dominio y exportación del archivo `spec.md` (Spec Kit).

2. **🏗️ Pestaña 2 - Diseño Arquitectónico & Componentes (IA)**:
   - Visualización en tiempo real del diagrama **Mermaid** en 4 capas estrictas (`Controller` ➔ `Service` ➔ `Repository` ➔ `Model`).
   - Catálogo jerárquico de componentes y contratos de endpoints REST con Java Records inmutables.
   - Refinamiento interactivo de la arquitectura mediante instrucciones en lenguaje natural.

3. **💾 Pestaña 3 - Modelos de Dominio JPA & Esquema SQL**:
   - Entidades Jakarta Persistence fuertemente tipadas con auditoría (`createdAt`, `updatedAt`) y claves autonuméricas.
   - Diagrama visual de entidades y relaciones (Mermaid `erDiagram`).
   - Scripts relacionales sincronizados: `schema.sql` (DDL de tablas e índices) y `data.sql` (DML de datos semilla).

4. **📥 Pestaña 4 - Ingesta de Especificación**:
   - Carga de especificaciones previas mediante drag-and-drop de archivos `spec.md` o JSON blueprint.
   - Validación automática de sintaxis, entidades y cobertura de criterios de aceptación.

5. **🚀 Pestaña 5 - Generación & Logs en Vivo**:
   - Orquestación de la síntesis autónoma con el grafo LangGraph.
   - Terminal de logs en tiempo real vía Server-Sent Events (SSE).
   - Visualización del progreso de etapas (`SCAFFOLDING` → `CODE_GENERATION` → `TEST_SYNTHESIS` → `SANDBOX_BUILD` → `SELF_REPAIR_LOOP` → `VERIFIED`).

6. **🔍 Pestaña 6 - Código, Tests & Auto-Reparación**:
   - Explorador jerárquico del código fuente Java 21 / Spring Boot 3 generado con resaltado de sintaxis.
   - Inspección de suites de pruebas Unitarias Mockito, Web y de Integración.
   - Historial de auto-reparaciones quirúrgicas con visor de diferencias unificadas (`diff`).
   - Consola de intervención manual para desbloquear sesiones detenidas por límite de iteraciones.

7. **🛡️ Pestaña 7 - Seguridad, Calidad & SAST**:
   - Banner de veredicto del **Quality Gate** (PASS / BLOCKED) y cálculo de Score de Calidad (0-100).
   - Detección estática de secretos hardcodeados, vulnerabilidades SAST (inyección SQL, XSS, deserialización insegura) y CVEs.
   - Botón de **Auto-Remediación Quirúrgica 1-Click** para aplicar parches de seguridad directos sin reescribir archivos manualmente.
   - Métricas de mantenibilidad: Complejidad ciclomática, duplicación y densidad de aserciones.

8. **🚀 Pestaña 8 - DevOps, Contenerización & Despliegue**:
   - Generación de `Dockerfile` multi-stage optimizado para Java 21 LTS.
   - Configuración de `docker-compose.yml` con servicio PostgreSQL y volúmenes persistentes.
   - Pipelines de CI/CD para GitHub Actions y GitLab CI con caché de dependencias Maven.
   - Manifiestos de Kubernetes (`deployment.yaml`, `service.yaml`, `configmap.yaml`).

9. **📦 Pestaña 9 - Exportación & Publicación en Git**:
   - Descarga del código fuente completo empaquetado como proyecto Maven en archivo ZIP.
   - Publicación atómica a repositorios Git remotos (GitHub / GitLab) en ramas dedicadas `feature/{specName}` con credenciales efímeras en memoria.
