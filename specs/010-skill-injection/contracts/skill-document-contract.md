# Contract: Seed Skill Markdown Document Format

**Standard Reference**: CODESKILL Figures 4-5  
**Target Path**: `backend/app/resources/skills/<domain_key>.md`  

---

## 1. Required Document Structure

Every seed skill markdown file MUST strictly adhere to this exact 5-section sequence without deviation:

```markdown
# <Title>

## Granularity
<task-level | event-driven>

## When to apply
<Trigger condition>

## Rules
1. <Actionable procedural rule>
2. <Actionable procedural rule>
3. <Actionable procedural rule>
...

<!-- SLOW_UPDATE_START -->
<!-- SLOW_UPDATE_END -->
```

---

## 2. Section Specifications

### 2.1 `# <Title>`
- Level 1 markdown header.
- Short, conceptual, reusable name.
- Prohibited: Repository names, class names, file paths, variable names, or one-off literals.
- Examples:
  - ✅ `# Architectural Layer Isolation`
  - ✅ `# Centralized Exception Handling`
  - ✅ `# Mockito Test Synthesis and Stubbing Correctness`
  - ❌ `# OrderController and OrderService Layer Rules`
  - ❌ `# AgentIA Fixes in src/main/java`

### 2.2 `## Granularity`
- Level 2 markdown header.
- Exactly one value: either `task-level` or `event-driven`.
  - `task-level`: Injected at task initialization / code generation time.
  - `event-driven`: Injected conditionally upon observing test failures or repair iterations.

### 2.3 `## When to apply`
- Level 2 markdown header.
- High-level, transferable trigger condition.
- Broad enough to fire on unseen domain tasks; specific enough not to fire universally on every prompt.
- Must not reference specific file paths, package strings, or project classes.

### 2.4 `## Rules`
- Level 2 markdown header.
- Sequential numbered list: `1.`, `2.`, `3.`, etc.
- Every rule MUST begin with an imperative action verb (e.g., *Verify*, *Extract*, *Declare*, *Inject*, *Isolate*, *Annotate*, *Configure*).
- Rules must be chronologically ordered. If rule 3 presupposes rule 2, it must explicitly reference rule 2.
- Zero instance-specific identifiers. Grounded 100% in empirical failure data or platform constitution.

### 2.5 Slow Update Markers
- HTML comments:
  ```markdown
  <!-- SLOW_UPDATE_START -->
  <!-- SLOW_UPDATE_END -->
  ```
- Must be empty for seed skills (no characters or whitespace between the start and end comments).
- Reserved for future epoch-wise optimization passes.

---

## 3. Token Budget Limits

- **Individual Skill Maximum**: 500 tokens.
- **Combined Collection Maximum**: 2,000 tokens across all seed skills.
