"""Tests for the minimal resolver."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

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
from asof123.policy import SourcePolicy
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


class _StatusProvider:
    def __init__(self, name: str, status: SourceStatus) -> None:
        self.name = name
        self._status = status

    def report(self, now_utc: datetime) -> SourceStatus:
        return self._status


class _PreOpenCalendar:
    market = "XNYS"
    market_timezone = "America/New_York"

    def business_date_for(self, now_utc):
        return date(2026, 5, 12)

    def market_phase_for(self, now_utc):
        return MarketPhase.PRE_OPEN


def _publication_status(**overrides) -> SourceStatus:
    publication = {
        "publication_state": PublicationState.PUBLISHED.value,
        "canonical_state": CanonicalState.CANONICAL.value,
        "publication_utc": "2026-05-12T21:05:00Z",
        "asserted_at_utc": "2026-05-12T21:06:00Z",
    }
    publication.update(overrides)
    return SourceStatus(
        provider="official-close",
        freshness=SourceFreshness.FRESH,
        metadata={"publication": publication},
    )


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


def test_source_policy_marks_missing_required_source():
    calendar = XNYSCalendar()
    request = ResolveRequest(
        perspective=Perspective.PRE_TRADE_INTENT,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=_PRE_OPEN_UTC,
    )

    ctx = resolve(
        request,
        {"XNYS": calendar},
        policy=SourcePolicy(required_sources={"quotes_feed"}),
    )

    status = ctx.sources["quotes_feed"]
    assert status.provider == "quotes_feed"
    assert status.freshness is SourceFreshness.MISSING
    assert status.reason_code == "REQUIRED_SOURCE_MISSING"
    assert "did not report" in (status.explanation or "")


def test_source_policy_required_failed_source_does_not_become_missing():
    calendar = XNYSCalendar()
    failing = _FailingProvider("quotes_feed", "upstream timeout")
    request = ResolveRequest(
        perspective=Perspective.PRE_TRADE_INTENT,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=_PRE_OPEN_UTC,
    )

    ctx = resolve(
        request,
        {"XNYS": calendar},
        [failing],
        policy=SourcePolicy(required_sources={"quotes_feed"}),
    )

    status = ctx.sources["quotes_feed"]
    assert status.freshness is SourceFreshness.FAILED
    assert status.reason_code == "PROVIDER_REPORT_FAILED"
    assert "upstream timeout" in (status.explanation or "")


def test_source_policy_marks_replay_source_after_cutoff_not_published():
    calendar = XNYSCalendar()
    request = ResolveRequest(
        perspective=Perspective.REPLAY,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=datetime(2026, 2, 10, 21, 0, 0, tzinfo=timezone.utc),
        knowledge_cutoff_utc=datetime(2026, 2, 10, 21, 0, 0, tzinfo=timezone.utc),
    )
    provider = _StatusProvider(
        "warehouse",
        SourceStatus(
            provider="warehouse",
            freshness=SourceFreshness.FRESH,
            last_update_utc=datetime(2026, 2, 11, 1, 0, 0, tzinfo=timezone.utc),
        ),
    )

    ctx = resolve(
        request,
        {"XNYS": calendar},
        [provider],
        policy=SourcePolicy(required_sources={"warehouse"}),
    )

    status = ctx.sources["warehouse"]
    assert status.freshness is SourceFreshness.NOT_PUBLISHED
    assert status.reason_code == "SOURCE_NOT_ADMISSIBLE"
    assert "knowledge_cutoff_utc" in (status.explanation or "")


def test_source_policy_keeps_source_at_cutoff_admissible():
    calendar = XNYSCalendar()
    cutoff = datetime(2026, 2, 10, 21, 0, 0, tzinfo=timezone.utc)
    request = ResolveRequest(
        perspective=Perspective.REPLAY,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=cutoff,
        knowledge_cutoff_utc=cutoff,
    )
    provider = _StatusProvider(
        "warehouse",
        SourceStatus(
            provider="warehouse",
            freshness=SourceFreshness.FRESH,
            last_update_utc=cutoff,
        ),
    )

    ctx = resolve(
        request,
        {"XNYS": calendar},
        [provider],
        policy=SourcePolicy(required_sources={"warehouse"}),
    )

    status = ctx.sources["warehouse"]
    assert status.freshness is SourceFreshness.FRESH
    assert status.reason_code is None
    assert status.explanation is None


def test_source_policy_ignores_cutoff_and_max_age_when_last_update_missing():
    calendar = XNYSCalendar()
    cutoff = datetime(2026, 2, 10, 21, 0, 0, tzinfo=timezone.utc)
    request = ResolveRequest(
        perspective=Perspective.REPLAY,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=cutoff,
        knowledge_cutoff_utc=cutoff,
    )
    provider = _StatusProvider(
        "warehouse",
        SourceStatus(provider="warehouse", freshness=SourceFreshness.FRESH),
    )

    ctx = resolve(
        request,
        {"XNYS": calendar},
        [provider],
        policy=SourcePolicy(
            required_sources={"warehouse"},
            max_age_seconds=60,
        ),
    )

    status = ctx.sources["warehouse"]
    assert status.freshness is SourceFreshness.FRESH
    assert status.last_update_utc is None
    assert status.reason_code is None
    assert status.explanation is None


def test_source_policy_marks_old_source_stale_when_age_exceeds_threshold():
    calendar = XNYSCalendar()
    request = ResolveRequest(
        perspective=Perspective.PRE_TRADE_INTENT,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=_OPEN_UTC,
    )
    provider = _StatusProvider(
        "quotes_feed",
        SourceStatus(
            provider="quotes_feed",
            freshness=SourceFreshness.FRESH,
            last_update_utc=_OPEN_UTC - timedelta(minutes=10),
        ),
    )

    ctx = resolve(
        request,
        {"XNYS": calendar},
        [provider],
        policy=SourcePolicy(max_age_seconds=60),
    )

    status = ctx.sources["quotes_feed"]
    assert status.freshness is SourceFreshness.STALE
    assert status.reason_code == "SOURCE_STALE"
    assert "max_age_seconds=60" in (status.explanation or "")


def test_source_policy_preserves_provider_diagnostics_under_policy_metadata():
    calendar = XNYSCalendar()
    request = ResolveRequest(
        perspective=Perspective.PRE_TRADE_INTENT,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=_OPEN_UTC,
    )
    provider = _StatusProvider(
        "quotes_feed",
        SourceStatus(
            provider="quotes_feed",
            freshness=SourceFreshness.FRESH,
            last_update_utc=_OPEN_UTC - timedelta(minutes=10),
            reason_code="PROVIDER_LAGGING",
            explanation="Provider says it is behind.",
            metadata={"provider_detail": "slow partition"},
        ),
    )

    ctx = resolve(
        request,
        {"XNYS": calendar},
        [provider],
        policy=SourcePolicy(max_age_seconds=60),
    )

    status = ctx.sources["quotes_feed"]
    assert status.freshness is SourceFreshness.STALE
    assert status.reason_code == "SOURCE_STALE"
    assert status.explanation is not None
    assert status.metadata["provider_detail"] == "slow partition"
    assert status.metadata["policy"]["previous_freshness"] == "FRESH"
    assert status.metadata["policy"]["previous_reason_code"] == "PROVIDER_LAGGING"
    assert (
        status.metadata["policy"]["previous_explanation"]
        == "Provider says it is behind."
    )
    assert status.metadata["policy"]["reason_code"] == "SOURCE_STALE"


def test_source_policy_does_not_overwrite_provider_stale_status():
    calendar = XNYSCalendar()
    request = ResolveRequest(
        perspective=Perspective.PRE_TRADE_INTENT,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=_OPEN_UTC,
    )
    provider = _StatusProvider(
        "quotes_feed",
        SourceStatus(
            provider="quotes_feed",
            freshness=SourceFreshness.STALE,
            last_update_utc=_OPEN_UTC - timedelta(minutes=10),
            reason_code="PROVIDER_STALE",
            explanation="Provider reported stale data.",
        ),
    )

    ctx = resolve(
        request,
        {"XNYS": calendar},
        [provider],
        policy=SourcePolicy(max_age_seconds=60),
    )

    status = ctx.sources["quotes_feed"]
    assert status.freshness is SourceFreshness.STALE
    assert status.reason_code == "PROVIDER_STALE"
    assert status.explanation == "Provider reported stale data."
    assert "policy" not in status.metadata


def test_source_policy_live_does_not_apply_replay_cutoff_logic():
    class _MarketOpenCalendar:
        market = "XNYS"
        market_timezone = "America/New_York"

        def business_date_for(self, now_utc):
            return XNYSCalendar().business_date_for(now_utc)

        def market_phase_for(self, now_utc):
            return MarketPhase.MARKET_OPEN

    future_update = datetime(2999, 1, 1, tzinfo=timezone.utc)
    request = ResolveRequest(
        perspective=Perspective.LIVE,
        market="XNYS",
        market_timezone="America/New_York",
    )
    provider = _StatusProvider(
        "quotes_feed",
        SourceStatus(
            provider="quotes_feed",
            freshness=SourceFreshness.FRESH,
            last_update_utc=future_update,
        ),
    )

    ctx = resolve(
        request,
        {"XNYS": _MarketOpenCalendar()},
        [provider],
        policy=SourcePolicy(required_sources={"quotes_feed"}),
    )

    status = ctx.sources["quotes_feed"]
    assert status.freshness is SourceFreshness.FRESH
    assert status.reason_code is None


def test_source_policy_per_source_max_age_overrides_default():
    calendar = XNYSCalendar()
    request = ResolveRequest(
        perspective=Perspective.PRE_TRADE_INTENT,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=_OPEN_UTC,
    )
    provider = _StatusProvider(
        "quotes_feed",
        SourceStatus(
            provider="quotes_feed",
            freshness=SourceFreshness.FRESH,
            last_update_utc=_OPEN_UTC - timedelta(minutes=5),
        ),
    )

    ctx = resolve(
        request,
        {"XNYS": calendar},
        [provider],
        policy=SourcePolicy(
            max_age_seconds=60,
            max_age_seconds_by_source={"quotes_feed": 600},
        ),
    )

    status = ctx.sources["quotes_feed"]
    assert status.freshness is SourceFreshness.FRESH
    assert status.reason_code is None


def test_resolver_canonical_ready_when_single_admissible_publication_exists():
    provider = _StatusProvider("official_close", _publication_status())
    request = ResolveRequest(
        perspective=Perspective.CANONICAL,
        market="XNYS",
        market_timezone="America/New_York",
        knowledge_cutoff_utc=datetime(2026, 5, 12, 21, 6, 0, tzinfo=timezone.utc),
    )

    ctx = resolve(request, {"XNYS": _PreOpenCalendar()}, [provider])

    assert ctx.perspective is Perspective.CANONICAL
    assert ctx.publication_state is PublicationState.PUBLISHED
    assert ctx.canonical_state is CanonicalState.CANONICAL
    assert ctx.price_basis is PriceBasis.PRIOR_CLOSE
    assert ctx.reason_code is None
    assert ctx.explanation is None
    assert ctx.sources["official_close"].metadata["publication"]["canonical_state"] == "CANONICAL"


def test_resolver_canonical_fails_without_publication_assertion():
    provider = _FreshProvider("quotes_feed")
    request = ResolveRequest(
        perspective=Perspective.CANONICAL,
        market="XNYS",
        market_timezone="America/New_York",
    )

    with pytest.raises(ResolverError) as exc_info:
        resolve(
            request,
            {"XNYS": _PreOpenCalendar()},
            [provider],
            policy=SourcePolicy(required_sources={"quotes_feed"}),
        )

    assert exc_info.value.reason_code is ErrorReasonCode.PUBLICATION_METADATA_MISSING


def test_resolver_canonical_fails_when_publication_not_published():
    provider = _StatusProvider(
        "official_close",
        _publication_status(publication_state=PublicationState.PRE_PUBLISHED.value),
    )
    request = ResolveRequest(
        perspective=Perspective.CANONICAL,
        market="XNYS",
        market_timezone="America/New_York",
    )

    with pytest.raises(ResolverError) as exc_info:
        resolve(request, {"XNYS": _PreOpenCalendar()}, [provider])

    assert exc_info.value.reason_code is ErrorReasonCode.PUBLICATION_NOT_PUBLISHED


def test_resolver_canonical_fails_when_not_canonical():
    provider = _StatusProvider(
        "official_close",
        _publication_status(canonical_state=CanonicalState.PROVISIONAL.value),
    )
    request = ResolveRequest(
        perspective=Perspective.CANONICAL,
        market="XNYS",
        market_timezone="America/New_York",
    )

    with pytest.raises(ResolverError) as exc_info:
        resolve(request, {"XNYS": _PreOpenCalendar()}, [provider])

    assert exc_info.value.reason_code is ErrorReasonCode.CANONICAL_NOT_CANONICAL


def test_resolver_canonical_fails_when_multiple_assertions_exist():
    providers = [
        _StatusProvider("official_close_a", _publication_status()),
        _StatusProvider("official_close_b", _publication_status()),
    ]
    request = ResolveRequest(
        perspective=Perspective.CANONICAL,
        market="XNYS",
        market_timezone="America/New_York",
    )

    with pytest.raises(ResolverError) as exc_info:
        resolve(request, {"XNYS": _PreOpenCalendar()}, providers)

    assert exc_info.value.reason_code is ErrorReasonCode.PUBLICATION_ASSERTION_AMBIGUOUS


def test_resolver_canonical_fails_when_metadata_invalid():
    provider = _StatusProvider(
        "official_close",
        _publication_status(publication_state="FINALISH"),
    )
    request = ResolveRequest(
        perspective=Perspective.CANONICAL,
        market="XNYS",
        market_timezone="America/New_York",
    )

    with pytest.raises(ResolverError) as exc_info:
        resolve(request, {"XNYS": _PreOpenCalendar()}, [provider])

    assert exc_info.value.reason_code is ErrorReasonCode.PUBLICATION_METADATA_INVALID


def test_resolver_canonical_fails_when_assertion_after_cutoff():
    provider = _StatusProvider(
        "official_close",
        _publication_status(asserted_at_utc="2026-05-12T21:07:00Z"),
    )
    request = ResolveRequest(
        perspective=Perspective.CANONICAL,
        market="XNYS",
        market_timezone="America/New_York",
        knowledge_cutoff_utc=datetime(2026, 5, 12, 21, 6, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(ResolverError) as exc_info:
        resolve(request, {"XNYS": _PreOpenCalendar()}, [provider])

    assert exc_info.value.reason_code is ErrorReasonCode.PUBLICATION_ASSERTION_AFTER_CUTOFF


def test_resolver_canonical_fails_when_lifecycle_metadata_present():
    provider = _StatusProvider(
        "official_close",
        _publication_status(withdrawal_utc="2026-05-12T21:30:00Z"),
    )
    request = ResolveRequest(
        perspective=Perspective.CANONICAL,
        market="XNYS",
        market_timezone="America/New_York",
    )

    with pytest.raises(ResolverError) as exc_info:
        resolve(request, {"XNYS": _PreOpenCalendar()}, [provider])

    assert exc_info.value.reason_code is ErrorReasonCode.PUBLICATION_METADATA_UNSUPPORTED


def test_non_canonical_perspectives_unchanged():
    provider = _StatusProvider("official_close", _publication_status())
    request = ResolveRequest(
        perspective=Perspective.PRE_TRADE_INTENT,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=_PRE_OPEN_UTC,
    )

    ctx = resolve(request, {"XNYS": XNYSCalendar()}, [provider])

    assert ctx.perspective is Perspective.PRE_TRADE_INTENT
    assert ctx.canonical_state is CanonicalState.PROVISIONAL
    assert ctx.publication_state is PublicationState.PUBLISHED


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
