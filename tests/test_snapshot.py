"""Tests for `make_snapshot` and `canonicalize_asof`."""

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
from asof123.models import AsOfSnapshot, SourceStatus, AsOf
from asof123.snapshot import (
    canonicalize_asof,
    canonicalize_snapshot_payload,
    make_snapshot,
)


UTC_NOW = datetime(2026, 5, 12, 13, 45, 0, tzinfo=timezone.utc)


def _asof(**overrides) -> AsOf:
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
    return AsOf(**base)


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


def _asof_with_publication(**publication_overrides) -> AsOf:
    return _asof(
        sources={
            "official_close": _source_with_publication(
                _publication_metadata(**publication_overrides)
            )
        }
    )


def test_make_snapshot_returns_valid_as_of_snapshot():
    asof = _asof()
    snap = make_snapshot(asof, "snap-1")
    assert isinstance(snap, AsOfSnapshot)
    assert snap.snapshot_id == "snap-1"
    assert snap.asof is not asof
    assert snap.asof == asof
    assert snap.captured_at_utc.tzinfo is not None
    assert snap.captured_at_utc.utcoffset().total_seconds() == 0
    assert snap.content_hash is not None
    assert len(snap.content_hash) == 64  # SHA256 hex
    int(snap.content_hash, 16)  # raises if not valid hex


def test_snapshot_persists_source_timestamp_authority():
    timestamp = datetime(2026, 5, 12, 13, 44, 58, tzinfo=timezone.utc)
    asof = _asof(
        sources={
            "quotes": SourceStatus(
                provider="quotes",
                freshness=SourceFreshness.FRESH,
                timestamp_utc=timestamp,
                timestamp_name="vendor_updated_at",
            )
        }
    )

    snap = make_snapshot(asof, "timestamp-authority")
    payload = snap.model_dump(mode="json")

    status = payload["asof"]["sources"]["quotes"]
    assert status["timestamp_utc"].startswith("2026-05-12T13:44:58")
    assert status["timestamp_name"] == "vendor_updated_at"


def test_content_hash_deterministic_for_same_context():
    asof = _asof()
    snap_a = make_snapshot(asof, "a")
    snap_b = make_snapshot(asof, "b")
    assert snap_a.content_hash == snap_b.content_hash


def test_canonicalize_asof_deterministic():
    asof = _asof()
    assert canonicalize_asof(asof) == canonicalize_asof(asof)


def test_changing_context_changes_hash():
    snap_live = make_snapshot(_asof(perspective=Perspective.LIVE), "a")
    snap_pti = make_snapshot(
        _asof(
            perspective=Perspective.PRE_TRADE_INTENT,
            price_basis=PriceBasis.PRIOR_CLOSE,
        ),
        "b",
    )
    assert snap_live.content_hash != snap_pti.content_hash


def test_snapshot_id_required():
    asof = _asof()
    with pytest.raises(ValidationError):
        make_snapshot(asof, "")


def test_captured_at_utc_is_timezone_aware_utc():
    snap = make_snapshot(_asof(), "snap-1")
    assert snap.captured_at_utc.tzinfo is not None
    assert snap.captured_at_utc.utcoffset().total_seconds() == 0


def test_canonical_json_uses_sorted_keys_and_tight_separators():
    asof = _asof()
    canonical = canonicalize_asof(asof)
    expected = json.dumps(
        asof.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert canonical == expected
    # No whitespace introduced by tight separators.
    assert ", " not in canonical
    assert ": " not in canonical


def test_canonical_snapshot_payload_includes_versions_and_asof_only():
    asof = _asof()
    payload = json.loads(canonicalize_snapshot_payload(asof))
    assert sorted(payload) == [
        "asof",
        "semantic_contract_version",
        "snapshot_schema_version",
    ]
    assert payload["snapshot_schema_version"] == "asof123.snapshot.v2"
    assert payload["semantic_contract_version"] == "asof123.contract.v1"
    assert payload["asof"] == asof.model_dump(mode="json")


def test_make_snapshot_does_not_mutate_original_context():
    asof = _asof()
    before = asof.model_dump(mode="json")
    make_snapshot(asof, "snap-1")
    after = asof.model_dump(mode="json")
    assert before == after


def test_snapshot_rejects_mutation_after_creation():
    snap = make_snapshot(_asof(), "snap-1")
    with pytest.raises(ValidationError):
        snap.snapshot_id = "changed"
    with pytest.raises(ValidationError):
        snap.asof.market_phase = MarketPhase.CLOSED
    with pytest.raises(TypeError):
        snap.asof.sources["new"] = SourceStatus(
            freshness=SourceFreshness.FRESH
        )


def test_snapshot_hash_matches_embedded_context_after_copy():
    snap = make_snapshot(_asof(), "snap-1")
    assert (
        snap.content_hash
        == make_snapshot(snap.asof, "snap-2").content_hash
    )


def test_snapshot_hash_is_over_versioned_payload_not_audit_fields():
    snap_a = make_snapshot(_asof(), "snap-a")
    snap_b = make_snapshot(_asof(), "snap-b")
    assert snap_a.snapshot_id != snap_b.snapshot_id
    assert snap_a.captured_at_utc != snap_b.captured_at_utc
    assert snap_a.content_hash == snap_b.content_hash


def test_snapshot_hash_matches_versioned_payload_sha256():
    asof = _asof()
    expected = hashlib.sha256(
        canonicalize_snapshot_payload(asof).encode("utf-8")
    ).hexdigest()
    assert make_snapshot(asof, "snap-1").content_hash == expected


def test_hash_differs_when_source_status_changes():
    asof_fresh = _asof()
    asof_stale = _asof(
        sources={
            "quotes": SourceStatus(
                provider="quotes",
                freshness=SourceFreshness.STALE,
                last_update_utc=UTC_NOW,
            ),
        },
    )
    a = make_snapshot(asof_fresh, "a")
    b = make_snapshot(asof_stale, "b")
    assert a.content_hash != b.content_hash


def test_source_order_does_not_change_canonical_hash():
    quotes = SourceStatus(provider="quotes", freshness=SourceFreshness.FRESH)
    actions = SourceStatus(provider="actions", freshness=SourceFreshness.STALE)
    asof_a = _asof(sources={"quotes": quotes, "actions": actions})
    asof_b = _asof(sources={"actions": actions, "quotes": quotes})
    assert (
        make_snapshot(asof_a, "a").content_hash
        == make_snapshot(asof_b, "b").content_hash
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
    asof_a = _asof(sources={"quotes": status_a})
    asof_b = _asof(sources={"quotes": status_b})
    assert (
        make_snapshot(asof_a, "a").content_hash
        == make_snapshot(asof_b, "b").content_hash
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
    asof_a = _asof(sources={"official_close": status_a})
    asof_b = _asof(sources={"official_close": status_b})

    assert (
        make_snapshot(asof_a, "a").content_hash
        == make_snapshot(asof_b, "b").content_hash
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
    asof_a = _asof(sources={"official_close": status_a})
    asof_b = _asof(sources={"official_close": status_b})

    assert (
        make_snapshot(asof_a, "a").content_hash
        == make_snapshot(asof_b, "b").content_hash
    )


def test_publication_state_change_changes_snapshot_hash():
    asof_published = _asof_with_publication(
        publication_state=PublicationState.PUBLISHED.value
    )
    asof_pre_published = _asof_with_publication(
        publication_state=PublicationState.PRE_PUBLISHED.value
    )

    assert (
        make_snapshot(asof_published, "published").content_hash
        != make_snapshot(asof_pre_published, "pre-published").content_hash
    )


def test_canonical_state_change_changes_snapshot_hash():
    asof_canonical = _asof_with_publication(
        canonical_state=CanonicalState.CANONICAL.value
    )
    asof_provisional = _asof_with_publication(
        canonical_state=CanonicalState.PROVISIONAL.value
    )

    assert (
        make_snapshot(asof_canonical, "canonical").content_hash
        != make_snapshot(asof_provisional, "provisional").content_hash
    )


def test_publication_utc_change_changes_snapshot_hash():
    asof_initial = _asof_with_publication(
        publication_utc="2026-05-12T21:05:00Z"
    )
    asof_later = _asof_with_publication(
        publication_utc="2026-05-12T21:10:00Z"
    )

    assert (
        make_snapshot(asof_initial, "initial").content_hash
        != make_snapshot(asof_later, "later").content_hash
    )


def test_asserted_at_utc_change_changes_snapshot_hash():
    asof_initial = _asof_with_publication(
        asserted_at_utc="2026-05-12T21:06:00Z"
    )
    asof_later = _asof_with_publication(
        asserted_at_utc="2026-05-12T21:07:00Z"
    )

    assert (
        make_snapshot(asof_initial, "initial").content_hash
        != make_snapshot(asof_later, "later").content_hash
    )


def test_snapshot_audit_fields_do_not_change_publication_hash():
    asof = _asof_with_publication()
    content_hash = make_snapshot(asof, "base").content_hash
    snap_a = AsOfSnapshot(
        snapshot_id="audit-record-a",
        captured_at_utc=datetime(2026, 5, 12, 21, 10, 0, tzinfo=timezone.utc),
        asof=asof,
        content_hash=content_hash,
    )
    snap_b = AsOfSnapshot(
        snapshot_id="audit-record-b",
        captured_at_utc=datetime(2026, 5, 12, 21, 15, 0, tzinfo=timezone.utc),
        asof=asof,
        content_hash=content_hash,
    )

    assert snap_a.snapshot_id != snap_b.snapshot_id
    assert snap_a.captured_at_utc != snap_b.captured_at_utc
    assert snap_a.content_hash == snap_b.content_hash


def test_publication_assertion_exactly_at_cutoff_is_identity_admissible():
    cutoff = datetime(2026, 5, 12, 21, 6, 0, tzinfo=timezone.utc)
    asof = _asof(
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
    first = make_snapshot(asof, "first")
    second = make_snapshot(asof, "second")

    assert asof.knowledge_cutoff_utc == cutoff
    assert first.snapshot_id != second.snapshot_id
    assert first.content_hash == second.content_hash


def test_publication_assertion_after_cutoff_is_identity_distinct():
    cutoff = datetime(2026, 5, 12, 21, 6, 0, tzinfo=timezone.utc)
    asof_at_cutoff = _asof(
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
    asof_after_cutoff = _asof(
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
        make_snapshot(asof_at_cutoff, "at-cutoff").content_hash
        != make_snapshot(asof_after_cutoff, "after-cutoff").content_hash
    )


def test_withdrawal_metadata_changes_snapshot_hash():
    asof_published = _asof_with_publication()
    asof_withdrawn = _asof_with_publication(
        withdrawal_utc="2026-05-12T21:30:00Z",
        withdrawal_id="withdrawal-official-close-2026-05-12-v1",
    )

    assert (
        make_snapshot(asof_published, "published").content_hash
        != make_snapshot(asof_withdrawn, "withdrawn").content_hash
    )


def test_supersession_metadata_changes_snapshot_hash():
    asof_original = _asof_with_publication()
    asof_superseded = _asof_with_publication(
        superseded_utc="2026-05-12T22:00:00Z",
        superseded_by="official-close-2026-05-12-v2",
    )

    assert (
        make_snapshot(asof_original, "original").content_hash
        != make_snapshot(asof_superseded, "superseded").content_hash
    )
