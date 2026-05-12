"""MarketCalendar protocol for asof123.

A `MarketCalendar` answers two questions about a UTC instant in the
context of a specific market:

- which business date does the instant belong to in that market's
  timezone (`business_date_for`), and
- which `MarketPhase` is the market in at that instant
  (`market_phase_for`).

Implementations must take UTC-aware datetimes only. Naive datetimes and
non-UTC tz-aware datetimes must be rejected; the calendar does not
guess wall-clock offsets. This mirrors the same UTC discipline enforced
by the request and response models (PRODUCT_CONTRACT.md section 12).

This module defines the protocol only. Concrete calendars live under
`asof123.calendars`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, runtime_checkable

from .enums import MarketPhase


@runtime_checkable
class MarketCalendar(Protocol):
    """A read-only calendar for one named market.

    Implementations must satisfy the following contract:

    - `market` is the market code (for example `"XNYS"`) and must match
      the value used in `TemporalContext.market` and `ResolveRequest.market`.
    - `market_timezone` is the IANA Region/City identifier (for example
      `"America/New_York"`) used to interpret the market's session.
    - `business_date_for(now_utc)` accepts a UTC-aware datetime and
      returns the calendar date in the market's timezone that the
      instant belongs to. Implementations may refine this to roll
      weekends or holidays to the next or prior business day; the
      minimal contract is "the date in market_timezone".
    - `market_phase_for(now_utc)` accepts a UTC-aware datetime and
      returns one of the values in `MarketPhase`.

    Both methods must reject naive datetimes and non-UTC tz-aware
    datetimes by raising `ValueError`.
    """

    market: str
    market_timezone: str

    def business_date_for(self, now_utc: datetime) -> date:
        ...

    def market_phase_for(self, now_utc: datetime) -> MarketPhase:
        ...
