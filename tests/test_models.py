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

import asof123
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
    AsOf,
)


UTC_NOW = datetime(2026, 5, 12, 13, 45, 0, tzinfo=timezone.utc)


def test_public_asof_names_are_exported_without_old_ontology_names():
    old_resolved_name = "Temporal" + "Context"
    old_request_name = "Resolve" + "Request"
    assert asof123.AsOf is AsOf
    assert asof123.AsOfRequest is not None
    assert asof123.AsOfSnapshot is AsOfSnapshot
    assert "AsOf" in asof123.__all__
    assert "AsOfRequest" in asof123.__all__
    assert "AsOfSnapshot" in asof123.__all__
    assert old_resolved_name not in asof123.__all__
    assert old_request_name not in asof123.__all__
    assert not hasattr(asof123, old_resolved_name)
    assert not hasattr(asof123, old_request_name)


def _valid_asof(**overrides) -> AsOf:
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
    return AsOf(**base)


def test_valid_asof_xnys_new_york():
    asof = _valid_asof()
    assert asof.market == "XNYS"
    assert asof.market_timezone == "America/New_York"
    assert asof.market_datetime.isoformat() == "2026-05-12T09:45:00-04:00"
    assert asof.market_date == date(2026, 5, 12)
    assert asof.perspective is Perspective.LIVE
    assert asof.market_phase is MarketPhase.MARKET_OPEN
    assert "equities_quotes" in asof.sources


def test_market_datetime_and_market_date_are_derived_from_utc_and_timezone():
    asof = _valid_asof(
        resolved_at_utc=datetime(2026, 5, 13, 4, 0, 0, tzinfo=timezone.utc),
        knowledge_cutoff_utc=datetime(2026, 5, 13, 4, 0, 0, tzinfo=timezone.utc),
        business_date=date(2026, 5, 13),
        market_phase=MarketPhase.PRE_OPEN,
        price_basis=PriceBasis.PRIOR_CLOSE,
    )
    assert asof.market_datetime.isoformat() == "2026-05-13T00:00:00-04:00"
    assert asof.market_date == date(2026, 5, 13)


def test_market_datetime_spring_dst_offset_is_derived():
    asof = _valid_asof(
        resolved_at_utc=datetime(2026, 3, 9, 14, 0, 0, tzinfo=timezone.utc),
        knowledge_cutoff_utc=datetime(2026, 3, 9, 14, 0, 0, tzinfo=timezone.utc),
        business_date=date(2026, 3, 9),
    )
    assert asof.market_datetime.isoformat() == "2026-03-09T10:00:00-04:00"
    assert asof.market_date == date(2026, 3, 9)


def test_market_datetime_fall_dst_offset_is_derived():
    asof = _valid_asof(
        resolved_at_utc=datetime(2026, 11, 2, 15, 0, 0, tzinfo=timezone.utc),
        knowledge_cutoff_utc=datetime(2026, 11, 2, 15, 0, 0, tzinfo=timezone.utc),
        business_date=date(2026, 11, 2),
    )
    assert asof.market_datetime.isoformat() == "2026-11-02T10:00:00-05:00"
    assert asof.market_date == date(2026, 11, 2)


def test_mismatched_market_datetime_rejected():
    with pytest.raises(ValidationError, match="market_datetime is derived"):
        _valid_asof(
            market_datetime=datetime(2026, 5, 12, 13, 45, 0, tzinfo=timezone.utc),
        )


def test_mismatched_market_date_rejected():
    with pytest.raises(ValidationError, match="market_date is derived"):
        _valid_asof(market_date=date(2026, 5, 13))


def test_market_identity_valid():
    ident = MarketIdentity(market="XNYS", market_timezone="America/New_York")
    assert ident.market == "XNYS"
    assert ident.market_timezone == "America/New_York"


def test_market_identity_allows_explicit_utc():
    ident = MarketIdentity(market="XCRYPTO", market_timezone="UTC")
    assert ident.market_timezone == "UTC"


def test_naive_datetime_rejected_on_asof():
    naive = datetime(2026, 5, 12, 13, 45, 0)
    with pytest.raises(ValidationError):
        _valid_asof(resolved_at_utc=naive)


def test_non_utc_aware_datetime_rejected_on_asof():
    plus_two = datetime(2026, 5, 12, 13, 45, 0, tzinfo=timezone(timedelta(hours=2)))
    with pytest.raises(ValidationError):
        _valid_asof(knowledge_cutoff_utc=plus_two)


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


def test_empty_source_key_rejected_in_asof():
    with pytest.raises(ValidationError):
        _valid_asof(
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
        _valid_asof(
            perspective=Perspective.CANONICAL,
            canonical_state=CanonicalState.PROVISIONAL,
        )


def test_canonical_perspective_with_canonical_state_ok():
    asof = _valid_asof(
        perspective=Perspective.CANONICAL,
        canonical_state=CanonicalState.CANONICAL,
    )
    assert asof.perspective is Perspective.CANONICAL
    assert asof.canonical_state is CanonicalState.CANONICAL


def test_executed_perspective_rejects_intended_execution_state():
    with pytest.raises(ValidationError):
        _valid_asof(
            perspective=Perspective.EXECUTED,
            execution_state=ExecutionState.INTENDED,
        )


def test_executed_perspective_rejects_working_execution_state():
    with pytest.raises(ValidationError):
        _valid_asof(
            perspective=Perspective.EXECUTED,
            execution_state=ExecutionState.WORKING,
        )


def test_executed_perspective_accepts_filled_execution_state():
    asof = _valid_asof(
        perspective=Perspective.EXECUTED,
        execution_state=ExecutionState.FILLED,
    )
    assert asof.execution_state is ExecutionState.FILLED


def test_unknown_price_basis_requires_reason_and_explanation():
    with pytest.raises(ValidationError):
        _valid_asof(price_basis=PriceBasis.UNKNOWN)


def test_unknown_price_basis_accepted_with_reason_and_explanation():
    asof = _valid_asof(
        price_basis=PriceBasis.UNKNOWN,
        reason_code="PRICE_FEED_DOWN",
        explanation="Vendor price feed has not reported since 21:00 UTC.",
    )
    assert asof.price_basis is PriceBasis.UNKNOWN


def test_unknown_publication_state_requires_reason_and_explanation():
    with pytest.raises(ValidationError):
        _valid_asof(publication_state=PublicationState.UNKNOWN)


def test_unknown_canonical_state_requires_reason_and_explanation():
    with pytest.raises(ValidationError):
        _valid_asof(canonical_state=CanonicalState.UNKNOWN)


def test_as_of_snapshot_valid():
    snap = AsOfSnapshot(
        snapshot_id="snap-1",
        captured_at_utc=UTC_NOW,
        asof=_valid_asof(),
        content_hash="abc123",
    )
    assert snap.snapshot_id == "snap-1"
    assert snap.snapshot_schema_version == SNAPSHOT_SCHEMA_VERSION
    assert snap.semantic_contract_version == SEMANTIC_CONTRACT_VERSION
    assert snap.hash_algorithm == SNAPSHOT_HASH_ALGORITHM
    assert snap.captured_at_utc == UTC_NOW
    assert snap.asof.market == "XNYS"


def test_as_of_snapshot_rejects_empty_snapshot_id():
    with pytest.raises(ValidationError):
        AsOfSnapshot(snapshot_id="", captured_at_utc=UTC_NOW, asof=_valid_asof())


def test_as_of_snapshot_rejects_naive_captured_at():
    with pytest.raises(ValidationError):
        AsOfSnapshot(
            snapshot_id="snap-2",
            captured_at_utc=datetime(2026, 5, 12, 13, 45, 0),
            asof=_valid_asof(),
        )


def test_as_of_snapshot_rejects_non_utc_captured_at():
    plus_one = datetime(2026, 5, 12, tzinfo=timezone(timedelta(hours=1)))
    with pytest.raises(ValidationError):
        AsOfSnapshot(
            snapshot_id="snap-3",
            captured_at_utc=plus_one,
            asof=_valid_asof(),
        )


def test_as_of_snapshot_rejects_empty_content_hash():
    with pytest.raises(ValidationError):
        AsOfSnapshot(
            snapshot_id="snap-4",
            captured_at_utc=UTC_NOW,
            asof=_valid_asof(),
            content_hash="",
        )


def test_as_of_snapshot_rejects_unknown_schema_version():
    with pytest.raises(ValidationError):
        AsOfSnapshot(
            snapshot_id="snap-5",
            snapshot_schema_version="asof123.snapshot.v999",
            captured_at_utc=UTC_NOW,
            asof=_valid_asof(),
        )


def test_as_of_snapshot_rejects_unknown_semantic_contract_version():
    with pytest.raises(ValidationError):
        AsOfSnapshot(
            snapshot_id="snap-6",
            semantic_contract_version="asof123.contract.v999",
            captured_at_utc=UTC_NOW,
            asof=_valid_asof(),
        )


def test_as_of_snapshot_rejects_unknown_hash_algorithm():
    with pytest.raises(ValidationError):
        AsOfSnapshot(
            snapshot_id="snap-7",
            hash_algorithm="md5",
            captured_at_utc=UTC_NOW,
            asof=_valid_asof(),
        )
