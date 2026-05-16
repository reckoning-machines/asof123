"""Minimal XNYS (NYSE) reference calendar.

This is the smallest reference calendar that satisfies the
`MarketCalendar` protocol. It covers regular weekday sessions, weekends,
and a small hard-coded holiday set for 2025-2026. It does not model
full early-close sessions, half-days, ad hoc closures, or full holiday
calendars. Known unsupported early-close dates and dates outside the
supported holiday years fail closed as `CLOSED`.
Full exchange-calendar coverage is out of scope for the open-source
minimum slice; downstream callers that need it should plug in a richer
implementation against the protocol.

UTC discipline (PRODUCT_CONTRACT.md section 12) is enforced via
`asof123.models._require_utc`. The calendar does not guess wall-clock
offsets, does not accept naive datetimes, and does not silently coerce
non-UTC tz-aware inputs.
"""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from ..enums import MarketPhase
from ..models import _require_utc

_OPEN_TIME = time(9, 30)
_CLOSE_TIME = time(16, 0)
_SUPPORTED_YEARS: frozenset[int] = frozenset({2025, 2026})

# Small hard-coded NYSE holiday set, sufficient for tests.
# 2025 and 2026 only. Not a full exchange calendar.
_HOLIDAYS: frozenset[date] = frozenset(
    {
        # 2025
        date(2025, 1, 1),    # New Year's Day
        date(2025, 1, 20),   # Martin Luther King Jr. Day
        date(2025, 2, 17),   # Presidents' Day
        date(2025, 4, 18),   # Good Friday
        date(2025, 5, 26),   # Memorial Day
        date(2025, 6, 19),   # Juneteenth
        date(2025, 7, 4),    # Independence Day
        date(2025, 9, 1),    # Labor Day
        date(2025, 11, 27),  # Thanksgiving Day
        date(2025, 12, 25),  # Christmas Day
        # 2026
        date(2026, 1, 1),    # New Year's Day
        date(2026, 1, 19),   # Martin Luther King Jr. Day
        date(2026, 2, 16),   # Presidents' Day
        date(2026, 4, 3),    # Good Friday
        date(2026, 5, 25),   # Memorial Day
        date(2026, 6, 19),   # Juneteenth
        date(2026, 7, 3),    # Independence Day (observed; Jul 4 is Sat)
        date(2026, 9, 7),    # Labor Day
        date(2026, 11, 26),  # Thanksgiving Day
        date(2026, 12, 25),  # Christmas Day
    }
)

# Known XNYS early-close dates inside the supported 2025-2026 slice. The
# minimal reference calendar does not model shortened sessions, so these fail
# closed instead of pretending regular 09:30-16:00 rules apply.
_UNSUPPORTED_EARLY_CLOSES: frozenset[date] = frozenset(
    {
        date(2025, 7, 3),
        date(2025, 11, 28),
        date(2025, 12, 24),
        date(2026, 11, 27),
        date(2026, 12, 24),
    }
)


class XNYSCalendar:
    """Minimal NYSE / America/New_York reference calendar.

    Phases:
    - Saturday or Sunday in market_timezone -> `WEEKEND`.
    - Date outside the supported holiday years -> `CLOSED`.
    - Date in `_HOLIDAYS` -> `HOLIDAY`.
    - Known unsupported early-close date -> `CLOSED`.
    - Otherwise, before 09:30 ET -> `PRE_OPEN`,
      09:30 ET until before 16:00 ET -> `MARKET_OPEN`,
      at or after 16:00 ET -> `POST_CLOSE`.
    """

    market: str = "XNYS"
    market_timezone: str = "America/New_York"

    def business_date_for(self, now_utc: datetime) -> date:
        return self._to_local(now_utc).date()

    def market_phase_for(self, now_utc: datetime) -> MarketPhase:
        local = self._to_local(now_utc)
        if local.weekday() >= 5:
            return MarketPhase.WEEKEND
        if local.year not in _SUPPORTED_YEARS:
            return MarketPhase.CLOSED
        if local.date() in _HOLIDAYS:
            return MarketPhase.HOLIDAY
        if local.date() in _UNSUPPORTED_EARLY_CLOSES:
            return MarketPhase.CLOSED
        local_t = local.time()
        if local_t < _OPEN_TIME:
            return MarketPhase.PRE_OPEN
        if local_t < _CLOSE_TIME:
            return MarketPhase.MARKET_OPEN
        return MarketPhase.POST_CLOSE

    def _to_local(self, now_utc: datetime) -> datetime:
        _require_utc(now_utc, "now_utc")
        return now_utc.astimezone(ZoneInfo(self.market_timezone))
