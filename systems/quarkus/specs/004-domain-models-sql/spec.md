# Feature Specification: Automated Domain Models & SQL Schema Generation

**Feature Branch**: `004-domain-models-sql`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "dentro del sistema debe generar modelos y SQL."

---

## Overview

Following the design of the 4-layer software architecture, component topology, and REST API contracts (Feature 003), the system must provide automated synthesis and visual management of **Domain Entity Models** and **Relational SQL Database Schemas**. 

This capability automatically translates domain entities, attributes, data types, and business rules derived from user stories into concrete JPA/Hibernate domain models (Java 21 classes with Jakarta Persistence annotations) and compliant SQL DDL scripts (`schema.sql` and `data.sql`). It ensures high database integrity, foreign key relations, primary key generation strategies, indexes, unique constraints, and initial seed data, fully aligned with Spring Boot 3 standards and hermetic offline sandbox validation.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automated Domain Entity Model Synthesis (Priority: P1) 🎯 MVP

As a software architect or backend developer, I want the system to automatically generate clean domain entity models with strongly typed attributes, primary keys, audit fields, and JPA annotations from the architecture and specification draft, so that our data layer is consistent and ready for persistence without manual coding.

**Why this priority**: Core foundational data capability. Enables subsequent repository, service, and database interaction layers to compile and operate on formal domain structures.

**Independent Test**: Can be tested by submitting an architectural specification with domain entities (e.g. `Order`, `OrderItem`), triggering domain model synthesis, and verifying that the system outputs valid Java entity definitions with `@Entity`, `@Table`, `@Id`, typed fields, and getters/setters.

**Acceptance Scenarios**:

1. **Given** a specification draft with domain entities and attributes, **When** domain model synthesis executes, **Then** the system generates JPA domain entity models with proper Jakarta persistence annotations (`@Entity`, `@Table`, `@Id`, `@GeneratedValue`, `@Column`).
2. **Given** domain entities with business fields (e.g. monetary amounts, timestamps, status enums), **When** models are synthesized, **Then** attributes are mapped to standard Java types (`BigDecimal`, `Instant`/`LocalDateTime`, `String`, `UUID`, Enums) with field validation annotations (`@NotNull`, `@Size`, `@PositiveOrZero`).
3. **Given** domain aggregates with relationships (e.g. 1 Order to N OrderItems), **When** models are synthesized, **Then** the system establishes JPA relationship mappings (`@OneToMany`, `@ManyToOne`, `@JoinColumn`) with cascade and fetch configurations.

---

### User Story 2 - Relational SQL DDL & Seed Data Generation (Priority: P1)

As a database engineer or backend developer, I want the system to generate standard relational SQL DDL scripts (`schema.sql`) and sample seed DML scripts (`data.sql`) matching the domain models, so that the database tables, constraints, and test fixtures are automatically prepared for execution in the local/Docker environment.

**Why this priority**: Direct companion to domain models. Guarantees that the relational schema mirrors the entity models and supports hermetic offline testing (`mvn test -o`) with zero schema drift.

**Independent Test**: Can be tested by generating SQL scripts from a domain model specification and running them against an in-memory SQL database (H2 in PostgreSQL mode), verifying that all tables, primary keys, and foreign keys execute without syntax errors.

**Acceptance Scenarios**:

1. **Given** synthesized domain entity models, **When** SQL schema generation runs, **Then** the system produces a complete `schema.sql` DDL script containing `CREATE TABLE`, `PRIMARY KEY`, `FOREIGN KEY`, `UNIQUE`, and `INDEX` statements.
2. **Given** acceptance scenarios with sample initial states (Given preconditions), **When** SQL seed generation executes, **Then** the system generates a corresponding `data.sql` DML script populated with deterministic test records.
3. **Given** column definitions, **When** the DDL script is created, **Then** data types are aligned with the target database dialect (e.g. `BIGINT`, `VARCHAR`, `NUMERIC`, `TIMESTAMP WITH TIME ZONE`).

---

### User Story 3 - Visual Entity-Relationship Diagram & Interactive Review (Priority: P2)

As a solutions architect, I want an interactive visual Entity-Relationship (ER) diagram and interactive model/SQL editor in the web studio, so that I can inspect, customize fields, modify constraints, and iteratively refine data models using natural language before code generation.

**Why this priority**: Visual validation and human-in-the-loop governance. Ensures architects can review data structures, adjust column names, and refine relationships before generating project code.

**Independent Test**: Can be tested by opening the domain models view in the web studio, modifying an attribute or relationship in the UI, and verifying that both the Mermaid ER diagram and the SQL script update dynamically.

**Acceptance Scenarios**:

1. **Given** synthesized domain models, **When** viewed in the web studio, **Then** the system displays a live directional Mermaid Entity-Relationship diagram (`erDiagram`) depicting entities, attributes, primary keys, and cardinalities (`||--o{`, etc.).
2. **Given** generated SQL scripts and entity models, **When** the architect submits a natural language refinement suggestion (e.g. "add a unique constraint on email and an index on created_at"), **Then** the system updates the models, SQL DDL, and ER diagram.
3. **Given** editable model cards, **When** the architect edits column names, data types, or nullability toggles directly, **Then** the changes immediately reflect in the synchronized SQL script.

---

### User Story 4 - Model & SQL Export and Pipeline Handoff (Priority: P3)

As a developer or DevOps engineer, I want to download the generated SQL scripts and Java entity source files, and seamlessly hand off the validated data layer to the autonomous microservice code generator.

**Why this priority**: Closes the loop with downstream code generation (Feature 001) and enables standalone artifact consumption for external DB administration.

**Independent Test**: Can be tested by clicking download buttons for `schema.sql`, `data.sql`, and entity zip, and verifying that clicking "Transfer to Microservice Generator" attaches the schema and models to the active generation blueprint.

**Acceptance Scenarios**:

1. **Given** approved domain models and SQL scripts, **When** the user clicks "Download SQL Scripts", **Then** the system downloads `schema.sql` and `data.sql`.
2. **Given** approved domain entities, **When** the user clicks "Transfer to Code Generation", **Then** the system injects the full domain entity definitions and SQL initialization scripts into the microservice specification store for automated building in Feature 001.

---

### Edge Cases

- **Circular Foreign Key References**: When two entities reference each other, the system arranges DDL statements with deferred foreign keys or `ALTER TABLE ADD CONSTRAINT` to prevent creation order deadlocks.
- **Reserved SQL Keywords**: When an entity or attribute name matches an SQL reserved word (e.g. `order`, `user`, `group`), the system automatically escapes or qualifies the table/column name (e.g. `orders`, `app_user`, or quoted identifiers).
- **Composite Primary Keys & Join Tables**: When a many-to-many relationship is detected, the system automatically synthesizes an intermediate join table with compound primary key constraints.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST synthesize JPA domain entity models with strongly typed fields, numeric primary keys (`Long id` with `@GeneratedValue(strategy = GenerationType.IDENTITY)`), and Jakarta persistence annotations (`@Entity`, `@Table`, `@Id`, `@Column`) from domain specifications, mapping directly to relational `BIGINT GENERATED BY DEFAULT AS IDENTITY` primary keys.
- **FR-002**: System MUST infer and establish entity relationships (`@OneToMany`, `@ManyToOne`, `@ManyToMany`) with appropriate join columns and cascade strategies.
- **FR-003**: System MUST generate standard relational SQL DDL scripts (`schema.sql`) including table creation, primary keys, foreign keys, unique constraints, and performance indexes.
- **FR-004**: System MUST generate initial test fixtures and seed data (`data.sql`) derived from Given/When/Then acceptance scenarios.
- **FR-005**: System MUST render a visual Entity-Relationship (ER) diagram in Mermaid (`erDiagram`) reflecting entities, attributes, keys, and cardinalities in real time.
- **FR-006**: System MUST provide an interactive web interface allowing architects to view, inspect, and directly edit entity fields, types, and constraints.
- **FR-007**: System MUST provide an AI-assisted refinement loop enabling users to adjust models and SQL schemas via natural language prompts.
- **FR-008**: System MUST support downloading `schema.sql`, `data.sql`, and Java entity models.
- **FR-009**: System MUST support 1-click transfer of synthesized models and SQL scripts into the microservice code generation pipeline.
- **FR-010**: System MUST integrate the Domain Models & SQL Schema studio view as a dedicated independent sequential tab (`💾 2. Modelos de Dominio & Esquema SQL`) in the Streamlit frontend, and provide a transition button `"💾 Diseñar Modelos & SQL"` in Tab 1 that synthesizes the data models and shifts focus to Tab 2, establishing a clean pipeline: Requirements (Tab 0) ➔ Architecture (Tab 1) ➔ Domain Models & SQL (Tab 2) ➔ Ingestion & Validation (Tab 3) ➔ Generation & Logs (Tab 4).
- **FR-011**: System MUST generate standard Spring Boot SQL scripts (`schema.sql` for DDL and `data.sql` for seed DML) fully compatible with PostgreSQL and H2 in-memory mode, ensuring direct compatibility with hermetic offline test execution (`mvn test -o`).
- **FR-012**: System MUST automatically infer entity relationships (`@OneToMany`, `@ManyToOne`, `@JoinColumn`), foreign key constraints, and unique indexes from user stories and acceptance criteria, while providing interactive UI cards and fields for immediate manual review and overrides.
- **FR-013**: System MUST automatically include temporal audit fields (`createdAt` and `updatedAt` of type `Instant`) mapped to `TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP` in SQL DDL across all generated domain entities and tables.

---

### Key Entities

- **DomainEntityModel**: Represents a persistent domain entity (entity name, table name, package, fields, primary key, relationships, audit fields).
- **EntityAttribute**: Represents a field within an entity (name, column name, Java type, SQL type, nullable, primary key, unique, index).
- **EntityRelationship**: Represents an association between two entities (source, target, cardinality `ONE_TO_MANY`, `MANY_TO_ONE`, `MANY_TO_MANY`, join column, cascade type).
- **SqlSchemaDefinition**: Aggregates the generated DDL (`schema.sql`), DML (`data.sql`), target dialect, and table list.
- **DataModelSynthesisResponse**: Complete payload containing domain entities, SQL DDL, seed DML, Mermaid ER diagram, and validation status.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Domain model and SQL schema synthesis completes in under 15 seconds for specifications with 2–10 domain entities.
- **SC-002**: 100% of generated SQL DDL scripts execute cleanly without syntax errors in standard PostgreSQL and H2 databases.
- **SC-003**: 100% of domain entities include valid primary key definitions and non-conflicting column mappings.
- **SC-004**: 100% of generated entity classes adhere to Java 21 and Spring Boot 3 Jakarta persistence standards.
- **SC-005**: Architects can inspect, edit, and approve the domain models and SQL schema in under 3 minutes via the web studio.

---

## Assumptions

- Specifications originate from Feature 002 (User Stories) or Feature 003 (Architecture Design), containing identified domain entities and attributes.
- The default database dialect is PostgreSQL compatible with H2 in-memory mode for offline test execution (Constitution Principle IV).
- Lombok annotations on domain entities adhere strictly to the Constitution (`@Getter`, `@Setter`, `@Builder`, `@NoArgsConstructor`, `@AllArgsConstructor`; no `@Data`).

---

## Clarifications

### Session 2026-09-13
- Q: ¿Dónde debe ubicarse la vista interactiva de modelos de dominio y scripts SQL dentro de la aplicación Streamlit? → A: Pestaña independiente secuencial (`💾 2. Modelos de Dominio & Esquema SQL`) posicionada entre Arquitectura (Tab 1) y la Ingesta/Generación (Tab 3), creando un pipeline ordenado de extremo a extremo.
- Q: ¿Qué formato y dialecto de scripts SQL debe sintetizar el motor? → A: Scripts estándar Spring Boot (`schema.sql` y `data.sql`) compatibles con PostgreSQL y H2 en memoria, asegurando máxima compatibilidad con el sandbox hermético (`--network none`).
- Q: ¿Cómo debe determinar el sistema las relaciones entre entidades (@OneToMany, @ManyToOne, claves foráneas e índices únicos)? → A: Inferencia automática con IA a partir de las historias y entidades, complementada con tarjetas visuales interactivas en la UI para ajustes y modificaciones manuales.
- Q: ¿Cuál debe ser la estrategia predeterminada para las claves primarias y tipos de identificadores de las entidades de dominio y tablas SQL? → A: Numérico autonumérico (`Long id`) con `@GeneratedValue(strategy = GenerationType.IDENTITY)` y tipo SQL `BIGINT GENERATED BY DEFAULT AS IDENTITY`.
- Q: ¿Debe el generador incorporar automáticamente campos de auditoría temporal (created_at, updated_at) en todas las entidades de dominio y tablas SQL generadas? → A: Auditoría temporal automática: Incluir siempre `createdAt` y `updatedAt` (`Instant` / `TIMESTAMP WITH TIME ZONE`) con valores por defecto en SQL.
- Q: ¿Cómo debe activarse la transición desde la fase de arquitectura hacia el diseño de modelos de dominio y esquema SQL? → A: Botón de transición en Tab 1: Botón `"💾 Diseñar Modelos & SQL"` al final de Tab 1 que orquesta la síntesis en el backend y transfiere el foco directamente a Tab 2 con los modelos listos para inspección.

