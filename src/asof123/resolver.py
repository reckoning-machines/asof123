"""Minimal resolver for asof123.

Composes a `ResolveRequest`, a `Mapping[str, MarketCalendar]`, and an
`Iterable[SourceProvider]` into a `TemporalContext`. The resolver:

- looks up the calendar for the requested market and fails closed if it
  is missing or has mismatched metadata,
- determines `now_utc` from `request.as_of_utc` if present or from
  `datetime.now(timezone.utc)` otherwise,
- delegates `business_date` and `market_phase` to the calendar,
- collects each provider's `SourceStatus`, translating
  `ProviderReportError` into a `FAILED` status,
- applies a small fixed set of defaults for `price_basis`,
  `publication_state`, `canonical_state`, and `execution_state` and
  attaches `reason_code` / `explanation` whenever the contract's
  fail-closed rule (PRODUCT_CONTRACT.md section 13) requires it,
- and lets `TemporalContext`'s own validator be the final guardrail.

The resolver does no IO, no scheduling, no retries, no orchestration,
and no persistence.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Optional

from .calendar import MarketCalendar
from .enums import (
    CanonicalState,
    ExecutionState,
    MarketPhase,
    Perspective,
    PriceBasis,
    PublicationState,
    SourceFreshness,
)
from .models import SourceStatus, TemporalContext
from .providers import ProviderReportError, SourceProvider
from .requests import ResolveRequest


class ResolverError(Exception):
    """Raised when the resolver cannot safely produce a TemporalContext.

    Examples: unknown market (no calendar registered), calendar metadata
    that disagrees with the request, duplicate provider name. Per
    PRODUCT_CONTRACT.md section 13, the resolver fails closed rather
    than guess.
    """


def _resolve_price_basis(
    perspective: Perspective, market_phase: MarketPhase
) -> tuple[PriceBasis, Optional[tuple[str, str]]]:
    if (
        perspective == Perspective.LIVE
        and market_phase == MarketPhase.MARKET_OPEN
    ):
        return PriceBasis.LAST_TRADE, None
    if market_phase == MarketPhase.PRE_OPEN:
        return PriceBasis.PRIOR_CLOSE, None
    if perspective in (Perspective.PRE_TRADE_INTENT, Perspective.PREVIEW):
        return PriceBasis.PRIOR_CLOSE, None
    return PriceBasis.UNKNOWN, (
        "PRICE_BASIS_UNRESOLVED",
        f"No default price basis for perspective={perspective.value} "
        f"market_phase={market_phase.value}; minimal resolver",
    )


def _resolve_execution_state(
    perspective: Perspective,
) -> tuple[ExecutionState, Optional[tuple[str, str]]]:
    if perspective != Perspective.EXECUTED:
        return ExecutionState.NOT_EXECUTED, None
    return ExecutionState.UNKNOWN, (
        "EXECUTION_FACTS_UNAVAILABLE",
        "No execution SourceProvider supplied; minimal resolver cannot "
        "assert an execution state for perspective=EXECUTED",
    )


def resolve(
    request: ResolveRequest,
    calendars: Mapping[str, MarketCalendar],
    providers: Iterable[SourceProvider] = (),
) -> TemporalContext:
    now_utc = (
        request.as_of_utc
        if request.as_of_utc is not None
        else datetime.now(timezone.utc)
    )

    calendar = calendars.get(request.market)
    if calendar is None:
        raise ResolverError(
            f"No calendar registered for market={request.market!r}; "
            "fail-closed per PRODUCT_CONTRACT.md section 11"
        )
    if calendar.market != request.market:
        raise ResolverError(
            f"calendar.market={calendar.market!r} does not match "
            f"request.market={request.market!r}; calendar is registered "
            "under the wrong key"
        )
    if calendar.market_timezone != request.market_timezone:
        raise ResolverError(
            f"calendar.market_timezone={calendar.market_timezone!r} does not "
            f"match request.market_timezone={request.market_timezone!r}; "
            "see PRODUCT_CONTRACT.md section 11"
        )

    business_date = calendar.business_date_for(now_utc)
    market_phase = calendar.market_phase_for(now_utc)

    sources: dict[str, SourceStatus] = {}
    seen: set[str] = set()
    for provider in providers:
        if provider.name in seen:
            raise ResolverError(
                f"Duplicate provider name {provider.name!r}; "
                "each SourceProvider must have a unique name"
            )
        seen.add(provider.name)
        try:
            status = provider.report(now_utc)
        except ProviderReportError as exc:
            message = str(exc) or "ProviderReportError raised with no message"
            status = SourceStatus(
                provider=provider.name,
                freshness=SourceFreshness.FAILED,
                reason_code="PROVIDER_REPORT_FAILED",
                explanation=message,
            )
        sources[provider.name] = status

    price_basis, price_reason = _resolve_price_basis(
        request.perspective, market_phase
    )
    execution_state, execution_reason = _resolve_execution_state(
        request.perspective
    )
    canonical_state = (
        CanonicalState.CANONICAL
        if request.perspective == Perspective.CANONICAL
        else CanonicalState.PROVISIONAL
    )
    publication_state = PublicationState.PUBLISHED

    reasons = [r for r in (price_reason, execution_reason) if r is not None]
    if reasons:
        reason_code = ";".join(r[0] for r in reasons)
        explanation = " | ".join(r[1] for r in reasons)
    else:
        reason_code = None
        explanation = None

    knowledge_cutoff_utc = (
        request.knowledge_cutoff_utc
        if request.knowledge_cutoff_utc is not None
        else now_utc
    )

    return TemporalContext(
        resolved_at_utc=now_utc,
        perspective=request.perspective,
        market=request.market,
        market_timezone=request.market_timezone,
        business_date=business_date,
        market_phase=market_phase,
        knowledge_cutoff_utc=knowledge_cutoff_utc,
        price_basis=price_basis,
        execution_state=execution_state,
        publication_state=publication_state,
        canonical_state=canonical_state,
        sources=sources,
        reason_code=reason_code,
        explanation=explanation,
    )
