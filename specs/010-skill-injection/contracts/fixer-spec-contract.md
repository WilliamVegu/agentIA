# Contract: Deterministic Fixer Specification Format

**Target Path**: `specs/010-skill-injection/fixers.md`  
**Purpose**: Provide complete engineering specifications for AST/regex post-processing fixers without implementing code yet.

---

## 1. Document Structure

The fixer specification document MUST contain:
1. **Executive Overview**: Explaining why mechanical tasks are delegated to deterministic post-processors rather than prompt skills.
2. **Execution Architecture**: Where fixers run in the generation lifecycle (e.g. post-generation, pre-compilation, or pre-repair).
3. **Fixer Entry Specifications**: For each fixer-appropriate domain (`jakarta_namespace`, `maven_pom`).

---

## 2. Fixer Entry Schema

Each fixer entry MUST specify:
- **Fixer Identifier**: Unique tag (e.g., `FIX-JAKARTA-001`, `FIX-POM-001`).
- **Target Files Pattern**: Glob pattern (e.g., `**/*.java`, `pom.xml`).
- **Detection Trigger / Pattern**: Exact regex pattern or AST condition that triggers the fix.
- **Replacement / Transformation Logic**: Exact string substitution, AST rewrite rule, or XML snippet insertion.
- **Execution Phase**: When the fixer runs (`post-generation`, `pre-build`, or `pre-repair`).
- **Verification Criterion**: How to verify the fix succeeded (e.g. absence of `javax.*` imports, offline dependency resolution).
- **Safety Boundaries**: Conditions where the fixer MUST NOT touch code (e.g. comments, non-Java files).
