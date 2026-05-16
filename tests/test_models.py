"""Tests for the Pydantic models in asof123.models.

Covers UTC and IANA-timezone enforcement, market identity validation,
source-name validation, and the fail-closed bindings between Perspective,
ExecutionState, CanonicalState, PriceBasis, and PublicationState.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math

import pytest
from pydantic import ValidationError

from asof123.enums import (
    CanonicalState,
    ExecutionState,
    MarketPhase,
    Perspective,
    PriceBasis,
    PublicationState,
    SourceFreshness,
)
from asof123.models import (
    SEMANTIC_CONTRACT_VERSION,
    SNAPSHOT_HASH_ALGORITHM,
    SNAPSHOT_SCHEMA_VERSION,
    AsOfSnapshot,
    MarketIdentity,
    SourceStatus,
    TemporalContext,
)


UTC_NOW = datetime(2026, 5, 12, 13, 45, 0, tzinfo=timezone.utc)


def _valid_context(**overrides) -> TemporalContext:
    base = dict(
        resolved_at_utc=UTC_NOW,
        perspective=Perspective.LIVE,
        market="XNYS",
        market_timezone="America/New_York",
        business_date=date(2026, 5, 12),
        market_phase=MarketPhase.MARKET_OPEN,
        knowledge_cutoff_utc=UTC_NOW,
        price_basis=PriceBasis.LAST_TRADE,
        execution_state=ExecutionState.NOT_EXECUTED,
        publication_state=PublicationState.PUBLISHED,
        canonical_state=CanonicalState.PROVISIONAL,
        sources={
            "equities_quotes": SourceStatus(
                provider="vendor_a",
                freshness=SourceFreshness.FRESH,
                last_update_utc=UTC_NOW,
            ),
        },
    )
    base.update(overrides)
    return TemporalContext(**base)


def test_valid_temporal_context_xnys_new_york():
    ctx = _valid_context()
    assert ctx.market == "XNYS"
    assert ctx.market_timezone == "America/New_York"
    assert ctx.perspective is Perspective.LIVE
    assert ctx.market_phase is MarketPhase.MARKET_OPEN
    assert "equities_quotes" in ctx.sources


def test_market_identity_valid():
    ident = MarketIdentity(market="XNYS", market_timezone="America/New_York")
    assert ident.market == "XNYS"
    assert ident.market_timezone == "America/New_York"


def test_market_identity_allows_explicit_utc():
    ident = MarketIdentity(market="XCRYPTO", market_timezone="UTC")
    assert ident.market_timezone == "UTC"


def test_naive_datetime_rejected_on_temporal_context():
    naive = datetime(2026, 5, 12, 13, 45, 0)
    with pytest.raises(ValidationError):
        _valid_context(resolved_at_utc=naive)


def test_non_utc_aware_datetime_rejected_on_temporal_context():
    plus_two = datetime(2026, 5, 12, 13, 45, 0, tzinfo=timezone(timedelta(hours=2)))
    with pytest.raises(ValidationError):
        _valid_context(knowledge_cutoff_utc=plus_two)


def test_source_status_rejects_naive_last_update():
    with pytest.raises(ValidationError):
        SourceStatus(
            freshness=SourceFreshness.FRESH,
            last_update_utc=datetime(2026, 5, 12, 13, 45, 0),
        )


def test_source_status_rejects_non_utc_expected_publication():
    plus_two = datetime(2026, 5, 12, tzinfo=timezone(timedelta(hours=2)))
    with pytest.raises(ValidationError):
        SourceStatus(
            freshness=SourceFreshness.NOT_PUBLISHED,
            expected_publication_utc=plus_two,
        )


def test_source_status_rejects_empty_provider_string():
    with pytest.raises(ValidationError):
        SourceStatus(provider="", freshness=SourceFreshness.FRESH)


def test_est_abbreviation_rejected_as_market_timezone():
    with pytest.raises(ValidationError):
        MarketIdentity(market="XNYS", market_timezone="EST")


def test_unknown_timezone_rejected():
    with pytest.raises(ValidationError):
        MarketIdentity(market="XNYS", market_timezone="America/Not_A_Place")


def test_lowercase_market_rejected():
    with pytest.raises(ValidationError):
        MarketIdentity(market="xnys", market_timezone="America/New_York")


def test_empty_market_rejected():
    with pytest.raises(ValidationError):
        MarketIdentity(market="", market_timezone="America/New_York")


def test_empty_source_key_rejected_in_context():
    with pytest.raises(ValidationError):
        _valid_context(
            sources={"": SourceStatus(freshness=SourceFreshness.FRESH)},
        )


def test_source_status_metadata_is_frozen_after_validation():
    status = SourceStatus(
        freshness=SourceFreshness.FRESH,
        metadata={"coverage": {"symbols": ["A", "B"]}},
    )
    assert status.metadata == {"coverage": {"symbols": ("A", "B")}}
    with pytest.raises(TypeError):
        status.metadata["new"] = "value"
    with pytest.raises(TypeError):
        status.metadata["coverage"]["symbols"] = ["C"]


def test_source_status_metadata_rejects_non_json_values():
    with pytest.raises(ValidationError):
        SourceStatus(freshness=SourceFreshness.FRESH, metadata={"bad": {"A", "B"}})


def test_source_status_metadata_rejects_non_finite_float():
    with pytest.raises(ValidationError):
        SourceStatus(freshness=SourceFreshness.FRESH, metadata={"bad": math.nan})


def test_canonical_perspective_requires_canonical_state_canonical():
    with pytest.raises(ValidationError):
        _valid_context(
            perspective=Perspective.CANONICAL,
            canonical_state=CanonicalState.PROVISIONAL,
        )


def test_canonical_perspective_with_canonical_state_ok():
    ctx = _valid_context(
        perspective=Perspective.CANONICAL,
        canonical_state=CanonicalState.CANONICAL,
    )
    assert ctx.perspective is Perspective.CANONICAL
    assert ctx.canonical_state is CanonicalState.CANONICAL


def test_executed_perspective_rejects_intended_execution_state():
    with pytest.raises(ValidationError):
        _valid_context(
            perspective=Perspective.EXECUTED,
            execution_state=ExecutionState.INTENDED,
        )


def test_executed_perspective_rejects_working_execution_state():
    with pytest.raises(ValidationError):
        _valid_context(
            perspective=Perspective.EXECUTED,
            execution_state=ExecutionState.WORKING,
        )


def test_executed_perspective_accepts_filled_execution_state():
    ctx = _valid_context(
        perspective=Perspective.EXECUTED,
        execution_state=ExecutionState.FILLED,
    )
    assert ctx.execution_state is ExecutionState.FILLED


def test_unknown_price_basis_requires_reason_and_explanation():
    with pytest.raises(ValidationError):
        _valid_context(price_basis=PriceBasis.UNKNOWN)


def test_unknown_price_basis_accepted_with_reason_and_explanation():
    ctx = _valid_context(
        price_basis=PriceBasis.UNKNOWN,
        reason_code="PRICE_FEED_DOWN",
        explanation="Vendor price feed has not reported since 21:00 UTC.",
    )
    assert ctx.price_basis is PriceBasis.UNKNOWN


def test_unknown_publication_state_requires_reason_and_explanation():
    with pytest.raises(ValidationError):
        _valid_context(publication_state=PublicationState.UNKNOWN)


def test_unknown_canonical_state_requires_reason_and_explanation():
    with pytest.raises(ValidationError):
        _valid_context(canonical_state=CanonicalState.UNKNOWN)


def test_as_of_snapshot_valid():
    snap = AsOfSnapshot(
        snapshot_id="snap-1",
        captured_at_utc=UTC_NOW,
        context=_valid_context(),
        content_hash="abc123",
    )
    assert snap.snapshot_id == "snap-1"
    assert snap.snapshot_schema_version == SNAPSHOT_SCHEMA_VERSION
    assert snap.semantic_contract_version == SEMANTIC_CONTRACT_VERSION
    assert snap.hash_algorithm == SNAPSHOT_HASH_ALGORITHM
    assert snap.captured_at_utc == UTC_NOW
    assert snap.context.market == "XNYS"


def test_as_of_snapshot_rejects_empty_snapshot_id():
    with pytest.raises(ValidationError):
        AsOfSnapshot(snapshot_id="", captured_at_utc=UTC_NOW, context=_valid_context())


def test_as_of_snapshot_rejects_naive_captured_at():
    with pytest.raises(ValidationError):
        AsOfSnapshot(
            snapshot_id="snap-2",
            captured_at_utc=datetime(2026, 5, 12, 13, 45, 0),
            context=_valid_context(),
        )


def test_as_of_snapshot_rejects_non_utc_captured_at():
    plus_one = datetime(2026, 5, 12, tzinfo=timezone(timedelta(hours=1)))
    with pytest.raises(ValidationError):
        AsOfSnapshot(
            snapshot_id="snap-3",
            captured_at_utc=plus_one,
            context=_valid_context(),
        )


def test_as_of_snapshot_rejects_empty_content_hash():
    with pytest.raises(ValidationError):
        AsOfSnapshot(
            snapshot_id="snap-4",
            captured_at_utc=UTC_NOW,
            context=_valid_context(),
            content_hash="",
        )


def test_as_of_snapshot_rejects_unknown_schema_version():
    with pytest.raises(ValidationError):
        AsOfSnapshot(
            snapshot_id="snap-5",
            snapshot_schema_version="asof123.snapshot.v999",
            captured_at_utc=UTC_NOW,
            context=_valid_context(),
        )


def test_as_of_snapshot_rejects_unknown_semantic_contract_version():
    with pytest.raises(ValidationError):
        AsOfSnapshot(
            snapshot_id="snap-6",
            semantic_contract_version="asof123.contract.v999",
            captured_at_utc=UTC_NOW,
            context=_valid_context(),
        )


def test_as_of_snapshot_rejects_unknown_hash_algorithm():
    with pytest.raises(ValidationError):
        AsOfSnapshot(
            snapshot_id="snap-7",
            hash_algorithm="md5",
            captured_at_utc=UTC_NOW,
            context=_valid_context(),
        )
