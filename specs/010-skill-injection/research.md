# Research & Technical Decisions: Skill Domain Finalization and Seed Skills Authoring

**Feature**: Finalize Skill Domain Set and Author Seed Skill Documents  
**Branch**: `010-skill-injection`  
**Date**: 2026-09-25  

---

## 1. Resolution of Open Decisions

### Decision 1: Dual Representation (Skill AND Fixer)?
- **Question**: Should any candidate domain be represented as both a skill AND a deterministic fixer (e.g., `jakarta_namespace` having a mechanical regex fixer and a semantic prompt skill)?
- **Resolution**: **Strict separation of concerns (No dual representation)**.
- **Rationale**:
  - In `reports/009-historical-baseline.md`, `jakarta_namespace` failures consist entirely of `package javax.persistence does not exist` and `package javax.validation.constraints does not exist`. In Java 21 / Spring Boot 3, replacing `javax.*` with `jakarta.*` in imports and annotations is 100% mechanical.
  - Adding a prompt skill for mechanical find-and-replace wastes LLM context window budget (violating the <2,000 token combined budget) and risks non-deterministic hallucinations on imports.
  - Similarly, `maven_pom` failures (30.0% error share) are driven by offline dependency declaration and plugin configurations, which are best repaired by deterministic XML injectors.
  - Therefore, `jakarta_namespace` and `maven_pom` are triaged **exclusively to deterministic fixers**, keeping prompt skills focused on complex semantic reasoning.

### Decision 2: Granularity (Task-Level vs. Event-Driven)?
- **Question**: Are any domains cross-cutting enough to warrant a dedicated always-on task-level skill, separate from event-driven triggers?
- **Resolution**:
  - **`layer_architecture`**: **`task-level`**. Architectural layer boundaries (Controller -> Service -> Repository -> Entity) and Record DTO immutability must be established proactively during initial code scaffolding. Retroactive repair of layer violations is expensive and complex.
  - **`exception_handling`**: **`task-level`**. Centralized `@RestControllerAdvice` and RFC 7807 `ProblemDetails` error structures must be generated alongside controllers and services rather than patched ad-hoc after build errors.
  - **`mockito_tests`**: **`event-driven`**. Mockito strict stubbing (`Strictness.STRICT_STUBS`), interaction verification (`verify`), and argument matching errors surface specifically during test synthesis and Surefire test execution in the self-repair loop. Injecting this skill when test failures are detected maximizes prompt relevance.

### Decision 3: Pilot Viability Threshold
- **Question**: If fewer than 3 domains survive as skill-layer appropriate, is the pilot still viable? What is the explicit threshold?
- **Resolution**:
  - The minimum viability threshold is established at **>= 2 surviving skill domains**.
  - *Threshold Rationale*: Building a multi-domain skill retrieval, injection policy, and slow-update layer requires architectural overhead. If only 1 domain survived, a static prompt amendment would be simpler and more cost-effective.
  - *Empirical Status*: In Task 0 (`reports/009-historical-baseline.md`), **3 domains survived** (`layer_architecture`, `exception_handling`, `mockito_tests`), accounting for 40.0% of historical failures and 60.0% of non-pom errors. The pilot comfortably exceeds the viability threshold and is **100% viable**.

---

## 2. CODESKILL Format Alignment (Figures 4-5)

### Document Structure Specification
To ensure version-freezing and compatibility with future epoch-wise slow updates:
```markdown
# Title
<High-level, reusable concept name>

## Granularity
task-level | event-driven

## When to apply
<High-level trigger condition; zero instance literals>

## Rules
1. <Procedural command>
2. <Procedural command>
...

<!-- SLOW_UPDATE_START -->
<!-- SLOW_UPDATE_END -->
```

### Key Formatting Invariants:
1. **Procedural Grammar**: Every rule starts with an active verb (e.g. *Verify*, *Extract*, *Declare*, *Inject*, *Isolate*, *Annotate*). Declarative statements (e.g. *DTOs should be records*) are prohibited.
2. **Strict Chronological Ordering**: Rules follow the exact execution sequence expected of the code generator.
3. **Zero Instance Literals**: No references to project-specific names (e.g. `agentIA`, `OrderController`, `OrderService`, `src/main/java`). Use functional roles instead: `the controller class`, `the service interface`, `the data transfer record`.
4. **Empty Slow Update Section**: The markers `<!-- SLOW_UPDATE_START -->` and `<!-- SLOW_UPDATE_END -->` must enclose zero text. This section is reserved for dynamic optimization in subsequent specifications.

---

## 3. Token Budget Analysis & Sizing

### Budget Allocation:
- **Maximum per skill**: 500 tokens.
- **Maximum combined aggregate**: 2,000 tokens.

| Skill Document | Planned Section Breakdown | Target Word Count | Estimated Token Count |
| :--- | :--- | :---: | :---: |
| `layer_architecture.md` | Title + Granularity + Trigger + 6 Procedural Rules | ~180 words | ~240 tokens |
| `exception_handling.md` | Title + Granularity + Trigger + 5 Procedural Rules | ~160 words | ~210 tokens |
| `mockito_tests.md` | Title + Granularity + Trigger + 6 Procedural Rules | ~190 words | ~250 tokens |
| **Combined Total** | **3 Seed Skills** | **~530 words** | **~700 tokens** |

*Margin of Safety*: 700 tokens represents only 35% of the 2,000 token budget, leaving ample headroom for downstream retrieval and slow-update evolution.
