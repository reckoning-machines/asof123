"""Tests for `make_snapshot` and `canonicalize_context`."""

from __future__ import annotations

import json
import hashlib
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
from asof123.snapshot import (
    canonicalize_context,
    canonicalize_snapshot_payload,
    make_snapshot,
)


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


def _publication_metadata(**overrides) -> dict:
    """Return deterministic publication metadata for snapshot identity tests.

    Phase S1 deliberately keeps publication facts inside
    `SourceStatus.metadata["publication"]`; there is no publication evaluator
    and no new ontology object.
    """
    publication = {
        "publication_state": PublicationState.PUBLISHED.value,
        "canonical_state": CanonicalState.CANONICAL.value,
        "publication_utc": "2026-05-12T21:05:00Z",
        "asserted_at_utc": "2026-05-12T21:06:00Z",
    }
    publication.update(overrides)
    return {"publication": publication}


def _source_with_publication(metadata: dict) -> SourceStatus:
    return SourceStatus(
        provider="official-close",
        freshness=SourceFreshness.FRESH,
        last_update_utc=UTC_NOW,
        metadata=metadata,
    )


def _ctx_with_publication(**publication_overrides) -> TemporalContext:
    return _ctx(
        sources={
            "official_close": _source_with_publication(
                _publication_metadata(**publication_overrides)
            )
        }
    )


def test_make_snapshot_returns_valid_as_of_snapshot():
    ctx = _ctx()
    snap = make_snapshot(ctx, "snap-1")
    assert isinstance(snap, AsOfSnapshot)
    assert snap.snapshot_id == "snap-1"
    assert snap.context is not ctx
    assert snap.context == ctx
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


def test_canonical_snapshot_payload_includes_versions_and_context_only():
    ctx = _ctx()
    payload = json.loads(canonicalize_snapshot_payload(ctx))
    assert sorted(payload) == [
        "context",
        "semantic_contract_version",
        "snapshot_schema_version",
    ]
    assert payload["snapshot_schema_version"] == "asof123.snapshot.v1"
    assert payload["semantic_contract_version"] == "asof123.contract.v1"
    assert payload["context"] == ctx.model_dump(mode="json")


def test_make_snapshot_does_not_mutate_original_context():
    ctx = _ctx()
    before = ctx.model_dump(mode="json")
    make_snapshot(ctx, "snap-1")
    after = ctx.model_dump(mode="json")
    assert before == after


def test_snapshot_rejects_mutation_after_creation():
    snap = make_snapshot(_ctx(), "snap-1")
    with pytest.raises(ValidationError):
        snap.snapshot_id = "changed"
    with pytest.raises(ValidationError):
        snap.context.market_phase = MarketPhase.CLOSED
    with pytest.raises(TypeError):
        snap.context.sources["new"] = SourceStatus(
            freshness=SourceFreshness.FRESH
        )


def test_snapshot_hash_matches_embedded_context_after_copy():
    snap = make_snapshot(_ctx(), "snap-1")
    assert (
        snap.content_hash
        == make_snapshot(snap.context, "snap-2").content_hash
    )


def test_snapshot_hash_is_over_versioned_payload_not_audit_fields():
    snap_a = make_snapshot(_ctx(), "snap-a")
    snap_b = make_snapshot(_ctx(), "snap-b")
    assert snap_a.snapshot_id != snap_b.snapshot_id
    assert snap_a.captured_at_utc != snap_b.captured_at_utc
    assert snap_a.content_hash == snap_b.content_hash


def test_snapshot_hash_matches_versioned_payload_sha256():
    ctx = _ctx()
    expected = hashlib.sha256(
        canonicalize_snapshot_payload(ctx).encode("utf-8")
    ).hexdigest()
    assert make_snapshot(ctx, "snap-1").content_hash == expected


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


def test_source_order_does_not_change_canonical_hash():
    quotes = SourceStatus(provider="quotes", freshness=SourceFreshness.FRESH)
    actions = SourceStatus(provider="actions", freshness=SourceFreshness.STALE)
    ctx_a = _ctx(sources={"quotes": quotes, "actions": actions})
    ctx_b = _ctx(sources={"actions": actions, "quotes": quotes})
    assert (
        make_snapshot(ctx_a, "a").content_hash
        == make_snapshot(ctx_b, "b").content_hash
    )


def test_metadata_key_order_does_not_change_canonical_hash():
    status_a = SourceStatus(
        provider="quotes",
        freshness=SourceFreshness.FRESH,
        metadata={"b": 2, "a": {"y": 2, "x": 1}},
    )
    status_b = SourceStatus(
        provider="quotes",
        freshness=SourceFreshness.FRESH,
        metadata={"a": {"x": 1, "y": 2}, "b": 2},
    )
    ctx_a = _ctx(sources={"quotes": status_a})
    ctx_b = _ctx(sources={"quotes": status_b})
    assert (
        make_snapshot(ctx_a, "a").content_hash
        == make_snapshot(ctx_b, "b").content_hash
    )


def test_publication_metadata_key_order_does_not_change_snapshot_hash():
    status_a = _source_with_publication(
        {
            "publication": {
                "publication_state": PublicationState.PUBLISHED.value,
                "canonical_state": CanonicalState.CANONICAL.value,
                "publication_utc": "2026-05-12T21:05:00Z",
                "asserted_at_utc": "2026-05-12T21:06:00Z",
            }
        }
    )
    status_b = _source_with_publication(
        {
            "publication": {
                "asserted_at_utc": "2026-05-12T21:06:00Z",
                "publication_utc": "2026-05-12T21:05:00Z",
                "canonical_state": CanonicalState.CANONICAL.value,
                "publication_state": PublicationState.PUBLISHED.value,
            }
        }
    )
    ctx_a = _ctx(sources={"official_close": status_a})
    ctx_b = _ctx(sources={"official_close": status_b})

    assert (
        make_snapshot(ctx_a, "a").content_hash
        == make_snapshot(ctx_b, "b").content_hash
    )


def test_nested_publication_metadata_order_does_not_change_snapshot_hash():
    status_a = _source_with_publication(
        _publication_metadata(
            assertion_id="official-close-2026-05-12-v1",
            authority_id="official_close_reference",
            superseded_by=None,
            superseded_utc=None,
            withdrawal_id=None,
            withdrawal_utc=None,
            explanation="Official close asserted by static test fixture",
        )
    )
    status_b = _source_with_publication(
        {
            "publication": {
                "withdrawal_utc": None,
                "withdrawal_id": None,
                "superseded_utc": None,
                "superseded_by": None,
                "explanation": "Official close asserted by static test fixture",
                "authority_id": "official_close_reference",
                "assertion_id": "official-close-2026-05-12-v1",
                "asserted_at_utc": "2026-05-12T21:06:00Z",
                "publication_utc": "2026-05-12T21:05:00Z",
                "canonical_state": CanonicalState.CANONICAL.value,
                "publication_state": PublicationState.PUBLISHED.value,
            }
        }
    )
    ctx_a = _ctx(sources={"official_close": status_a})
    ctx_b = _ctx(sources={"official_close": status_b})

    assert (
        make_snapshot(ctx_a, "a").content_hash
        == make_snapshot(ctx_b, "b").content_hash
    )


def test_publication_state_change_changes_snapshot_hash():
    ctx_published = _ctx_with_publication(
        publication_state=PublicationState.PUBLISHED.value
    )
    ctx_pre_published = _ctx_with_publication(
        publication_state=PublicationState.PRE_PUBLISHED.value
    )

    assert (
        make_snapshot(ctx_published, "published").content_hash
        != make_snapshot(ctx_pre_published, "pre-published").content_hash
    )


def test_canonical_state_change_changes_snapshot_hash():
    ctx_canonical = _ctx_with_publication(
        canonical_state=CanonicalState.CANONICAL.value
    )
    ctx_provisional = _ctx_with_publication(
        canonical_state=CanonicalState.PROVISIONAL.value
    )

    assert (
        make_snapshot(ctx_canonical, "canonical").content_hash
        != make_snapshot(ctx_provisional, "provisional").content_hash
    )


def test_publication_utc_change_changes_snapshot_hash():
    ctx_initial = _ctx_with_publication(
        publication_utc="2026-05-12T21:05:00Z"
    )
    ctx_later = _ctx_with_publication(
        publication_utc="2026-05-12T21:10:00Z"
    )

    assert (
        make_snapshot(ctx_initial, "initial").content_hash
        != make_snapshot(ctx_later, "later").content_hash
    )


def test_asserted_at_utc_change_changes_snapshot_hash():
    ctx_initial = _ctx_with_publication(
        asserted_at_utc="2026-05-12T21:06:00Z"
    )
    ctx_later = _ctx_with_publication(
        asserted_at_utc="2026-05-12T21:07:00Z"
    )

    assert (
        make_snapshot(ctx_initial, "initial").content_hash
        != make_snapshot(ctx_later, "later").content_hash
    )


def test_snapshot_audit_fields_do_not_change_publication_hash():
    ctx = _ctx_with_publication()
    content_hash = make_snapshot(ctx, "base").content_hash
    snap_a = AsOfSnapshot(
        snapshot_id="audit-record-a",
        captured_at_utc=datetime(2026, 5, 12, 21, 10, 0, tzinfo=timezone.utc),
        context=ctx,
        content_hash=content_hash,
    )
    snap_b = AsOfSnapshot(
        snapshot_id="audit-record-b",
        captured_at_utc=datetime(2026, 5, 12, 21, 15, 0, tzinfo=timezone.utc),
        context=ctx,
        content_hash=content_hash,
    )

    assert snap_a.snapshot_id != snap_b.snapshot_id
    assert snap_a.captured_at_utc != snap_b.captured_at_utc
    assert snap_a.content_hash == snap_b.content_hash


def test_publication_assertion_exactly_at_cutoff_is_identity_admissible():
    cutoff = datetime(2026, 5, 12, 21, 6, 0, tzinfo=timezone.utc)
    ctx = _ctx(
        knowledge_cutoff_utc=cutoff,
        sources={
            "official_close": _source_with_publication(
                _publication_metadata(
                    publication_utc="2026-05-12T21:05:00Z",
                    asserted_at_utc="2026-05-12T21:06:00Z",
                )
            )
        },
    )
    first = make_snapshot(ctx, "first")
    second = make_snapshot(ctx, "second")

    assert ctx.knowledge_cutoff_utc == cutoff
    assert first.snapshot_id != second.snapshot_id
    assert first.content_hash == second.content_hash


def test_publication_assertion_after_cutoff_is_identity_distinct():
    cutoff = datetime(2026, 5, 12, 21, 6, 0, tzinfo=timezone.utc)
    ctx_at_cutoff = _ctx(
        knowledge_cutoff_utc=cutoff,
        sources={
            "official_close": _source_with_publication(
                _publication_metadata(
                    publication_utc="2026-05-12T21:05:00Z",
                    asserted_at_utc="2026-05-12T21:06:00Z",
                )
            )
        },
    )
    ctx_after_cutoff = _ctx(
        knowledge_cutoff_utc=cutoff,
        sources={
            "official_close": _source_with_publication(
                _publication_metadata(
                    publication_utc="2026-05-12T21:05:00Z",
                    asserted_at_utc="2026-05-12T21:07:00Z",
                )
            )
        },
    )

    assert (
        make_snapshot(ctx_at_cutoff, "at-cutoff").content_hash
        != make_snapshot(ctx_after_cutoff, "after-cutoff").content_hash
    )


def test_withdrawal_metadata_changes_snapshot_hash():
    ctx_published = _ctx_with_publication()
    ctx_withdrawn = _ctx_with_publication(
        withdrawal_utc="2026-05-12T21:30:00Z",
        withdrawal_id="withdrawal-official-close-2026-05-12-v1",
    )

    assert (
        make_snapshot(ctx_published, "published").content_hash
        != make_snapshot(ctx_withdrawn, "withdrawn").content_hash
    )


def test_supersession_metadata_changes_snapshot_hash():
    ctx_original = _ctx_with_publication()
    ctx_superseded = _ctx_with_publication(
        superseded_utc="2026-05-12T22:00:00Z",
        superseded_by="official-close-2026-05-12-v2",
    )

    assert (
        make_snapshot(ctx_original, "original").content_hash
        != make_snapshot(ctx_superseded, "superseded").content_hash
    )
