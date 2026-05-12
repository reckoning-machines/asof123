"""Tests pinning every enumeration to its contract values."""

from __future__ import annotations

from asof123.enums import (
    CanonicalState,
    DEFAULT_CANONICAL_STATE,
    DEFAULT_EXECUTION_STATE,
    DEFAULT_MARKET_PHASE,
    DEFAULT_PRICE_BASIS,
    DEFAULT_PUBLICATION_STATE,
    ExecutionState,
    MarketPhase,
    Perspective,
    PriceBasis,
    PublicationState,
    SourceFreshness,
)


def _values(enum_cls) -> set[str]:
    return {m.value for m in enum_cls}


def test_perspective_values_match_contract():
    assert _values(Perspective) == {
        "PREVIEW",
        "PRE_TRADE_INTENT",
        "LIVE",
        "EXECUTED",
        "CANONICAL",
        "REPLAY",
        "HISTORICAL",
    }


def test_market_phase_values_match_contract():
    assert _values(MarketPhase) == {
        "PRE_OPEN",
        "MARKET_OPEN",
        "POST_CLOSE",
        "WEEKEND",
        "HOLIDAY",
        "CLOSED",
    }


def test_source_freshness_values_match_contract():
    assert _values(SourceFreshness) == {
        "FRESH",
        "STALE",
        "MISSING",
        "FAILED",
        "PRIOR_CLOSE",
        "PARTIAL",
        "PUBLISHED",
        "NOT_PUBLISHED",
    }


def test_execution_state_values_match_contract():
    assert _values(ExecutionState) == {
        "NOT_EXECUTED",
        "INTENDED",
        "WORKING",
        "PARTIALLY_FILLED",
        "FILLED",
        "CANCELED",
        "REJECTED",
        "UNKNOWN",
    }


def test_price_basis_values_match_contract():
    assert _values(PriceBasis) == {
        "PRIOR_CLOSE",
        "LAST_TRADE",
        "INDICATIVE",
        "OFFICIAL_CLOSE",
        "SETTLEMENT",
        "MODEL",
        "UNKNOWN",
    }


def test_publication_state_values_match_contract():
    assert _values(PublicationState) == {
        "NOT_PUBLISHED",
        "PRE_PUBLISHED",
        "PUBLISHED",
        "EMBARGOED",
        "WITHDRAWN",
        "FAILED",
        "UNKNOWN",
    }


def test_canonical_state_values_match_contract():
    assert _values(CanonicalState) == {
        "PROVISIONAL",
        "CANONICAL",
        "SUPERSEDED",
        "NOT_CANONICAL",
        "NOT_AVAILABLE",
        "UNKNOWN",
    }


def test_defaults_match_contract():
    assert DEFAULT_MARKET_PHASE is MarketPhase.CLOSED
    assert DEFAULT_EXECUTION_STATE is ExecutionState.NOT_EXECUTED
    assert DEFAULT_PRICE_BASIS is PriceBasis.UNKNOWN
    assert DEFAULT_PUBLICATION_STATE is PublicationState.NOT_PUBLISHED
    assert DEFAULT_CANONICAL_STATE is CanonicalState.PROVISIONAL


def test_enum_values_are_strings():
    for enum_cls in (
        Perspective,
        MarketPhase,
        SourceFreshness,
        ExecutionState,
        PriceBasis,
        PublicationState,
        CanonicalState,
    ):
        for member in enum_cls:
            assert isinstance(member.value, str)
            assert isinstance(member, str)
            assert member.value == member.name
