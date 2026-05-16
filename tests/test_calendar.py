"""Tests for the MarketCalendar protocol and the XNYSCalendar reference."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from asof123.calendar import MarketCalendar
from asof123.calendars.xnys import XNYSCalendar
from asof123.enums import MarketPhase


# Reference times. 2026-05-12 is a Tuesday.
# America/New_York is on EDT (UTC-4) in May.
# 09:30 ET == 13:30 UTC; 16:00 ET == 20:00 UTC.
_TUESDAY = date(2026, 5, 12)
_PRE_OPEN_UTC = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)   # 08:00 ET
_OPEN_UTC = datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc)       # 10:00 ET
_POST_CLOSE_UTC = datetime(2026, 5, 12, 21, 0, 0, tzinfo=timezone.utc)  # 17:00 ET
_SATURDAY_UTC = datetime(2026, 5, 9, 14, 0, 0, tzinfo=timezone.utc)
_NEW_YEARS_UTC = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)


def test_xnys_conforms_to_market_calendar_protocol():
    cal = XNYSCalendar()
    assert isinstance(cal, MarketCalendar)
    assert cal.market == "XNYS"
    assert cal.market_timezone == "America/New_York"


def test_xnys_weekday_pre_open():
    cal = XNYSCalendar()
    assert cal.market_phase_for(_PRE_OPEN_UTC) is MarketPhase.PRE_OPEN


def test_xnys_weekday_market_open():
    cal = XNYSCalendar()
    assert cal.market_phase_for(_OPEN_UTC) is MarketPhase.MARKET_OPEN


def test_xnys_weekday_post_close():
    cal = XNYSCalendar()
    assert cal.market_phase_for(_POST_CLOSE_UTC) is MarketPhase.POST_CLOSE


def test_xnys_weekend_returns_weekend():
    cal = XNYSCalendar()
    assert cal.market_phase_for(_SATURDAY_UTC) is MarketPhase.WEEKEND


def test_xnys_known_holiday_returns_holiday():
    cal = XNYSCalendar()
    assert cal.market_phase_for(_NEW_YEARS_UTC) is MarketPhase.HOLIDAY


def test_xnys_known_unsupported_early_close_fails_closed():
    cal = XNYSCalendar()
    # 2026-11-27 is the Friday after Thanksgiving, a known early-close date.
    # The reference calendar does not model shortened sessions, so it fails
    # closed instead of applying regular-session rules.
    utc = datetime(2026, 11, 27, 19, 0, 0, tzinfo=timezone.utc)  # 14:00 ET
    assert cal.market_phase_for(utc) is MarketPhase.CLOSED


def test_xnys_outside_supported_holiday_years_fails_closed():
    cal = XNYSCalendar()
    utc = datetime(2027, 5, 12, 14, 0, 0, tzinfo=timezone.utc)
    assert cal.market_phase_for(utc) is MarketPhase.CLOSED


def test_xnys_business_date_in_market_timezone():
    cal = XNYSCalendar()
    assert cal.business_date_for(_OPEN_UTC) == _TUESDAY


def test_xnys_business_date_late_utc_crosses_into_next_local_day():
    cal = XNYSCalendar()
    # 04:00 UTC on May 13 == 00:00 EDT on May 13, so business_date is May 13.
    utc = datetime(2026, 5, 13, 4, 0, 0, tzinfo=timezone.utc)
    assert cal.business_date_for(utc) == date(2026, 5, 13)


def test_xnys_dst_spring_forward_day_is_deterministic():
    cal = XNYSCalendar()
    # 2026-03-09 is the first Monday after US DST starts in 2026.
    pre_open = datetime(2026, 3, 9, 13, 0, 0, tzinfo=timezone.utc)  # 09:00 ET
    open_time = datetime(2026, 3, 9, 14, 0, 0, tzinfo=timezone.utc)  # 10:00 ET
    assert cal.business_date_for(pre_open) == date(2026, 3, 9)
    assert cal.market_phase_for(pre_open) is MarketPhase.PRE_OPEN
    assert cal.market_phase_for(open_time) is MarketPhase.MARKET_OPEN


def test_xnys_dst_fall_back_day_is_deterministic():
    cal = XNYSCalendar()
    # 2026-11-02 is the first Monday after US DST ends in 2026.
    pre_open = datetime(2026, 11, 2, 14, 0, 0, tzinfo=timezone.utc)  # 09:00 ET
    open_time = datetime(2026, 11, 2, 15, 0, 0, tzinfo=timezone.utc)  # 10:00 ET
    assert cal.business_date_for(pre_open) == date(2026, 11, 2)
    assert cal.market_phase_for(pre_open) is MarketPhase.PRE_OPEN
    assert cal.market_phase_for(open_time) is MarketPhase.MARKET_OPEN


def test_xnys_naive_datetime_rejected():
    cal = XNYSCalendar()
    naive = datetime(2026, 5, 12, 14, 0, 0)
    with pytest.raises(ValueError):
        cal.market_phase_for(naive)


def test_xnys_non_utc_aware_datetime_rejected():
    cal = XNYSCalendar()
    plus_two = datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    with pytest.raises(ValueError):
        cal.market_phase_for(plus_two)


def test_xnys_business_date_also_rejects_naive():
    cal = XNYSCalendar()
    with pytest.raises(ValueError):
        cal.business_date_for(datetime(2026, 5, 12, 14, 0, 0))
