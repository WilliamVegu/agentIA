# Modelo de Datos: Fábrica de Microservicios Quarkus ⚡

**Característica**: `001-quarkus-agent-factory` | **Fecha**: 2026-10-01 | **Versión**: 3.0.0 | **Estado**: Implementado (Modelos Pydantic v2 en `app.models.quarkus_factory`)

---

## 1. Entidades del Dominio de la Fábrica

### 1.1 FactoryOrder (Entidad Principal del Ciclo de Vida)
Representa el pedido integral ingresado por el usuario y rastreado a través de los 7 pasos y los 2 controles humanos.

| Campo | Tipo | Obligatorio | Regla de Validación | Descripción |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `str` | Sí | Prefijo `ORD-YYYYMMDD-XXXXXX` | Identificador único del pedido |
| `status` | `OrderStatusEnum` | Sí | Enum de estados del ciclo de vida | Estado actual del ciclo de vida |
| `basic_data` | `BasicDataBlock` | Sí | Bloque 1 válido | Metadatos básicos del servicio y build tool |
| `business` | `BusinessRequirementBlock` | Sí | Bloque 2 válido | Requerimientos funcionales de negocio (≥ 30 caracteres) |
| `technical` | `TechnicalRequirementsBlock`| Sí | Bloque 3 válido | Base de datos, seguridad, Kafka |
| `ai_mode` | `AIModeBlock` | Sí | Estándar equilibrado | Configuración de modelo y tokens |
| `attachments` | `AttachmentsBlock` | Sí | Opcional | OpenAPI 3.1 o documentos de apoyo |
| `openapi_contract` | `str` | Sí | YAML OpenAPI 3.1 | Contrato de interfaz editable y congelado |
| `user_stories` | `List[UserStory]` | Sí | Mínimo 10 HUs | Historias de usuario con criterios BDD |
| `database_model` | `DatabaseModelProposal` | Sí | Esquema relacional | Tablas, columnas, relaciones, Mermaid y DDL |
| `control_1_approved` | `bool` | Sí | Booleano | Veredicto de congelamiento de contrato |
| `control_1_approval_info` | `Dict[str, Any]` | No | Quién, cuándo y comentarios | Registro de auditoría Control 1 |
| `architecture_proposal` | `ArchitectureProposal` | No | 3 opciones arquitectónicas | Propuesta técnica y previews Maven/Gradle |
| `quarkus_extensions` | `List[QuarkusExtensionItem]` | Sí | Lista con versiones | Extensiones Quarkus 3.x aprobadas/reemplazadas |
| `chosen_architecture` | `Dict[str, Any]` | No | Patrón y build tool | Arquitectura y Maven/Gradle seleccionados |
| `skeleton_generated` | `bool` | Sí | Booleano | Esqueleto automático generado |
| `code_generated` | `bool` | Sí | Booleano | Lógica Java construida |
| `tests_executed` | `bool` | Sí | Booleano | Pruebas QA ejecutadas |
| `tests_summary` | `Dict[str, Any]` | No | Total, passed, cobertura | Métricas de calidad y pruebas |
| `self_healing_log` | `List[Dict[str, Any]]` | Sí | Log de verificaciones | Detección y auto-corrección de errores |
| `code_review_report` | `Dict[str, Any]` | No | Dictamen del Agente Revisor | Auditoría estática de estándares y buenas prácticas |
| `control_2_approved` | `bool` | Sí | Booleano | Aprobación final de entrega |
| `control_2_approval_info` | `Dict[str, Any]` | No | Quién, cuándo, repo y rama | Registro de auditoría Control 2 |
| `tokens_audit` | `TokensAudit` | Sí | Desglose por agente | Consumo real vs estimado |
| `generated_files` | `Dict[str, str]` | Sí | Ruta relativa -> contenido | Árbol completo de código fuente Java 21 |
| `documentation` | `Dict[str, str]` | Sí | 5 documentos oficiales | Suite documental en Markdown |
| `devops_artifacts` | `Dict[str, str]` | Sí | Jenkinsfile, Dockerfile, PR | Entregables para CI/CD |

---

### 1.2 Entidad QuarkusExtensionItem (Aprobación y Control de Dependencias)
Representa una extensión de Quarkus 3.x con su versión explícita y metadata de control:

| Campo | Tipo | Obligatorio | Descripción |
| :--- | :--- | :---: | :--- |
| `id` | `str` | Sí | Coordenadas Maven (ej. `io.quarkus:quarkus-resteasy-reactive-jackson`) |
| `name` | `str` | Sí | Nombre legible de la extensión (ej. `RESTEasy Reactive Jackson`) |
| `version` | `str` | Sí | Versión exacta (ej. `3.15.1`) |
| `category` | `str` | Sí | Categoría: `Web & REST`, `Persistencia`, `Observabilidad`, `Seguridad`, etc. |
| `description` | `str` | Sí | Propósito técnico o justificación en el microservicio |
| `is_selected` | `bool` | Sí | Si está aprobada por el usuario para su inclusión en el build |
| `is_mandatory` | `bool` | Sí | Si es imprescindible para el runtime u observabilidad |

---

### 1.3 Bloques del Pedido de Entrada

#### Bloque 1: BasicDataBlock
* `service_name` (`str`, obligatorio): Nombre técnico kebab-case (ej. `orders-service`).
* `team` (`str`, obligatorio): Área o equipo responsable (ej. `Ventas`).
* `group_id` (`str`, obligatorio): Formato de paquete Java (ej. `com.empresa.orders`).
* `java_version` (`str`, obligatorio): `21` (LTS recomendada).
* `build_tool` (`BuildToolEnum`, obligatorio): `maven` o `gradle`.

#### Bloque 2: BusinessRequirementBlock
* `description` (`str`, obligatorio): Requerimientos de negocio con entidades, operaciones y reglas (mínimo 30 caracteres).

#### Bloque 3: TechnicalRequirementsBlock
* `database` (`DatabaseEnum`, obligatorio): `SQLite (Demo local portable)`, `SQL Server`, `Azure SQL`, `PostgreSQL`, `H2 (En memoria)`.
* `security` (`SecurityEnum`, obligatorio): `JWT (SmallRye JWT)`, `OAuth2 / OIDC`, `Sin autenticación`.
* `enable_kafka` (`bool`, obligatorio): Mensajería reactiva asíncrona.
* `integraciones` (`List[str]`): Servicios externos a consumir.

---

### 1.4 Auditoría de Tokens y Calidad

#### TokensAudit
* `estimated_range` (`[int, int]`): Rango de tokens previsto por el modo.
* `by_agent` (`Dict[str, int]`): Consumo discriminado por agente (`analista`, `arquitecto`, `desarrollador`, `qa`, `documentador`, `revisor`, `devops`).
* `total_consumed` (`int`): Suma acumulada de tokens consumidos en el pedido.

#### SelfHealingLogItem
* `step` (`str`): Paso técnico verificado (`Sintaxis y Tipos`, `Inyección CDI`, `Pruebas @QuarkusTest`).
* `status` (`str`): `PASSED` o `AUTO_CORRECTED`.
* `detail` (`str`): Explicación técnica de la validación o corrección aplicada.
* `attempts` (`int`): Intentos de auto-corrección empleados.
