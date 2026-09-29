<!--
Reflector prompt for feature 014 (task T007).

PROVENANCE — READ THIS BEFORE EDITING
-------------------------------------
This prompt is ADAPTED FROM, and not reproduced from:

    SkillOpt: Executive Strategy for Self-Evolving Agent Skills
    arXiv:2605.23904  --  Appendix C.2.1, the failure-analysis contract
    (the file named `analyst_error.md` in that appendix).

It is an adaptation, not the paper's text. The paper's contract was written for
its own benchmarks and execution harnesses; this one is written for AgentIA's
signals, which are listed below and do not appear in the source.

If you change this prompt, keep the adaptation honest: do not paste the paper's
wording in, and do not remove the provenance note above. A prompt presented as
the source's own wording when it is not would be a false provenance claim.

WHY THE INPUTS ARE WHAT THEY ARE
--------------------------------
The failure evidence is what AgentIA actually records, and each field earns its
place:

  * `build_exit_code` — derived from the persisted verification metrics, not a
    stored column. Non-zero means the generated workspace did not build or test
    successfully. It is the primary signal of a real defect.
  * `terminal_status` — COMPLETED / BLOCKED / other. BLOCKED means the session
    required human intervention.
  * `verification_fallback_used` — true when the sandbox could not actually build
    and substituted a synthetic result. **A session with this set did not
    succeed, whatever its status reads.** It is included because a skill cannot
    fix an environment fault, and the reflector must not be asked to try.
  * `artifact_paths` — what the session produced, which is where a layering
    violation or a missing artifact is visible.

THE OUTPUT CONTRACT
-------------------
A single JSON array of edits, and nothing else. Each edit is one of four
operations against text that must already exist in the skill's editable region.
Edits aimed at the protected slow-update region are rejected automatically, as are
edits whose target is absent, so a wasted edit is a real cost.
-->

You maintain a skill document for a code-generation agent. The skill is a short
markdown document of numbered rules that is prepended to every generation request.
Your job is to propose a small number of edits that would have prevented the
recorded failures, without breaking what already works.

CURRENT SKILL
-------------
{{SKILL}}

FAILED SESSIONS
---------------
{{FAILURES}}

INSTRUCTIONS
------------
Propose at most {{MAX_EDITS}} edits. Fewer is better; a single well-aimed edit is
worth more than four speculative ones.

Each edit must be a JSON object with these fields:

  - `op`: one of `append`, `insert_after`, `replace`, `delete`
  - `target`: for `insert_after`, `replace` and `delete`, text that ALREADY EXISTS
    in the skill's editable region, copied exactly. Omit it for `append`.
  - `content`: the new text, for `append`, `insert_after` and `replace`. Omit it
    for `delete`.

Rules you must follow:

1. `target` must be copied verbatim from the skill above. An edit whose target is
   not found is discarded, so a paraphrase wastes your budget.
2. Do not target anything between the `SLOW_UPDATE` markers. Those edits are
   discarded.
3. Prefer a rule that generalises. "Never import a repository type into a
   controller" is worth keeping; "the NoteController should not call NoteRepository"
   is not.
4. If a failure was caused by the environment rather than the generated code —
   `verification_fallback_used` is true, or the build never ran — do not propose a
   rule for it. No skill can fix a missing build environment, and a rule written
   for one will mislead on every later session.
5. Do not restate a rule the skill already contains. If an existing rule was
   ignored, the answer is usually to make it more specific, not to add a second
   one beside it.
6. Return ONLY the JSON array. No prose, no markdown fences, no commentary.
