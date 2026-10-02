"""Cost tracing for feature 013.

Emits per-call token and cost telemetry, aggregates it per session, and prices it
against the provider's published rates — so the average cost of a completed
microservice generation becomes measurable and reportable.

Structural decisions, recorded because they are load-bearing:

* **The local store is authoritative; the telemetry destination is a mirror.**
  Records are always written locally first, so the destination being unreachable
  is a non-event and the report never depends on it (FR-005).
* **Recording keys on "is recording active", never on "is this a test".** The
  wrapper is applied by the model factory while a recording context — established
  by the stage execution boundary — is active. That is true for every real session
  and false for a direct factory call, which is what keeps production covered while
  leaving the existing factory-seam tests untouched.
* **Unknown is never recorded as zero.** For tokens, for cost, and for pricing. A
  missing value is reported as missing and counted, because a zero is a claim and
  an absence is not.
"""

from app.cost.store import (  # noqa: F401
    read_all_session_cost_records,
    read_call_records,
    read_session_cost_record,
    recording_failures,
    write_call_record,
    write_session_cost_record,
)
from app.cost.pricing import (  # noqa: F401
    PricingTableError,
    is_peak,
    load_pricing_table,
    price_call,
)

__all__ = [
    "PricingTableError",
    "is_peak",
    "load_pricing_table",
    "price_call",
    "read_all_session_cost_records",
    "read_call_records",
    "read_session_cost_record",
    "recording_failures",
    "write_call_record",
    "write_session_cost_record",
]
