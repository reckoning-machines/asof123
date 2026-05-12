"""Internal: SourceProvider protocol and ProviderReportError.

These symbols are re-exported from `asof123.providers`. Importing this
module directly from outside the package is not part of the public API
and is not supported.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from ..models import SourceStatus


class ProviderReportError(Exception):
    """Raised when a SourceProvider cannot safely report its status.

    A provider should raise this when it has detected an unsafe or
    ambiguous condition (connection failure, partial data with no
    coverage metadata, contradictory upstream signals) and prefers to
    fail closed rather than guess a freshness value.

    The resolver layer will translate `ProviderReportError` into a
    `SourceStatus` carrying `SourceFreshness.FAILED` along with a
    `reason_code` and `explanation`, per the fail-closed rule
    (PRODUCT_CONTRACT.md section 13). Providers do not resolve
    fail-closed semantics themselves; they only signal that the
    resolver should apply them.
    """


@runtime_checkable
class SourceProvider(Protocol):
    """A read-only fact reporter for one named external source.

    Implementations must satisfy the following contract:

    - `name` is a stable, non-empty string identifier. It is the key the
      resolver uses to look the provider up and the key under which the
      provider's `SourceStatus` appears in `TemporalContext.sources`.
    - `report(now_utc)` accepts a UTC-aware `datetime` and returns a
      `SourceStatus`. The input is the resolver's notion of "now" for
      this call; providers must treat it as UTC and must not interpret
      it as wall-clock local time, must not strip its timezone, and
      must not coerce it to a different offset.
    - Providers report facts only: last update instant, publication
      state, partial or complete coverage, failure reason. They must
      not infer market phase, business date, perspective, price basis,
      publication state of unrelated datasets, or any other
      `TemporalContext` field.
    - Providers must not mutate any `TemporalContext` or `AsOfSnapshot`,
      directly or indirectly.
    - Providers must not perform scheduling, retry orchestration, or
      workflow logic. If retries are needed they belong in the caller
      or in a future resolver layer, not inside the provider.
    - When a provider cannot safely report (network failure, partial
      data, contradictory upstream signals), it should either return a
      `SourceStatus` with `SourceFreshness.FAILED` plus a populated
      `reason_code` and `explanation`, or raise `ProviderReportError`.
      It must never silently guess a `FRESH` answer.
    """

    name: str

    def report(self, now_utc: datetime) -> SourceStatus:
        ...
