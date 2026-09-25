# Feature Specification: Finalize Skill Domain Set and Author Seed Skill Documents

**Feature Branch**: `010-skill-injection`

**Created**: 2026-09-25

**Status**: Draft

**Input**: User description: "Finalize skill domain set and author seed skill documents: Convert Task 0's triage output into a finalized set of hand-authored skill documents, version-frozen and ready for injection. Resolve any ambiguity in the triage classification before authoring."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Finalize and Validate Domain Triage Classifications (Priority: P1)

As an AI development lead and system architect, I want an authoritative domain classification document that reviews all candidate failure domains from the historical baseline report, resolves any classification ambiguity, and records the empirical justification for why each domain is targeted for skill injection, delegated to deterministic fixers, or dropped.

**Why this priority**: The scope and boundaries of the skill injection pilot depend strictly on this classification. Building skills for mechanical problems wastes LLM context, while building deterministic fixers for semantic problems leads to brittle regexes.

**Independent Test**: Can be independently verified by inspecting `specs/010-skill-injection/domains.md` and confirming that:
1. Every candidate domain (`jakarta_namespace`, `layer_architecture`, `exception_handling`, `maven_pom`, `mockito_tests`) is assigned an unambiguous verdict (`skill-layer appropriate`, `deterministic-fixer appropriate`, or `dropped/not observed`).
2. Every classification explicitly cites historical incident counts and percentage error shares from `reports/009-historical-baseline.md`.
3. The boundary between skill layers and deterministic fixers is clearly defined.

**Acceptance Scenarios**:

1. **Given** the Task 0 baseline report (`reports/009-historical-baseline.md`), **When** the domain triage is finalized, **Then** all 5 candidate domains have an explicit classification citing exact incident counts and failure shares.
2. **Given** the candidate domain `jakarta_namespace` (2 incidents, 10.0% error share), **When** evaluated for remediation type, **Then** it is classified as `deterministic-fixer appropriate` because package replacements (`javax.*` to `jakarta.*`) are mechanical syntactic substitutions.
3. **Given** the candidate domain `maven_pom` (6 incidents, 30.0% error share), **When** evaluated for remediation type, **Then** it is classified as `deterministic-fixer appropriate` because offline dependency caching and XML plugin configurations are mechanical.
4. **Given** the candidate domains `layer_architecture` (3 incidents, 15.0%), `exception_handling` (2 incidents, 10.0%), and `mockito_tests` (3 incidents, 15.0%), **When** evaluated for remediation type, **Then** all three are classified as `skill-layer appropriate` due to requiring multi-file semantic reasoning and architectural refactoring.

---

### User Story 2 - Author Version-Frozen Seed Skill Documents (Priority: P1)

As an autonomous code generator and prompt orchestrator, I want standardized, procedural, and version-frozen seed skill documents for each surviving skill-layer domain, so that they can be injected into code generation and test repair sessions without exceeding LLM context windows or overfitting to single tasks.

**Why this priority**: Seed skills represent the foundational knowledge assets of the pilot. They must be actionable, concise, ordered, and strictly follow the CODESKILL specification format.

**Independent Test**: Can be independently verified by inspecting each authored skill document in `backend/app/resources/skills/<domain>.md` and confirming that:
1. The file adheres strictly to the 5-section markdown structure (`# Title`, `## Granularity`, `## When to apply`, `## Rules`, and empty slow update block).
2. All rules are procedural (imperative actions) and sequentially ordered.
3. The document contains zero instance-specific literals (no class names, file paths, repository names, or variable names).
4. Each skill file is strictly under 500 tokens, and the total set is under 2,000 tokens combined.

**Acceptance Scenarios**:

1. **Given** surviving skill domains (`layer_architecture`, `exception_handling`, `mockito_tests`), **When** seed skill files are authored in `backend/app/resources/skills/`, **Then** exactly one markdown file is created per surviving domain: `layer_architecture.md`, `exception_handling.md`, `mockito_tests.md`.
2. **Given** any authored seed skill file, **When** inspected for structure, **Then** it contains `# Title`, `## Granularity` (task-level or event-driven), `## When to apply`, `## Rules` (ordered, procedural), and empty `<!-- SLOW_UPDATE_START -->` / `<!-- SLOW_UPDATE_END -->` markers.
3. **Given** any rule in an authored skill file, **When** evaluated for cross-task reusability, **Then** it contains zero repository names, file paths, class names, or specific variable names, and is grounded directly in empirical baseline data or platform constitutional principles.
4. **Given** the complete collection of authored seed skills, **When** tokenized, **Then** every individual skill is under 500 tokens and the combined aggregate is under 2,000 tokens.

---

### User Story 3 - Specify Deterministic Fixers for Mechanical Domains (Priority: P2)

As a backend engineer implementing post-processing hooks, I want a complete architectural specification of deterministic fixers for mechanical domains, so that I can implement automated AST/regex transformers in downstream tasks without needing additional design clarifications.

**Why this priority**: Triaging mechanical domains out of the LLM prompt layer requires a clear specification of how deterministic post-processors will handle those issues outside the LLM context.

**Independent Test**: Can be independently verified by reviewing `specs/010-skill-injection/fixers.md` and confirming that it provides precise regex/AST matching rules, target files, replacement syntax, and execution order for both `jakarta_namespace` and `maven_pom`.

**Acceptance Scenarios**:

1. **Given** domains classified as `deterministic-fixer appropriate` (`jakarta_namespace`, `maven_pom`), **When** the fixer specification is reviewed in `specs/010-skill-injection/fixers.md`, **Then** it details the target files, regex/AST detection patterns, substitution rules, and pipeline execution order for each fixer.
2. **Given** the fixer specification, **When** evaluated by a developer, **Then** it contains all necessary implementation guidance without including application code or modifying AgentIA runtime services during this task.

---

### User Story 4 - Synthesize Triage Decisions & Pilot Viability Summary (Priority: P3)

As an engineering manager and project stakeholder, I want an executive summary document that synthesizes the final domain counts, explains open decision resolutions, and validates the viability of the skill injection pilot.

**Why this priority**: Executive stakeholders require a concise, one-page status deliverable answering whether the pilot is viable and how key architectural trade-offs were resolved.

**Independent Test**: Can be verified by reviewing `specs/010-skill-injection/task1-summary.md` and confirming it explicitly addresses domain counts, fixer delegations, dropped domains, and the 3 open architectural decisions.

**Acceptance Scenarios**:

1. **Given** completed domain triage and seed skill authoring, **When** reviewing `specs/010-skill-injection/task1-summary.md`, **Then** it presents the final counts (3 skills, 2 fixers, 0 dropped), cites Task 0 metrics, and validates pilot viability against the minimum threshold.
2. **Given** the 3 open decisions (dual representation, granularity, viability threshold), **When** reading the summary document, **Then** each decision has an explicit, reasoned resolution.

---

### Edge Cases

- **Token Budget Overflow**: What happens if an authored skill document exceeds 500 tokens or the combined set exceeds 2,000 tokens? The skill must be ruthlessly edited for brevity, removing redundant phrasing while preserving sequential procedural rules and trigger conditions.
- **Instance-Specific Identifier Leakage**: What happens if an author inadvertently includes a specific class name (e.g. `OrderService`) or path (e.g. `src/main/java`)? The rule must be generalized to conceptual role names (e.g. `the service implementation class`, `the domain model directory`) to ensure universal cross-task transferability.
- **Contradictory Rules**: What happens if a rule within a skill contradicts another rule or the platform constitution? Every rule must be cross-verified against `.specify/memory/constitution.md` to guarantee complete alignment (e.g., verifying immutable Records for DTOs, Lombok restrictions, and layer isolation).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST create a finalized domain list artifact at `specs/010-skill-injection/domains.md` classifying all five candidate domains (`jakarta_namespace`, `layer_architecture`, `exception_handling`, `maven_pom`, `mockito_tests`) as `skill-layer appropriate`, `deterministic-fixer appropriate`, or `dropped/not observed`.
- **FR-002**: The domain list MUST cite specific empirical metrics (raw incident counts and error shares) from `reports/009-historical-baseline.md` for every classification.
- **FR-003**: The system MUST author exactly one seed skill markdown file for each surviving skill-layer domain under `backend/app/resources/skills/<domain>.md` (namely `layer_architecture.md`, `exception_handling.md`, and `mockito_tests.md`).
- **FR-004**: Each authored seed skill MUST strictly adhere to the required document structure: `# Title`, `## Granularity`, `## When to apply`, `## Rules`, and empty `<!-- SLOW_UPDATE_START -->` / `<!-- SLOW_UPDATE_END -->` markers.
- **FR-005**: All rules within seed skills MUST be phrased procedurally (actionable commands) and arranged in strict chronological/logical execution order.
- **FR-006**: Trigger conditions (`## When to apply`) MUST be formulated at a high conceptual level that reliably fires on relevant tasks while remaining generic enough to never mention specific repository names, class names, file paths, variable names, or one-off literals.
- **FR-007**: Every authored rule MUST be grounded in empirical failure patterns from `reports/009-historical-baseline.md` or normative constraints from `.specify/memory/constitution.md`.
- **FR-008**: Each authored seed skill document MUST contain fewer than 500 tokens, and the total set of surviving seed skills MUST contain fewer than 2,000 tokens in aggregate.
- **FR-009**: The system MUST create a deterministic fixer specification at `specs/010-skill-injection/fixers.md` describing the mechanical transformation rules, regex/AST patterns, and execution triggers for all domains classified as fixer-appropriate (`jakarta_namespace`, `maven_pom`).
- **FR-010**: The system MUST produce an executive summary document at `specs/010-skill-injection/task1-summary.md` detailing domain counts, surviving skills, fixer delegations, and explicit resolutions to the three open decisions (dual representation, granularity, and pilot viability threshold).
- **FR-011**: The system MUST NOT introduce any code modifications to existing AgentIA runtime services, schema changes, or LangGraph orchestration nodes during this task.

### Key Entities

- **Domain Triage Record**: Represents the formal categorization of a candidate failure domain, tracking domain identifier, display title, triage verdict (`skill`, `fixer`, `dropped`), historical incident count, error share percentage, and empirical rationale.
- **Seed Skill Document**: Represents an immutable, version-frozen markdown artifact stored in `backend/app/resources/skills/`, containing high-level title, lifecycle granularity (`task-level` or `event-driven`), transferrable trigger conditions, ordered procedural rules, and empty slow-update boundaries.
- **Deterministic Fixer Specification**: Represents a descriptive engineering artifact at `specs/010-skill-injection/fixers.md` defining automated regex/AST post-processing passes for mechanical code and build corrections.
- **Triage Summary**: Represents an executive report at `specs/010-skill-injection/task1-summary.md` synthesizing pilot scope, domain survival rates, and architectural governance decisions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of candidate domains from the historical baseline report receive an explicit, documented classification citing exact empirical counts and error percentages.
- **SC-002**: 100% of surviving skill domains have an authored seed skill markdown file adhering to the mandated 5-section CODESKILL format with zero syntax deviations.
- **SC-003**: 100% of rules within all authored skills are verified to be procedural, sequentially ordered, and free of any instance-specific literals (0 class names, 0 file paths, 0 repo names).
- **SC-004**: 100% of authored skill files individually measure below 500 tokens, and the complete set of seed skills measures below 2,000 tokens combined.
- **SC-005**: A developer can implement the deterministic post-processors specified in `fixers.md` without requiring any supplementary design decisions.
- **SC-006**: All three open architectural decisions are explicitly resolved and documented in `task1-summary.md` with unambiguous operational thresholds.

## Assumptions

- Historical data from `reports/009-historical-baseline.md` serves as the sole empirical truth for failure mode frequencies and justifications.
- Seed skill documents authored in this task are version-frozen initial baselines; slow-update dynamic refinement will be handled in subsequent specifications.
- Token counting is evaluated using standard whitespace/word approximations and cl100k tokenizer assumptions (~0.75 words per token).
- Downstream LangGraph node integration, injection policy engines, and fixer code implementations are deferred to subsequent feature specifications.
