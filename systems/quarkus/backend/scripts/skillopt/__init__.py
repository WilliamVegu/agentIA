"""The SkillOpt loop (feature 014).

One iteration, one skill, no memory between runs:

    collect recorded outcomes  ->  reflect into bounded edits  ->  apply to a copy
      ->  gate both skills on the same fresh executions  ->  accept only on a
          strict improvement  ->  log one run record

Deliberately absent, and deferred to v2: the rejected-edit buffer, the textual
learning-rate schedule, the epoch-wise slow/meta update, multi-skill banks,
hierarchical merge, and statistical validation. Each is a mechanism the source
method names as contributing to *stability*; this package establishes the loop
first.
"""
