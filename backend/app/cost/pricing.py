"""Pricing: load the published rate table and price a call against it.

The provider's published rates are **not two numbers per model**. They differ by
peak vs off-peak (a factor of two) and by whether the prompt was served from cache
(up to a factor of one hundred on the input side, for Flash). So the table carries
all four input rates plus output, and the basis is chosen **per call** from that
call's own timestamp and that call's own cache outcome (FR-003).

Two rules exist to keep the headline figure honest:

* A ``(provider, model)`` pair that is absent from the table is **unpriced**, with
  a ``NULL`` cost — never zero. A missing price silently becoming zero would
  understate spend (FR-009).
* When a response reports no cache breakdown, the call is priced as a full
  **cache-miss** — the upper bound — and counted. Guessing a cache *hit* would
  understate cost, which is the more dangerous error for a figure used to justify
  spend.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

RESOURCE_PATH = Path(__file__).resolve().parents[1] / "resources" / "model_pricing.json"

#: Tokens are priced per million.
_PER_MILLION = 1_000_000


class PricingTableError(RuntimeError):
    """Raised when the pricing table is missing, malformed, or uncited."""


def load_pricing_table(path: Optional[str] = None) -> Dict[str, Any]:
    """Load and validate the pricing table.

    Validation is deliberately strict: an uncited table fails to load, because the
    specification forbids recalled or estimated rates, and an off-peak value that
    is not exactly half of peak fails to load, because the cited source states
    that relationship. A malformed entry is an error rather than a silent skip, so
    a typo cannot quietly drop a model into the unpriced bucket.
    """
    table_path = Path(path) if path else RESOURCE_PATH
    if not table_path.exists():
        raise PricingTableError(f"pricing table not found: {table_path}")
    try:
        table = json.loads(table_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PricingTableError(f"pricing table is not valid JSON: {exc}") from exc

    if not table.get("source"):
        raise PricingTableError(
            "pricing table has no `source`. Rates must be fetched and cited, never recalled."
        )
    if not table.get("models"):
        raise PricingTableError("pricing table declares no models")

    for provider, models in table["models"].items():
        for model, rates in models.items():
            for basis in ("peak", "off_peak"):
                block = rates.get(basis)
                if not isinstance(block, dict):
                    raise PricingTableError(f"{provider}/{model} is missing its `{basis}` rates")
                for field in ("input_cache_hit", "input_cache_miss", "output"):
                    if field not in block:
                        raise PricingTableError(
                            f"{provider}/{model}.{basis} is missing `{field}`"
                        )
            for field in ("input_cache_hit", "input_cache_miss", "output"):
                expected_half = rates["peak"][field] / 2
                if abs(rates["off_peak"][field] - expected_half) > 1e-12:
                    raise PricingTableError(
                        f"{provider}/{model}.{field}: off-peak {rates['off_peak'][field]} is not "
                        f"half of peak {rates['peak'][field]}, which contradicts the cited source"
                    )
    return table


def _coerce_timestamp(timestamp: Any) -> datetime:
    if isinstance(timestamp, datetime):
        return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
    if isinstance(timestamp, str):
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def is_peak(timestamp: Any, table: Optional[Dict[str, Any]] = None) -> bool:
    """Whether a call at ``timestamp`` falls in the provider's peak window.

    Peak is 01:00-04:00 and 06:00-10:00 UTC, Monday-Friday. The provider's public
    holiday calendar is deliberately **not** modelled: a holiday call the provider
    prices off-peak is priced at peak here, which overstates rather than
    understates and is disclosed in the report's basis statement.
    """
    table = table or load_pricing_table()
    window = table.get("peak_window", {})
    moment = _coerce_timestamp(timestamp).astimezone(timezone.utc)

    weekdays = [day.lower() for day in window.get("weekdays", [])]
    if weekdays and moment.strftime("%A").lower() not in weekdays:
        return False

    for span in window.get("ranges", []):
        try:
            start_text, end_text = span.split("-")
            start_h, start_m = (int(part) for part in start_text.split(":"))
            end_h, end_m = (int(part) for part in end_text.split(":"))
        except ValueError:
            continue
        minutes = moment.hour * 60 + moment.minute
        if start_h * 60 + start_m <= minutes < end_h * 60 + end_m:
            return True
    return False


def _cache_hit_tokens(response_metadata: Optional[Dict[str, Any]]) -> Optional[int]:
    """Read the prompt-cache-hit token count from a response's metadata.

    The provider reports it under ``token_usage.prompt_cache_hit_tokens``. The
    platform has captured no real provider responses, so this path cannot be
    confirmed from anything in the repository; when it is absent the caller prices
    the call as a cache miss, which is the safe direction.
    """
    if not response_metadata:
        return None
    token_usage = response_metadata.get("token_usage") or {}
    value = token_usage.get("prompt_cache_hit_tokens")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def cache_hit_tokens_from_response(response: Any) -> Optional[int]:
    """Extract cache-hit input tokens from a response object, defensively.

    Accepts the real provider shape (``response_metadata.token_usage``) and the
    ``usage_metadata`` shape. Returns ``None`` when the response reports no cache
    breakdown — including for the test double, which reports none by default.
    """
    metadata = getattr(response, "response_metadata", None)
    found = _cache_hit_tokens(metadata)
    if found is not None:
        return found
    usage = getattr(response, "usage_metadata", None)
    if isinstance(usage, dict):
        details = usage.get("input_token_details") or {}
        value = details.get("cache_read")
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


def price_call(
    provider: str,
    model: str,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    timestamp: Any,
    cache_hit_input_tokens: Optional[int] = None,
    table: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Price one call. Never raises for an unknown model — it returns unpriced.

    Returns ``priced``, ``cost_usd`` (``None`` when unknown or unpriced),
    ``pricing_basis``, ``peak`` and ``cache_basis_known``.
    """
    table = table or load_pricing_table()
    peak = is_peak(timestamp, table)
    basis_name = "peak" if peak else "off_peak"

    # Usage unknown: no token counts at all. Cost is NULL, never zero.
    if input_tokens is None or output_tokens is None:
        return {
            "priced": False,
            "cost_usd": None,
            "pricing_basis": "usage-unknown",
            "peak": peak,
            "cache_basis_known": False,
        }

    rates = (table.get("models", {}).get(provider, {}) or {}).get(model)
    if not rates:
        return {
            "priced": False,
            "cost_usd": None,
            "pricing_basis": "unpriced",
            "peak": peak,
            "cache_basis_known": cache_hit_input_tokens is not None,
        }

    block = rates[basis_name]
    cache_basis_known = cache_hit_input_tokens is not None
    # No cache breakdown => price the WHOLE prompt as a cache miss (upper bound).
    cache_hit = int(cache_hit_input_tokens) if cache_basis_known else 0
    cache_hit = max(0, min(cache_hit, int(input_tokens)))
    cache_miss = int(input_tokens) - cache_hit

    input_cost = (
        cache_hit / _PER_MILLION * block["input_cache_hit"]
        + cache_miss / _PER_MILLION * block["input_cache_miss"]
    )
    output_cost = int(output_tokens) / _PER_MILLION * block["output"]

    return {
        "priced": True,
        "cost_usd": input_cost + output_cost,
        "pricing_basis": f"{basis_name}/{'cache-miss-assumed' if not cache_basis_known else 'cache-aware'}",
        "peak": peak,
        "cache_basis_known": cache_basis_known,
    }
