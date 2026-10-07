# Contract: Instruction Document & Revision Scheme

**Feature**: LLM-Driven Generation Stages
**Date**: 2026-09-28

---

## 1. Directory layout

```text
backend/app/resources/instructions/
├── VERSION          # human-readable label + changelog pointer (reporting only)
├── manifest.json    # stage → instruction file mapping
├── scaffolder.md
├── domain.md
├── service.md
├── controller.md
└── test.md
```

**Location rationale**: follows the existing resource-loader precedent (`backend/app/resources/cve_database.json`), which is also the pattern `specs/010-skill-injection/plan.md` cites for its skills directory. This directory is deliberately **separate from `backend/app/resources/skills/`**, which the skill-injection feature owns; sharing would entangle two independent lifecycles.

---

## 2. Revision scheme

**Authoritative identifier**: a content digest over the canonicalized map of `stage → instruction content`.

| Property | Value |
|---|---|
| Algorithm | SHA-256 over the canonicalized map |
| Canonicalization | Stages sorted by name; each entry serialized as `stage + NUL + content`; content normalized for line endings before hashing |
| Serialization | Recorded as a truncated hex string |
| Scope | One revision covers all five documents — they are versioned as a set, not individually |

**Human label**: `VERSION` holds a readable label plus a changelog pointer. It is used in reports and release notes only. It is **never** the value recorded in provenance.

### Why content-addressed, not Git SHA and not a version file

| Option | Verdict |
|---|---|
| **Content digest** | **Chosen.** Changes automatically on any edit; cannot drift from the content it names; needs no runtime Git dependency. |
| Git commit SHA | Rejected: requires `.git` at runtime — session workspaces are exported and run independently of the repository — and changes on unrelated commits touching the directory, producing revision churn that makes provenance comparison noisy. |
| `VERSION` file alone | Rejected: a hand-maintained label can silently diverge from the content it claims to identify. |
| No versioning | Rejected: FR-020 requires a revision that identifies the exact instructions in force. |

---

## 3. Document format

Each instruction document is markdown with a required section sequence. Sections are named, not positional, so a reader and a parser agree.

```markdown
# <Stage name> instruction

## Technology contract
<Language version and features, framework generation, namespace conventions,
layering direction, contract immutability, validation approach, test approach.>

## Rules
1. <Imperative, ordered rule>
2. <Imperative, ordered rule>
...

## Output contract
<What artifacts to produce, and the exact workspace-relative paths they must
use. The path set is a contract, not a suggestion — out-of-scope paths are a
rejection condition.>

## Prohibitions
<What must not appear: prohibited annotations, direct layer skips, ad-hoc error
handling, new dependencies outside the allowlist, credentials.>
```

### Field-level requirements

| Section | Requirement |
|---|---|
| Technology contract | MUST state the contract explicitly. The stage must not depend on the model inferring platform conventions — this is the point of "mechanism-explicit" in the feature's origin. |
| Rules | MUST be imperative and ordered. Rules that presuppose an earlier rule MUST reference it. |
| Output contract | MUST enumerate every artifact path the stage owns. These paths are the stage's `artifact_scope` for violation attribution. |
| Prohibitions | MUST include the dependency-allowlist constraint (FR-017) and the no-credentials constraint (FR-018). |

### Content constraints

- **No credentials.** Not in rules, not in examples, not in comments (Principle VI, FR-018).
- **No instance-specific literals** in the technology contract or rules. Entity and service names arrive through the task payload, never through the instruction. An instruction containing a literal entity name would bias every session toward that name.
- **Path literals are permitted only in the Output contract** — and only as patterns, since the concrete paths are package-dependent.

---

## 4. Loading contract

| Condition | Behavior |
|---|---|
| All five documents present, digests consistent | Load succeeds; `set_revision` computed and stamped on session state. |
| Any document missing | **Fail loudly.** Never fall back to the deterministic implementation. |
| Digest mismatch across the set | **Fail loudly.** Indicates a partially-loaded or concurrently-edited set; a mixed revision must never be vended. |
| `VERSION` missing or unreadable | Warn; proceed. The label is reporting-only and is not load-bearing. |
| Instruction appears to contain a credential | Fail loudly and refuse to load. |

The "fail loudly" rule for a missing document is deliberate and is invariant 11 of `stage-execution.md`: a silent fallback would let a session report success while producing pre-migration output, corrupting every SC-001 measurement without raising an error.

---

## 5. Versioning discipline

- Instructions are versioned **as a set**. Editing one document changes the set revision, which is correct: the five documents together define the generation behavior.
- Provenance records name the set revision in force when an artifact was produced, so an artifact can always be traced to the instructions that produced it (FR-019, FR-020).
- Changing instructions during a measurement window invalidates comparison across that window. Any revision change during the pilot must be recorded, and sessions before and after must not be pooled.
