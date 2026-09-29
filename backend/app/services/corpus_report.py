"""The corpus report: how the generator actually performs (feature 015, US2).

Summarises recorded session diagnostics into the numbers the platform currently
cannot state. Three rules keep it honest, and each closes a way it could mislead.

**Excluded sessions contribute to nothing.** A session whose build fell back to a
synthetic result is not a success. Averaging one in would report achievement the
platform never had — the failure feature 012 exists to prevent. The exclusion is
stated, never silent, because a reader who cannot see the exclusions cannot judge
the figure.

**"No data" is not zero.** An empty corpus reports that there is no data rather
than a 0% rate and a $0.00 cost. The two are different findings and a reader acts
on them differently: zero invites "the generator is broken", no-data invites "run
it". This is the same discipline the cost report already applies.

**Sessions are not tasks.** Running one task ten times is one task. Presenting it
as ten observations is pseudo-replication, and it is how a corpus of five gets
described as if it were fifty. Distinct tasks are therefore counted from an
explicit label, and records without one are reported as untagged rather than
guessed at. The count is reported **twice** -- available across the whole corpus,
and verified among the sessions that back the figures -- because a reader judging
whether more evidence is worth gathering needs the first, not just the second.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Any, Dict, List, Mapping, Optional, Sequence

#: Why a session was excluded from every figure. Each is stated in the report.
EXCLUDED_UNVERIFIED = "unverified"
EXCLUDED_NOT_EVALUABLE = "not_evaluable"

#: What the report says when there is nothing to summarise.
NO_DATA_NOTICE = (
    "No sessions have been recorded.\n"
    "\n"
    "This is not a measurement of zero: there is no data. A rate of 0% and a cost\n"
    "of $0.00 would both be claims this report cannot support.\n"
    "\n"
    "Run `backend/scripts/run_corpus_baseline.py` to record a baseline, then\n"
    "re-run this report."
)


@dataclass(frozen=True)
class CorpusReport:
    #: Every recorded session, including the excluded ones.
    sessions: int
    #: Sessions whose build was actually verified: evaluable AND not synthetic.
    verified: int
    #: reason -> count. Stated, never silent.
    excluded: Dict[str, int] = field(default_factory=dict)
    #: Distinct task labels among verified sessions -- the sample that backs every
    #: derived figure.
    distinct_tasks: int = 0
    #: Distinct task labels across EVERY recorded session, including the excluded
    #: ones. The two are reported separately because they answer different
    #: questions: "how many tasks does the corpus hold" and "how many tasks back
    #: the figures". Reporting only the verified count understates the corpus to a
    #: reader judging whether more evidence is worth gathering (FR-015).
    distinct_tasks_available: int = 0
    #: Verified sessions carrying no task label. Reported rather than guessed at.
    untagged: int = 0
    #: Conformance measures of verified sessions. Listed raw: at these counts a
    #: summary statistic would imply more than the data supports.
    densities: List[float] = field(default_factory=list)
    #: Raw conformance scores of verified sessions.
    scores: List[int] = field(default_factory=list)
    #: Absolute baseline-relative penalties of verified sessions -- **the decision
    #: metric**. ``None`` entries are records written before the column existed, and
    #: are reported as ``new_penalty_measured`` rather than as zero: an unmeasured
    #: penalty of 0 would read as a clean session.
    new_penalties: List[Optional[int]] = field(default_factory=list)
    #: Model requests spent across the verified sessions.
    total_requests: int = 0
    #: Stages that needed at least one correction attempt.
    corrected_stages: int = 0
    #: Cost aggregate, or None when no cost data exists. None is NOT zero.
    cost: Optional[Dict[str, Any]] = None

    @property
    def has_data(self) -> bool:
        return self.sessions > 0

    @property
    def clean(self) -> int:
        """Verified sessions whose artifacts carried no findings."""
        return sum(1 for penalty in self._penalties if penalty == 0)

    #: Populated by build_report; kept private to avoid implying a public field.
    _penalties: tuple = ()

    @property
    def success_rate(self) -> Optional[float]:
        """Clean verified sessions over verified sessions.

        None when nothing was verified: a rate over an empty denominator is not a
        number, and reporting it as zero would read as total failure.
        """
        if self.verified == 0:
            return None
        return self.clean / self.verified

    @property
    def median_density(self) -> Optional[float]:
        return median(self.densities) if self.densities else None

    @property
    def new_penalty_measured(self) -> int:
        """How many verified sessions carry a measured baseline-relative penalty."""
        return sum(1 for value in self.new_penalties if value is not None)

    @property
    def median_new_penalty(self) -> Optional[float]:
        """Median over the sessions that actually measured it, or None."""
        measured = [float(v) for v in self.new_penalties if v is not None]
        return median(measured) if measured else None


def _optional_int(value: Any) -> Optional[int]:
    """``None`` stays ``None``: an unmeasured penalty must not become a clean zero."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_report(
    records: Sequence[Mapping[str, Any]],
    cost: Optional[Mapping[str, Any]] = None,
) -> CorpusReport:
    """Summarise recorded diagnostics. Excluded sessions enter no figure."""
    verified: List[Mapping[str, Any]] = []
    excluded: Dict[str, int] = {}
    available_tasks: set = set()

    for record in records:
        if not isinstance(record, Mapping):
            continue
        # Availability is counted before any exclusion: a task is in the corpus
        # whether or not its session could be evaluated.
        if record.get("task"):
            available_tasks.add(str(record["task"]))
        if record.get("unverified"):
            excluded[EXCLUDED_UNVERIFIED] = excluded.get(EXCLUDED_UNVERIFIED, 0) + 1
            continue
        if not record.get("evaluable", True):
            excluded[EXCLUDED_NOT_EVALUABLE] = excluded.get(EXCLUDED_NOT_EVALUABLE, 0) + 1
            continue
        verified.append(record)

    tasks = {str(r.get("task")) for r in verified if r.get("task")}
    untagged = sum(1 for r in verified if not r.get("task"))

    total_requests = 0
    corrected_stages = 0
    for record in verified:
        for stage in record.get("stages") or []:
            if not isinstance(stage, Mapping):
                continue
            attempts = stage.get("request_count") or 0
            try:
                attempts = int(attempts)
            except (TypeError, ValueError):
                continue
            total_requests += attempts
            if attempts > 1:
                corrected_stages += 1

    raw_penalties = []
    for r in verified:
        try:
            raw_penalties.append(int(r.get("raw_penalty") or 0))
        except (TypeError, ValueError):
            raw_penalties.append(0)

    report = CorpusReport(
        sessions=sum(1 for r in records if isinstance(r, Mapping)),
        verified=len(verified),
        excluded=excluded,
        distinct_tasks=len(tasks),
        distinct_tasks_available=len(available_tasks),
        untagged=untagged,
        densities=[float(r.get("density") or 0.0) for r in verified],
        scores=[int(r.get("score") or 0) for r in verified],
        new_penalties=[_optional_int(r.get("new_penalty")) for r in verified],
        total_requests=total_requests,
        corrected_stages=corrected_stages,
        cost=dict(cost) if cost else None,
    )
    object.__setattr__(report, "_penalties", tuple(raw_penalties))
    return report


def render_report(report: CorpusReport) -> str:
    """Render the report. Says 'no data' rather than implying a measured zero."""
    if not report.has_data:
        return "Corpus baseline report\n" + "=" * 62 + "\n\n" + NO_DATA_NOTICE

    lines = ["Corpus baseline report", "=" * 62, ""]
    lines.append(f"  sessions recorded        : {report.sessions}")
    lines.append(f"  verified                 : {report.verified}")
    lines.append(f"  excluded                 : {sum(report.excluded.values())}")
    for reason, count in sorted(report.excluded.items()):
        detail = {
            EXCLUDED_UNVERIFIED: "build fell back to a synthetic result",
            EXCLUDED_NOT_EVALUABLE: "nothing to evaluate",
        }.get(reason, reason)
        lines.append(f"      - {reason}: {count} ({detail})")

    lines.append("")
    lines.append(f"  distinct tasks           : {report.distinct_tasks_available} available, "
                 f"{report.distinct_tasks} verified")
    lines.append("      Available counts every labelled task in the corpus; verified")
    lines.append("      counts the tasks that back the figures below.")
    if report.untagged:
        lines.append(f"  verified but untagged    : {report.untagged} (no task label)")

    lines.append("")
    if report.verified == 0:
        lines.append("  success rate             : not measurable")
        lines.append("      Nothing was verified, so there is no denominator. This is")
        lines.append("      not a 0% success rate.")
    else:
        rate = report.success_rate
        lines.append(f"  success rate             : {rate * 100:.1f}%"
                     f"  ({report.clean} of {report.verified} verified)")
        lines.append(f"  conformance density      : {sorted(report.densities)}")
        if report.median_density is not None:
            lines.append(f"  median density           : {report.median_density:.2f}"
                         f"  (penalty per 100 artifacts; lower is better)")
        # The decision metric, printed next to the deprecated ratio so the two
        # cannot be confused for one another. Its coverage is stated because a
        # record predating the column has no value, and an absent value is not 0.
        measured = [v for v in report.new_penalties if v is not None]
        if measured:
            lines.append(
                f"  new penalty (absolute)    : {sorted(measured)}"
                f"   [{report.new_penalty_measured} of {report.verified} verified measured]"
            )
        elif report.verified:
            lines.append(
                "  new penalty (absolute)    : not measured for any verified session"
            )
        lines.append("")
        lines.append(f"  model requests           : {report.total_requests}")
        lines.append(f"  stages needing correction: {report.corrected_stages}")

    lines.append("")
    if report.cost is None:
        lines.append("  cost                     : no data")
        lines.append("      No cost was recorded. This is not a cost of zero.")
    elif report.cost.get("calls_priced", 0) == 0:
        lines.append(f"  cost                     : {report.cost.get('calls', 0)} calls, "
                     f"none priced")
        lines.append("      Calls were recorded but none could be priced. That is not")
        lines.append("      a cost of zero.")
    else:
        total = report.cost.get("total_usd") or 0.0
        lines.append(f"  cost                     : ${total:.4f}"
                     f"  ({report.cost['calls_priced']} priced calls)")
        if report.cost.get("input_tokens") is not None:
            lines.append(f"      tokens                 : "
                         f"{report.cost['input_tokens']:,} in / "
                         f"{report.cost['output_tokens']:,} out")
        if report.cost["calls_priced"] != report.cost.get("calls"):
            lines.append(f"      {report.cost['calls'] - report.cost['calls_priced']} call(s) "
                         f"could not be priced and are excluded from the total")

    lines.append("")
    lines.append("  Note: excluded sessions contribute to no figure above.")
    return "\n".join(lines)
