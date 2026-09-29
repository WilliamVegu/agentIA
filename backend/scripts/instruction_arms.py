"""Instruction arms for the prohibition experiment (P4).

**The hypothesis, and where it comes from.** *Guardrails Beat Guidance*
(arXiv:2604.11088v2), 679 rule files and 25,532 rules over 5,000+ Claude Code runs
on SWE-bench Verified, found that "every individually beneficial rule is a negative
constraint ('do not refactor unrelated code'), while every individually harmful one
is a positive directive ('follow code style')" (Fisher p=0.029). This platform's
five stage instructions are overwhelmingly positive directives -- the harmful
polarity -- so the experiment is to restate the *same* constraints as prohibitions
and measure.

**Why the arms are built by transformation rather than hand-authored.** Only the
`Rules` section differs between arms. The technology contract, output contract and
prohibitions are byte-identical, so the comparison isolates polarity and nothing
else. A hand-authored alternative set would differ in a dozen uncontrolled ways.

**Why a placebo arm exists.** The same study found rule-file gains to be largely
*content-independent* -- random, shuffled and mismatched-domain files all matched
curated ones -- which it reads as a context-priming mechanism. Any instruction
change will therefore "work" by adding priming. The placebo is length-matched to
the prohibition arm and constrains nothing, so a prohibition gain that does not
beat the placebo is a priming effect, not a polarity effect. This is the control
design of arXiv:2606.06454, which is what let that study conclude that a skill's
procedural content added no separable benefit over a labels-only scaffold.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

CONTROL_DIR = Path(__file__).resolve().parents[1] / "app" / "resources" / "instructions"

STAGES: Tuple[str, ...] = ("scaffolder", "domain", "service", "controller", "test")

ARMS: Tuple[str, ...] = ("control", "prohibition", "placebo")

#: The same constraints as the control documents, stated as prohibitions.
#:
#: Each entry mirrors the control rule at the same index. The transformation is
#: deliberately conservative -- it preserves every constraint's *content* and
#: changes only its polarity -- because a rewrite that also changed what was being
#: asked would confound polarity with scope.
PROHIBITION_RULES: Dict[str, str] = {
    "scaffolder": """1. Do not emit any artifact before reading the blueprint payload, and never let the
   service identity, the base package name, the HTTP port, or the database engine
   differ from the values it declares.
2. Do not declare dependency versions individually. Never override the Spring Boot
   starter parent at the 3.x line, which is what keeps those versions managed.
3. Do not express the Java language level as a source/target pair that could drift
   apart, and never set it to anything other than 21.
4. Do not declare any dependency absent from the allowlist, and do not pad the set
   with starters the blueprint does not require.
5. Do not configure a datasource that needs external provisioning, and do not
   require the schema to be created by hand.
6. Do not bind the server to a port other than the one the blueprint declares.
7. Do not place the application entry point outside the base package, and do not
   leave any generated layer outside component scanning.
8. Do not let the application class name and the artifact identifier disagree about
   the service identity.
""",
    "domain": """1. Do not proceed without the blueprint payload's declared entities and, for each,
   its attributes with a name, a type, and constraints.
2. Do not invent an entity the blueprint does not declare, and do not merge two
   declared entities into one.
3. Do not emit an entity with zero identifiers or with more than one. Never promote
   an arbitrary business attribute to identifier when the blueprint has not marked
   one; use a generated surrogate of integral type instead.
4. Do not map a declared attribute to a Java type that misrepresents it, and never
   widen a declared type to a universal type such as `String` merely to avoid a
   mapping decision.
5. Do not omit declarative validation from any attribute the blueprint marks as
   required or as carrying a format constraint, and do not substitute a constraint
   of a different kind than the one declared.
6. Do not apply any validation constraint the blueprint does not declare. An
   invented constraint changes the service's contract without authorisation and is
   as much a defect as a missing one.
7. Do not omit the no-argument constructor, and do not implement equality over
   mutable business attributes; identity equality is over the identifier only.
8. Do not omit either contract for an entity, and never include the identifier in
   the request contract or exclude it from the response contract.
9. Do not translate an entity into a contract anywhere but the response contract's
   static factory, and do not throw on a `null` input where the factory is
   specified to return `null`.
10. Do not emit the request contract before the response contract, and do not refer
    to an artifact that does not already exist.
""",
    "service": """1. Do not invent entities or contracts. Work only with what the scaffolding and
   domain stages already produced.
2. Do not hand-write the standard persistence operations, and do not add a derived
   query method that no acceptance scenario requires.
3. Do not emit a generic CRUD superset. Declare only the operations the blueprint's
   scenarios require, and never fewer than create, read-one, read-all, and delete.
4. Do not annotate the implementation with anything other than a Spring service
   stereotype, and do not leave an individual read operation outside a read-only
   transaction.
5. Do not construct or persist an entity without translating through the request
   contract, and do not return anything but the response contract.
6. Do not signal absence by returning `null` or an empty result. A missing resource
   must raise the dedicated not-found exception declared in the Output contract.
7. Do not return `null` from read-all when there is nothing to return, and do not
   reorder the persisted entities.
8. Do not let a branch, a validation decision, or a domain rule live in the
   repository or in a layer above the service implementation.
9. Do not duplicate field-by-field mapping logic in more than one place; translate
   exclusively through the response contract's factory and the entity's accessors.
10. Do not let the not-found exception be a checked exception, and do not omit the
    identifier that was not found from its message.
""",
    "controller": """1. Do not redeclare the service interfaces or record contracts that earlier stages
   already produced.
2. Do not bind a controller to a path other than the entity-derived collection path
   resolved under the application's versioned API root, and do not emit more than
   one controller per entity.
3. Do not emit a fixed endpoint catalogue; expose exactly the operations the
   blueprint's acceptance scenarios require.
4. Do not accept an unvalidated request body, so declarative constraints are never
   bypassed before the service is entered.
5. Do not return a status that misrepresents the outcome. Creation must not return a
   non-created status, and a missing resource must not be reported by the
   controller -- only through the global handler.
6. Do not use field injection, and do not construct the service inside a method;
   obtain it through the constructor.
7. Do not branch on domain state and do not transform data in a controller. Delegate
   in a single call and return the result.
8. Do not emit more than one global exception handler, and do not omit any of: the
   service layer's not-found exception, request-payload validation failures, or
   unhandled failures. Never let one case produce a different error structure.
9. Do not omit the root-path catalogue endpoint reporting the service identity, an
   operational status, and the exposed endpoints.
10. Do not place the global handler outside the application's base package, so that
    no controller needs to be individually registered with it.
""",
    "test": """1. Do not derive the suite from a fixed list of method names. The acceptance
   scenarios are the specification, and no scenario may go unmapped.
2. Do not write a test method that is not derived from a scenario's stated
   precondition, described action, and declared outcome, and do not name it after
   anything but the behaviour it verifies.
3. Do not omit, per entity, any of: successful creation, retrieval by identifier,
   the not-found path for a missing resource, or retrieval of the full collection.
4. Do not assert a missing resource merely by an empty result; it must be asserted
   to raise the dedicated not-found exception.
5. Do not reach for a real repository. Substitute it with a mock, inject it through
   the constructor, and verify the required interactions as well as the returned
   value.
6. Do not stub a method the test does not exercise. Unnecessary stubbing fails under
   strict stub enforcement and is reported as an error rather than a failure.
7. Do not assert a bare boolean where a fluent AssertJ assertion expresses the
   intent.
8. Do not emit a placeholder context test that always passes; the context assertion
   must be genuine.
9. Do not let a unit test require a running HTTP server or a real database.
10. Do not let the test tree diverge from the main source package layout.
""",
}

#: Neutral sentences for the placebo arm. They are process-shaped and grammatically
#: complete but constrain nothing about the artifacts, which is what makes them a
#: control for priming rather than a second treatment.
NEUTRAL_SENTENCES: Tuple[str, ...] = (
    "Consider the material you have been given before you begin.",
    "Take the time to read the whole request rather than only its first part.",
    "Work carefully and steadily through the task in front of you.",
    "Keep in mind that the person reading the result is not present with you.",
    "Think about what a careful colleague would want to know.",
    "Approach the work in the order that seems most natural to you.",
    "There is no particular hurry, and no particular order to follow.",
    "Pay attention to the details as they arise.",
    "Reflect briefly on what you have produced when you believe you are finished.",
    "Remember that clarity is generally appreciated.",
    "It is often useful to pause and reconsider before continuing.",
    "Use your judgement about the level of detail that is appropriate.",
    "Keep your work organised in whatever way you find helpful.",
    "Notice anything that seems unusual as you go.",
    "A steady, methodical approach is usually reasonable.",
    "Consider how the parts of the work relate to one another.",
    "Be aware that you are working with a limited amount of information.",
    "Take reasonable care with the material you have been given.",
    "There is no single correct way to approach this kind of work.",
    "Keep the whole shape of the task in view as you proceed.",
)


def placebo_rules(target: str) -> str:
    """Length-matched, constraint-free replacement for a Rules body.

    Matching the length matters: an unconstrained shorter text would confound
    polarity with token budget, and the whole point of the arm is to hold
    everything but content constant. Deterministic, so the arm is reproducible.
    """
    lines: List[str] = []
    index = 0
    number = 1
    while len("\n".join(lines)) < len(target):
        sentence = NEUTRAL_SENTENCES[index % len(NEUTRAL_SENTENCES)]
        lines.append(f"{number}. {sentence}")
        index += 1
        number += 1
    return "\n".join(lines) + "\n"


_RULES_BLOCK = re.compile(r"(## Rules\n)(.*?)(\n## Output contract)", re.DOTALL)


def _replace_rules(document: str, rules_body: str) -> str:
    """Swap only the Rules body, preserving every other section byte-for-byte."""
    replaced, count = _RULES_BLOCK.subn(
        lambda match: f"{match.group(1)}{rules_body}{match.group(3)}",
        document,
        count=1,
    )
    if count != 1:
        raise ValueError("the instruction document does not have the expected Rules block")
    return replaced


def build_arm(arm: str, target_dir: Path, *, control_dir: Path = CONTROL_DIR) -> Path:
    """Write one arm's five documents (plus manifest and VERSION) to ``target_dir``.

    Returns the directory. Only the Rules section differs between arms.
    """
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; expected one of {ARMS}")

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    for stage in STAGES:
        source = (control_dir / f"{stage}.md").read_text(encoding="utf-8")

        if arm == "control":
            body = source
        elif arm == "prohibition":
            body = _replace_rules(source, PROHIBITION_RULES[stage])
        else:
            # Length-matched to the TREATMENT arm, not to the control: the
            # comparison that matters is prohibition-vs-placebo, and an unconstrained
            # text of different length would confound polarity with token budget.
            body = _replace_rules(source, placebo_rules(PROHIBITION_RULES[stage]))

        (target_dir / f"{stage}.md").write_text(body, encoding="utf-8")

    # The manifest and VERSION are copied verbatim: the digest is computed over the
    # five stage documents only, so each arm's revision differs exactly by its text.
    for name in ("manifest.json", "VERSION"):
        source = control_dir / name
        if source.is_file():
            (target_dir / name).write_text(
                source.read_text(encoding="utf-8"), encoding="utf-8"
            )
    return target_dir


def arm_revision(arm_dir: Path):
    """The loader's own revision for an arm, so a run records which text it used."""
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root / "backend") not in sys.path:
        sys.path.insert(0, str(repo_root / "backend"))
    from app.orchestrator.stages.instructions import load_instruction_set

    return load_instruction_set(Path(arm_dir)).revision
