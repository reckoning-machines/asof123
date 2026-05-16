"""Tests for the minimal resolver."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from asof123.calendars.xnys import XNYSCalendar
from asof123.enums import (
    CanonicalState,
    ExecutionState,
    MarketPhase,
    Perspective,
    PriceBasis,
    PublicationState,
    SourceFreshness,
)
from asof123.models import SourceStatus, TemporalContext
from asof123.providers import ProviderReportError
from asof123.requests import ResolveRequest
from asof123.resolver import ResolverError, resolve
from asof123.errors import ErrorReasonCode


# Reference UTC times on 2026-05-12 (Tuesday) in America/New_York.
_PRE_OPEN_UTC = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)   # 08:00 ET
_OPEN_UTC = datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc)       # 10:00 ET


class _FreshProvider:
    def __init__(self, name: str) -> None:
        self.name = name

    def report(self, now_utc: datetime) -> SourceStatus:
        return SourceStatus(
            provider=self.name,
            freshness=SourceFreshness.FRESH,
            last_update_utc=now_utc,
        )


class _FailingProvider:
    def __init__(self, name: str, message: str = "upstream unreachable") -> None:
        self.name = name
        self._message = message

    def report(self, now_utc: datetime) -> SourceStatus:
        raise ProviderReportError(self._message)


def test_live_happy_path_returns_validated_temporal_context():
    calendar = XNYSCalendar()
    provider = _FreshProvider("equities_quotes")
    request = ResolveRequest(
        perspective=Perspective.LIVE,
        market="XNYS",
        market_timezone="America/New_York",
    )

    ctx = resolve(request, {"XNYS": calendar}, [provider])

    assert isinstance(ctx, TemporalContext)
    assert ctx.market == "XNYS"
    assert ctx.market_timezone == "America/New_York"
    assert ctx.perspective is Perspective.LIVE
    assert ctx.publication_state is PublicationState.PUBLISHED
    assert ctx.canonical_state is CanonicalState.PROVISIONAL
    assert "equities_quotes" in ctx.sources
    assert ctx.sources["equities_quotes"].freshness is SourceFreshness.FRESH
    assert ctx.resolved_at_utc.utcoffset().total_seconds() == 0


def test_pre_trade_intent_pre_open_yields_prior_close_and_not_executed():
    calendar = XNYSCalendar()
    request = ResolveRequest(
        perspective=Perspective.PRE_TRADE_INTENT,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=_PRE_OPEN_UTC,
    )

    ctx = resolve(request, {"XNYS": calendar})

    assert ctx.market_phase is MarketPhase.PRE_OPEN
    assert ctx.price_basis is PriceBasis.PRIOR_CLOSE
    assert ctx.execution_state is ExecutionState.NOT_EXECUTED
    assert ctx.reason_code is None
    assert ctx.explanation is None


def test_live_market_open_with_pinned_time_yields_last_trade():
    # PRE_TRADE_INTENT during market_open also falls into the PRE_TRADE_INTENT
    # branch, so the LAST_TRADE branch needs a perspective that does not
    # short-circuit. We use a LIVE request and pin time by routing through
    # a custom calendar that always reports MARKET_OPEN, since LIVE forbids
    # as_of_utc on the request.
    class _MarketOpenCalendar:
        market = "XNYS"
        market_timezone = "America/New_York"

        def business_date_for(self, now_utc):
            return XNYSCalendar().business_date_for(now_utc)

        def market_phase_for(self, now_utc):
            return MarketPhase.MARKET_OPEN

    request = ResolveRequest(
        perspective=Perspective.LIVE,
        market="XNYS",
        market_timezone="America/New_York",
    )

    ctx = resolve(request, {"XNYS": _MarketOpenCalendar()})

    assert ctx.market_phase is MarketPhase.MARKET_OPEN
    assert ctx.price_basis is PriceBasis.LAST_TRADE
    assert ctx.execution_state is ExecutionState.NOT_EXECUTED


def test_missing_calendar_raises_resolver_error():
    request = ResolveRequest(
        perspective=Perspective.LIVE,
        market="XNYS",
        market_timezone="America/New_York",
    )
    with pytest.raises(ResolverError, match="UNKNOWN_MARKET"):
        resolve(request, {})


def test_resolver_error_exposes_stable_reason_code_and_explanation():
    request = ResolveRequest(
        perspective=Perspective.LIVE,
        market="XNYS",
        market_timezone="America/New_York",
    )
    with pytest.raises(ResolverError) as exc_info:
        resolve(request, {})

    assert exc_info.value.reason_code is ErrorReasonCode.UNKNOWN_MARKET
    assert "No calendar registered" in exc_info.value.explanation
    assert str(exc_info.value).startswith("UNKNOWN_MARKET: ")


def test_calendar_timezone_mismatch_raises_resolver_error():
    calendar = XNYSCalendar()  # America/New_York
    request = ResolveRequest(
        perspective=Perspective.LIVE,
        market="XNYS",
        market_timezone="Europe/London",
    )
    with pytest.raises(ResolverError, match="CALENDAR_TIMEZONE_MISMATCH"):
        resolve(request, {"XNYS": calendar})


def test_calendar_market_mismatch_raises_resolver_error():
    # Calendar registered under the wrong key.
    calendar = XNYSCalendar()
    request = ResolveRequest(
        perspective=Perspective.LIVE,
        market="XNAS",
        market_timezone="America/New_York",
    )
    with pytest.raises(ResolverError, match="CALENDAR_MARKET_MISMATCH"):
        resolve(request, {"XNAS": calendar})


def test_duplicate_provider_names_raise_resolver_error():
    calendar = XNYSCalendar()
    p1 = _FreshProvider("vendor_a")
    p2 = _FreshProvider("vendor_a")
    request = ResolveRequest(
        perspective=Perspective.LIVE,
        market="XNYS",
        market_timezone="America/New_York",
    )
    with pytest.raises(ResolverError, match="DUPLICATE_PROVIDER_NAME"):
        resolve(request, {"XNYS": calendar}, [p1, p2])


def test_provider_report_error_becomes_failed_source_status():
    calendar = XNYSCalendar()
    failing = _FailingProvider("vendor_b", "connection refused")
    request = ResolveRequest(
        perspective=Perspective.PRE_TRADE_INTENT,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=_PRE_OPEN_UTC,
    )

    ctx = resolve(request, {"XNYS": calendar}, [failing])

    status = ctx.sources["vendor_b"]
    assert status.freshness is SourceFreshness.FAILED
    assert status.reason_code == "PROVIDER_REPORT_FAILED"
    assert status.explanation is not None
    assert "connection refused" in status.explanation
    assert status.provider == "vendor_b"


def test_canonical_request_fails_closed_without_canonical_authority():
    calendar = XNYSCalendar()
    request = ResolveRequest(
        perspective=Perspective.CANONICAL,
        market="XNYS",
        market_timezone="America/New_York",
    )

    with pytest.raises(ResolverError, match="CANONICAL_UNSUPPORTED"):
        resolve(request, {"XNYS": calendar})


def test_executed_with_no_execution_provider_returns_unknown_with_reason():
    calendar = XNYSCalendar()
    request = ResolveRequest(
        perspective=Perspective.EXECUTED,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=_OPEN_UTC,
    )

    ctx = resolve(request, {"XNYS": calendar})

    assert ctx.execution_state is ExecutionState.UNKNOWN
    assert ctx.reason_code is not None
    assert "EXECUTION_FACTS_UNAVAILABLE" in ctx.reason_code
    assert ctx.explanation is not None
    assert "execution" in ctx.explanation.lower()


def test_resolver_returns_a_valid_temporal_context_instance():
    calendar = XNYSCalendar()
    request = ResolveRequest(
        perspective=Perspective.PRE_TRADE_INTENT,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=_PRE_OPEN_UTC,
    )
    ctx = resolve(request, {"XNYS": calendar})
    # If the resolver had assembled an invalid context, TemporalContext's
    # own model_validator would have raised before we got here.
    assert isinstance(ctx, TemporalContext)
    # Confirm the resolver carried through key request fields.
    assert ctx.resolved_at_utc == _PRE_OPEN_UTC
    assert ctx.knowledge_cutoff_utc == _PRE_OPEN_UTC
