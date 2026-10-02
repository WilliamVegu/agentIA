# Especificación Funcional: Fábrica de Agentes Java Developer de Microservicios Quarkus 3.x

**Rama de Característica**: `001-quarkus-agent-factory` | **Fecha**: 2026-10-01 | **Iniciativa**: Fábrica de Agentes Java Quarkus | **Versión**: 3.0.0 | **Estado**: Aprobado / Implementado

**Entrada Inicial**:
> "Construir un agente de IA con el perfil de Java developer de APIs y microservicios, capaz de crear microservicios en Quarkus a partir de un pedido de negocio y entregarlos con pruebas, documentación, seguimiento, monitoreo y pull request. Este agente sería el primer producto de la fábrica de agentes."

---

## 1. Decisiones de Negocio y Arquitectura de Flujo

* **Paso 1: Entrada del Pedido, Selección de Arquetipo y Validador de Calidad**:
  * Formulario limpio (Zero Defaults) sin precargas ficticias ni plantillas rígidas.
  * Selección explícita de herramienta de construcción: **Apache Maven** (`pom.xml`) o **Gradle** (`build.gradle`) con Java 21 LTS.
  * Validador en vivo de criterios técnicos: nombre kebab-case (≥ 3 caracteres), equipo (≥ 2 caracteres), groupId Java válido, descripción funcional (≥ 30 caracteres) y motor de base de datos.
* **Eliminación Total del Módulo de Preguntas / Aclaración**:
  * Se descarta de forma definitiva el cuestionario de preguntas intermedias que interrumpía el flujo. La IA sintetiza de inmediato el contrato OpenAPI 3.1, Historias de Usuario BDD y Modelo Relacional para su revisión.
* **Paso 2 (Control Humano 1): Contrato OpenAPI Dinámico y Revisión Viva (Contract-Driven Real)**:
  * El usuario inspecciona y edita el contrato OpenAPI 3.1, las Historias de Usuario (mínimo 10 HUs BDD) y el modelo de datos relacional.
  * **Inteligencia Reactiva**: Cada cambio realizado por el usuario en el contrato OpenAPI es **parseado e interpretado dinámicamente por la IA** para generar los endpoints, los DTOs inmutables (Java 21 Records) y la estructura de tablas correspondiente.
  * Al aprobar, el alcance queda congelado de forma inmutable.
* **Paso 3: Arquitectura & Aprobación/Reemplazo de Extensiones Quarkus y sus Versiones**:
  * Elección entre 3 patrones de diseño: Capas Estándar (Pragmática), Hexagonal / Ports & Adapters (DDD), o Reactiva (Mutiny).
  * **Catálogo Transparente de Extensiones**: La IA lista previamente las extensiones Quarkus 3.x con sus coordenadas Maven, categorías y **versiones exactas** (ej. Quarkus 3.15 LTS), permitiendo al usuario **aprobarlas**, **descartarlas**, **cambiar la versión** o **reemplazarlas/añadir nuevas**.
* **Paso 4: Generación de Código Java/Quarkus, APIs, Modelos y Base de Datos**:
  * Interfaces y Recursos JAX-RS / RESTEasy Reactive respetando los endpoints del contrato revisado.
  * DTOs generados obligatoriamente como **Java 21 Records inmutables** con Jakarta Bean Validation.
  * Persistencia mediante entidades Hibernate ORM con Panache y scripts de migración Flyway (`V1.0.0__init_schema.sql`).
* **Paso 5: Pruebas Automatizadas y Bucle de Auto-Corrección (Self-Healing)**:
  * Ejecución de suite `@QuarkusTest`, integración con RestAssured y unitarias con Mockito.
  * Detección automática y corrección de discrepancias de compilación, imports o tests en runtime.
* **Paso 6: Documentación Completa y Auditoría de Code Review**:
  * Generación de los 5 manuales Markdown (`README.md`, `DOCUMENTACION_API.md`, `ADR_001`, `GUIA_PRUEBAS_COBERTURA.md`, `GUIA_OPERACION_SERVICIO.md`).
  * Auditoría estática por el Agente Revisor evaluando estándares SOLID, scopes CDI `@ApplicationScoped` y seguridad.
* **Paso 7 (Control Humano 2): Aprobación Final, CI/CD y Descarga ZIP**:
  * Revisión del árbol de código Java, pruebas y consumo de tokens.
  * Preparación de `Jenkinsfile`, `Dockerfile` multi-stage y descarga directa en paquete `.ZIP` ejecutable con `./mvnw quarkus:dev`.

---

## 2. Historias de Usuario y Criterios de Aceptación

### Historia de Usuario 1 - Entrada de Pedido Limpia con Validador y Arquetipo (Prioridad: P1)
**Como** Solicitante o Desarrollador de Microservicios,  
**Quiero** ingresar los requerimientos de negocio y elegir la herramienta de construcción (Maven o Gradle) en un formulario limpio,  
**Para** que la IA sintetice directamente el contrato técnico inicial sin cuestionarios ni retrasos.

#### Criterios de Aceptación:
1. **Dado** el formulario de entrada, **Cuando** se carga la pantalla, **Entonces** todos los campos inician sin datos precargados.
2. **Dado** el llenado del formulario, **When** el usuario especifica nombre, equipo, groupId, build tool y descripción (≥ 30 caracteres), **Then** el validador en tiempo real habilita el envío.
3. **Dado** el envío del pedido, **When** se procesa la solicitud, **Then** el sistema avanza directamente al Paso 2 con el contrato OpenAPI 3.1, Historias BDD y Modelo Relacional ya sintetizados.

---

### Historia de Usuario 2 - Control 1: Contrato OpenAPI Dinámico y Revisión Viva (Prioridad: P1)
**Como** Líder Técnico o Arquitecto de Software,  
**Quiero** revisar y editar el contrato OpenAPI 3.1, las Historias de Usuario BDD y el modelo relacional, sabiendo que la IA adaptará la generación a mis cambios,  
**Para** fijar contractualmente el alcance funcional y de datos antes de generar código.

#### Criterios de Aceptación:
1. **Dado** el visor/editor de OpenAPI en YAML, **When** el usuario añade o modifica rutas, esquemas o campos, **Then** la IA interpreta dinámicamente dichos cambios para derivar la API y los DTOs.
2. **Dado** el editor de Modelo Relacional, **When** se modifican tablas, columnas o relaciones, **Then** el diagrama Mermaid y el script SQL DDL se recalculan en tiempo real.
3. **Dado** el visto bueno formal, **When** el usuario confirma la aprobación, **Then** el contrato queda inmutablemente congelado y se habilita la propuesta de arquitectura.

---

### Historia de Usuario 3 - Aprobación y Reemplazo de Extensiones Quarkus y sus Versiones (Prioridad: P1)
**Como** Desarrollador Quarkus,  
**Quiero** revisar la lista explícita de extensiones Quarkus 3.x con sus versiones exactas y poder aprobarlas, descartarlas o reemplazarlas antes de generar el código,  
**Para** mantener el control absoluto sobre las dependencias del proyecto.

#### Criterios de Aceptación:
1. **Dado** el Paso 3, **When** se presenta la arquitectura, **Then** se despliega una tabla con cada extensión Quarkus, categoría, versión (ej. `3.15.1`) y justificación técnica.
2. **Dado** el catálogo de extensiones, **When** el usuario desea ajustar una versión o reemplazar una dependencia, **Then** puede editar la versión directamente o añadir una extensión personalizada.
3. **Dado** la selección de arquitectura y confirmación de extensiones, **When** el usuario avanza, **Then** el build file (`pom.xml` o `build.gradle`) se actualiza con la selección aprobada.

---

### Historia de Usuario 4 - Construcción de Código, APIs y Modelo de Datos (Prioridad: P1)
**Como** Desarrollador Java,  
**Quiero** que el sistema genere el esqueleto, los DTOs Java 21 Records inmutables, los recursos RESTEasy Reactive y las entidades Panache basadas en el contrato revisado,  
**Para** disponer de una implementación limpia, tipada y con observabilidad corporativa.

#### Criterios de Aceptación:
1. **Dado** el contrato congelado, **When** se ejecuta la generación, **Then** todos los esquemas se convierten en Java Records inmutables con anotaciones Jakarta Validation.
2. **Dado** el modelo relacional, **When** se generan las entidades, **Then** implementan `PanacheEntityBase` con PK UUID y script Flyway en `db/migration`.

---

### Historia de Usuario 5 - Pruebas Automatizadas y Bucle Self-Healing (Prioridad: P1)
**Como** Ingeniero de Calidad (QA),  
**Quiero** ejecutar pruebas `@QuarkusTest` con RestAssured y contar con auto-corrección de errores de sintaxis y dependencias,  
**Para** garantizar una suite verde y funcional sin intervención manual para errores menores.

#### Criterios de Aceptación:
1. **Dado** el código generado, **When** se ejecutan las pruebas, **Then** se validan los endpoints del contrato obteniendo 100% de éxito.
2. **Dado** el bucle de auto-corrección (Self-Healing), **When** se detectan desajustes de tipos o imports, **Then** el sistema aplica auto-correcciones y registra el log de resolución.

---

### Historia de Usuario 6 - Code Review, Entrega DevOps y Exportación ZIP (Prioridad: P1)
**Como** Responsable de Despliegue,  
**Quiero** auditar el informe de Code Review y descargar el proyecto completo en `.ZIP`,  
**Para** disponer del repositorio listo para producción con `Jenkinsfile` y `Dockerfile`.

#### Criterios de Aceptación:
1. **Dado** el Control 2, **When** se audita el microservicio, **Then** se presenta el dictamen del Agente Revisor y el desglose de tokens.
2. **Dado** la aprobación de entrega, **When** el usuario pulsa "Descargar .ZIP", **Then** obtiene el paquete listo para ejecutar con `./mvnw quarkus:dev`.

---

### Historia de Usuario 7 - Medidor Continuo de Tokens No Restrictivo y Monitor de Avance 0-100% (Prioridad: P1)
**Como** Desarrollador / Supervisor de la Fábrica,  
**Quiero** monitorear el consumo de tokens en tiempo real sin límites artificiales (como "Modo Medio") que interrumpan o degraden la generación, con un porcentaje de progreso visible de 0% a 100% y una alerta explícita de finalización,  
**Para** saber con total precisión en qué fase se encuentra la construcción, tener certeza del momento en que finaliza y disponer de auditoría de telemetría sin bloqueos.

#### Criterios de Aceptación:
1. **Dado** la fase de construcción en Step 5, **When** se ejecutan los agentes de desarrollo y pruebas, **Then** la interfaz despliega un medidor continuo de tokens consumidos (por agente y global) con estado "Ilimitado / Continuo", sin abortar ni truncar la generación por cuotas fijas artificiales.
2. **Dado** el proceso de construcción y QA, **When** avanza cada hito (DTOs, Panache, JAX-RS, Tests, Self-Healing), **Then** una barra de progreso refleja el avance incremental de 0% a 100% en tiempo real.
3. **Dado** la culminación del 100% de la construcción y suite de pruebas, **When** finaliza el proceso, **Then** el sistema presenta un banner visible de éxito y celebración con métricas de archivos y tests, permaneciendo en la vista para su revisión antes de avanzar a la documentación.
4. **Dado** cualquier eventualidad de red o error de validación, **When** ocurre un fallo, **Then** se expone de forma inmediata un banner con el mensaje de error exacto y botón de reintento, evitando cargas silenciosas infinitas.

---

## 3. Requisitos Funcionales Detallados

* **RF-001 (Zero Defaults & Arquetipo)**: Formulario limpio con selección de Maven (`pom.xml`) o Gradle (`build.gradle`) y validación de calidad en tiempo real.
* **RF-002 (Eliminación de Módulo de Preguntas)**: Flujo directo que sintetiza el contrato sin cuestionarios ni interrupciones.
* **RF-003 (Contract-First Dinámico)**: Parser reactivo que traduce cualquier cambio del contrato OpenAPI en APIs y DTOs Java 21 Records.
* **RF-004 (Control 1 - Congelamiento Formal)**: Aprobación formal de contrato OpenAPI, 10+ HUs BDD y Modelo Relacional reactivo.
* **RF-005 (Aprobación y Reemplazo de Extensiones)**: Catálogo explícito de extensiones Quarkus 3.x con versiones editables antes de la generación.
* **RF-006 (Generación de Código Limpio)**: DTOs Java Records inmutables, Resources RESTEasy Reactive, entidades Panache y Flyway.
* **RF-007 (Pruebas Automatizadas)**: Suite `@QuarkusTest`, RestAssured y Mockito.
* **RF-008 (Bucle Self-Healing)**: Detección y auto-corrección de errores de sintaxis, dependencias y pruebas.
* **RF-009 (Code Review Automatizado)**: Informe de calidad de código con verificación de principios SOLID y scopes CDI.
* **RF-010 (Suite Documental)**: Generación obligatoria de los 5 manuales Markdown oficiales.
* **RF-011 (CI/CD y Exportación ZIP)**: Dockerfile multi-stage, Jenkinsfile corporativo y descarga directa en paquete `.ZIP`.
* **RF-012 (Medidor Continuo de Tokens No Bloqueante)**: Monitoreo en vivo de telemetría de tokens por agente bajo modalidad continua sin límites punitivos ni cortes abruptos de código.
* **RF-013 (Monitor de Progreso 0-100% y Alerta de Finalización)**: Indicador visual de avance porcentual y banner de éxito explícito al completar la construcción y pruebas QA.
* **RF-014 (Mapeo y Resiliencia ante Errores)**: Captura y despliegue transparente de excepciones en pantalla con opciones de reintento, eliminando estados de espera indefinida.
