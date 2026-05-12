"""Tests for `make_snapshot` and `canonicalize_context`."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

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
from asof123.models import AsOfSnapshot, SourceStatus, TemporalContext
from asof123.snapshot import canonicalize_context, make_snapshot


UTC_NOW = datetime(2026, 5, 12, 13, 45, 0, tzinfo=timezone.utc)


def _ctx(**overrides) -> TemporalContext:
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
            "quotes": SourceStatus(
                provider="quotes",
                freshness=SourceFreshness.FRESH,
                last_update_utc=UTC_NOW,
            ),
        },
    )
    base.update(overrides)
    return TemporalContext(**base)


def test_make_snapshot_returns_valid_as_of_snapshot():
    ctx = _ctx()
    snap = make_snapshot(ctx, "snap-1")
    assert isinstance(snap, AsOfSnapshot)
    assert snap.snapshot_id == "snap-1"
    assert snap.context is ctx
    assert snap.captured_at_utc.tzinfo is not None
    assert snap.captured_at_utc.utcoffset().total_seconds() == 0
    assert snap.content_hash is not None
    assert len(snap.content_hash) == 64  # SHA256 hex
    int(snap.content_hash, 16)  # raises if not valid hex


def test_content_hash_deterministic_for_same_context():
    ctx = _ctx()
    snap_a = make_snapshot(ctx, "a")
    snap_b = make_snapshot(ctx, "b")
    assert snap_a.content_hash == snap_b.content_hash


def test_canonicalize_context_deterministic():
    ctx = _ctx()
    assert canonicalize_context(ctx) == canonicalize_context(ctx)


def test_changing_context_changes_hash():
    snap_live = make_snapshot(_ctx(perspective=Perspective.LIVE), "a")
    snap_pti = make_snapshot(
        _ctx(
            perspective=Perspective.PRE_TRADE_INTENT,
            price_basis=PriceBasis.PRIOR_CLOSE,
        ),
        "b",
    )
    assert snap_live.content_hash != snap_pti.content_hash


def test_snapshot_id_required():
    ctx = _ctx()
    with pytest.raises(ValidationError):
        make_snapshot(ctx, "")


def test_captured_at_utc_is_timezone_aware_utc():
    snap = make_snapshot(_ctx(), "snap-1")
    assert snap.captured_at_utc.tzinfo is not None
    assert snap.captured_at_utc.utcoffset().total_seconds() == 0


def test_canonical_json_uses_sorted_keys_and_tight_separators():
    ctx = _ctx()
    canonical = canonicalize_context(ctx)
    expected = json.dumps(
        ctx.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert canonical == expected
    # No whitespace introduced by tight separators.
    assert ", " not in canonical
    assert ": " not in canonical


def test_make_snapshot_does_not_mutate_original_context():
    ctx = _ctx()
    before = ctx.model_dump(mode="json")
    make_snapshot(ctx, "snap-1")
    after = ctx.model_dump(mode="json")
    assert before == after


def test_hash_differs_when_source_status_changes():
    ctx_fresh = _ctx()
    ctx_stale = _ctx(
        sources={
            "quotes": SourceStatus(
                provider="quotes",
                freshness=SourceFreshness.STALE,
                last_update_utc=UTC_NOW,
            ),
        },
    )
    a = make_snapshot(ctx_fresh, "a")
    b = make_snapshot(ctx_stale, "b")
    assert a.content_hash != b.content_hash
