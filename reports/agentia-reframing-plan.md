# Reframing AgentIA — architecture-first, inference-driven synthesis

Feedback del Tech Leader (revisión de la app) convertido en un plan de reframing y
una división de componentes. Dos ambigüedades quedan marcadas como *"a confirmar"* al
final en vez de bloquear el plan.

---

## 1. El reframing en una frase

> Hoy: un generador que produce un microservicio Spring Boot de **arquitectura fija**
> (4 capas, un módulo, Maven), donde el LLM incluso escribe el `pom.xml` y la
> estructura de carpetas (gasto de tokens).
>
> Objetivo: un sistema **"primero la arquitectura"** que (1) elige/infiere una
> arquitectura de un catálogo, (2) genera la estructura de forma **determinista**
> (arquetipo Maven o CLI de Quarkus, **cero tokens**), y (3) usa el LLM **solo para la
> lógica de negocio** dentro de una estructura ya correcta.

Esto separa dos cosas que hoy están mezcladas: *estructura* (determinista, barata,
correcta por construcción) y *lógica* (LLM, dentro de los límites que la estructura
impone).

---

## 2. Decisiones, mapeadas al feedback

| # | Feedback (notas) | Decisión |
|---|---|---|
| 1 | Definir qué arquitectura usar (¿hexagonal, DDD?) | **Catálogo de arquitecturas** con perfiles nombrados: `layered` (actual), `hexagonal`, `hexagonal-ddd`. La arquitectura se elige **primero** y queda registrada en la sesión. |
| 2 | Especificar arquitectura / patrones | Cada perfil declara en datos (no en prompts): módulos, paquetería, puertos/adaptadores, build tool, dependencias permitidas. |
| 3 | Capa X en Proyecto Y | **Multi-módulo**: cada capa es su propio módulo Maven/Gradle. Hexagonal → `domain`, `application`, `infrastructure`, `adapter-in/rest`, `adapter-out/db`. |
| 4 | Infraestructura "junto al controller" (¿bueno o malo?) | Resolver con multi-módulo: en hexagonal la infraestructura es un módulo **separado** (adapters), no junto al controller. *A confirmar* si el TL lo señaló como defecto o como patrón a formalizar. |
| 5 | Credenciales en archivo externo | Secretos **solo** en `application.yaml`/variables de entorno. La compuerta de cumplimiento prohíbe claves hardcodeadas en código fuente. |
| 6 | Nombre de entidades / reglas entity-dto-camel | Reglas de convención en la constitución: entidades PascalCase singular; DTO con sufijo `Request`/`Response`; campos y variables **camelCase**; paquetes en minúscula. Verificadas por la compuerta. |
| 7 | Inferir extensiones (ej. la base tendrá una DB de tipo tal) | Nuevo nodo **Inferencia**: del spec deduce DB, messaging, caché, librerías. |
| 8 | Interfaz de entrada: volumen de peticiones → tipo de DB | El spec gana una sección **"interfaz"**: volumen esperado (QPS), modelo de datos, integraciones. De ahí sale el tipo de DB. |
| 9 | Inferir las librerías | La inferencia elige librerías (JPA vs JDBC, framework web, validación) dentro de la lista blanca del perfil elegido. |
| 10 | Maven o Gradle, elegible | El build tool es un **atributo del perfil**, seleccionable por arquitectura. |
| 11 | Primero la arquitectura | Reordenar el pipeline: **arquitectura → inferencia → andamiaje → lógica → verificación**. |
| 12 | Arquetipo Maven por cada arquitectura | Un **arquetipo Maven por perfil**; el andamiaje corre el arquetipo (determinista, sin tokens). |
| 13 | Usar Quarkus CLI para generar carpetas | Estructura vía **`quarkus create`** (o el arquetipo) para perfiles Quarkus. El LLM **nunca** escribe `pom.xml` ni carpetas. |

---

## 3. División de componentes (implementación)

### Frontend — React/Vite
| Componente | Responsabilidad |
|---|---|
| `SpecIngestion` | Blueprint + la nueva sección **"interfaz"** (volumen, datos, integraciones). |
| `ArchitecturePreview` | Muestra el perfil elegido y el **plan inferido** (arquitectura, DB, build tool, módulos) antes de generar. |
| `GenerationMonitor` | Logs en vivo (SSE), progreso de fases. |
| `SettingsDrawer` | Proveedor LLM, modelo; secretos externalizados (nunca en código). |
| `Export` | ZIP / Git atómico. |

### Backend — FastAPI + LangGraph
| Componente | Tipo | Responsabilidad |
|---|---|---|
| `routes` | existente | API REST / sesiones / pipeline. |
| **`InferenceEngine`** | **nuevo** | Spec (con "interfaz") → `ArchitecturePlan` (perfil, DB, build tool, módulos, librerías). |
| **`ArchitectureCatalog`** | **nuevo** | Perfiles (`layered`, `hexagonal`, `hexagonal-ddd`) + arquetipos + plantillas Quarkus. |
| **`Scaffolder`** | **refactor** | Determinista: corre arquetipo/CLI. Ya **no** es un nodo LLM. |
| `GenerationStages` | existente | LLM rellena lógica (domain/service/controller/test) dentro de los módulos ya creados. |
| `ComplianceGate` | existente | Reglas + convenciones de nombres + "sin secretos en código" + lista blanca. |
| `VerificationSandbox` | existente | Compilación hermética **multi-módulo** (Spring o Quarkus). |
| `CostTracing` + `MlflowMirror` | existente | Coste/tokens por llamada y sesión. |

### Infraestructura / catálogo
| Componente | Responsabilidad |
|---|---|
| Arquetipos Maven (por perfil) | Estructura correcta por construcción, versionados. |
| Quarkus CLI (`quarkus create`) | Andamiaje para perfiles Quarkus. |
| Docker sandbox + caché `.m2` | Compilación offline hermética. |
| Cost store + MLflow | Sistema de registro y espejo de coste. |

---

## 4. El big picture

El diagrama de componentes (cada funcionalidad es una caja, con sus conexiones) está
en `docs/fig/reframing-components.pdf` (generado desde `reframing-components.dot`).

Flujo de la petición:
`Spec (con interfaz) → Inferencia → Catálogo/Arquetipo → Andamiaje determinista →
Generación LLM (módulos) → Compuerta → Verificación hermética → Entrega`.

---

## 5. Secuencia de trabajo (qué primero)

1. **Catálogo de arquitecturas** (perfiles `layered`/`hexagonal`/`hexagonal-ddd`) como datos.
2. **Sección "interfaz" del spec** + **InferenceEngine** (spec → plan).
3. **Scaffolder determinista** (arquetipo Maven + `quarkus create`) — retira al LLM del `pom.xml`.
4. **Multi-módulo** ("capa X en proyecto Y").
5. **Convenciones + secretos externos** en la compuerta.
6. **Verificación multi-módulo** (Spring y Quarkus).

---

## 6. A confirmar (ambigüedades de las notas)

- **"ddb"** — interpretado como **DDD** (hexagonal + DDD). Confirmar si se refiere a
  Domain-Driven Design o a otra cosa (p. ej. base de datos).
- **"Infraestructura junto al controller"** — asumido como punto a **corregir** vía
  multi-módulo (adapters separados). Confirmar si era defecto señalado o patrón deseado.
