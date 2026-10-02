# Contract — Skill Document

**Feature**: 014-skillopt-compact · **Implements**: FR-001, FR-002, FR-005

Defines the optimisable document's required shape, its protected region, and how it reaches a generation request.

---

## 1. Required structure

```markdown
# <Title>

## Granularity
task-level | event-driven

## When to apply
<the condition under which this skill is relevant>

## Rules
1. <rule>
2. <rule>

<!-- SLOW_UPDATE_START -->
<!-- SLOW_UPDATE_END -->
```

**Contract**

- All five parts MUST be present. A document missing any is **not a valid skill** and MUST be rejected at load.
- The protected markers MUST both be present, and `START` MUST precede `END`. A document missing either MUST be rejected rather than treated as having an empty protected region: a typo would otherwise silently unprotect the region and the applier would edit it.
- The document MUST be non-empty. An empty file is a load error, not a skill with no rules.
- Content between the markers is **never** editable by this feature. Nothing writes there in v1; it is honoured so that adding the deferred slow/meta update later does not require changing the edit contract.

## 2. The seed document

`layer_architecture.md`, covering controller → service → repository → model layering, hand-written and short (of the order of 250 tokens).

**Two facts that shape this requirement:**

1. **The file already exists at zero bytes**, created as a placeholder by an earlier feature that classified the domain as skill-layer appropriate but never authored content. This contract authors a file, it does not create one.
2. **The content is a placeholder.** Nothing in this feature validates its quality. A plausible-looking layering document is not validated advice, and it MUST NOT be treated as such — the loop does not care whether its seed is good, only whether it can be improved on.

## 3. The active pointer

A separate file, `active.md`, whose content names the skill in use.

| State | Required behaviour |
| --- | --- |
| Present and readable, naming a valid skill | That skill's content is prepended to the request |
| Absent | **No-op.** The request is rendered exactly as before this feature |
| Empty | No-op |
| Unreadable | No-op |
| Names a skill that does not exist | No-op, and the condition is recorded rather than raised |

**Absence is the normal state, not an error.** This is the first code to read a directory that is currently empty, on the generation path — an injection point that errored on absence would break every session the moment it shipped.

## 4. Injection

The skill's content is **prepended** to the request the stage boundary renders, alongside — not instead of — the stage's own instructions.

**Contract**

- The skill **augments** the stage instruction. It never replaces it.
- With no active skill, the rendered request MUST be **byte-identical** to the pre-feature request (SC-005). This is checkable directly against the renderer and is the regression guard for the whole feature.
- Injection MUST NOT change the stage's artifact scope, its payload, or its output contract.
- The skill's content MUST NOT be able to introduce a credential into a request by itself; the credential-shape check that guards the instruction set is not extended here, so a skill is trusted input like any other resource file, and this is recorded rather than assumed.

## 5. What this contract does not cover

- Whether the seed skill's advice is correct.
- Writing to the protected region (deferred).
- More than one skill at a time (deferred).
