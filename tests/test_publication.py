"""Tests for the pure publication-readiness evaluator."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from asof123.calendars.xnys import XNYSCalendar
from asof123.enums import CanonicalState, Perspective, PublicationState, SourceFreshness
from asof123.errors import ErrorReasonCode
from asof123.models import SourceStatus
from asof123.publication import (
    PublicationReadinessResult,
    evaluate_publication_readiness,
)
from asof123.requests import ResolveRequest
from asof123.resolver import ResolverError, resolve


CUTOFF = datetime(2026, 5, 12, 21, 6, 0, tzinfo=timezone.utc)


def _publication_metadata(**overrides) -> dict:
    publication = {
        "publication_state": PublicationState.PUBLISHED.value,
        "canonical_state": CanonicalState.CANONICAL.value,
        "publication_utc": "2026-05-12T21:05:00Z",
        "asserted_at_utc": "2026-05-12T21:06:00Z",
    }
    publication.update(overrides)
    return {"publication": publication}


def _source(**publication_overrides) -> SourceStatus:
    return SourceStatus(
        provider="official-close",
        freshness=SourceFreshness.FRESH,
        last_update_utc=CUTOFF,
        metadata=_publication_metadata(**publication_overrides),
    )


def _evaluate(
    *,
    perspective: Perspective = Perspective.CANONICAL,
    sources: dict[str, SourceStatus] | None = None,
) -> PublicationReadinessResult:
    return evaluate_publication_readiness(
        perspective=perspective,
        knowledge_cutoff_utc=CUTOFF,
        sources=sources if sources is not None else {"official_close": _source()},
    )


def test_no_publication_metadata_not_ready():
    result = _evaluate(
        sources={
            "quotes": SourceStatus(
                provider="quotes",
                freshness=SourceFreshness.FRESH,
                last_update_utc=CUTOFF,
            )
        }
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_METADATA_MISSING"


def test_publication_not_published_not_ready():
    result = _evaluate(
        sources={
            "official_close": _source(
                publication_state=PublicationState.PRE_PUBLISHED.value
            )
        }
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_NOT_PUBLISHED"
    assert result.publication_state is PublicationState.PRE_PUBLISHED


def test_canonical_not_canonical_not_ready():
    result = _evaluate(
        sources={
            "official_close": _source(
                canonical_state=CanonicalState.PROVISIONAL.value
            )
        }
    )

    assert result.ready is False
    assert result.reason_code == "CANONICAL_NOT_CANONICAL"
    assert result.canonical_state is CanonicalState.PROVISIONAL


def test_missing_publication_timestamp_not_ready():
    metadata = _publication_metadata()
    del metadata["publication"]["publication_utc"]
    result = _evaluate(
        sources={
            "official_close": SourceStatus(
                provider="official-close",
                freshness=SourceFreshness.FRESH,
                last_update_utc=CUTOFF,
                metadata=metadata,
            )
        }
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_METADATA_INCOMPLETE"
    assert "publication_utc" in (result.explanation or "")


def test_missing_asserted_timestamp_not_ready():
    metadata = _publication_metadata()
    del metadata["publication"]["asserted_at_utc"]
    result = _evaluate(
        sources={
            "official_close": SourceStatus(
                provider="official-close",
                freshness=SourceFreshness.FRESH,
                last_update_utc=CUTOFF,
                metadata=metadata,
            )
        }
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_METADATA_INCOMPLETE"
    assert "asserted_at_utc" in (result.explanation or "")


def test_replay_assertion_after_cutoff_not_ready():
    result = _evaluate(
        perspective=Perspective.REPLAY,
        sources={
            "official_close": _source(asserted_at_utc="2026-05-12T21:07:00Z")
        },
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_ASSERTION_AFTER_CUTOFF"


def test_replay_publication_after_cutoff_not_ready():
    result = _evaluate(
        perspective=Perspective.REPLAY,
        sources={
            "official_close": _source(publication_utc="2026-05-12T21:07:00Z")
        },
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_AFTER_CUTOFF"


def test_historical_assertion_after_cutoff_not_ready():
    result = _evaluate(
        perspective=Perspective.HISTORICAL,
        sources={
            "official_close": _source(asserted_at_utc="2026-05-12T21:07:00Z")
        },
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_ASSERTION_AFTER_CUTOFF"


def test_historical_publication_after_cutoff_not_ready():
    result = _evaluate(
        perspective=Perspective.HISTORICAL,
        sources={
            "official_close": _source(publication_utc="2026-05-12T21:07:00Z")
        },
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_AFTER_CUTOFF"


def test_replay_assertion_exactly_at_cutoff_ready():
    result = _evaluate(
        perspective=Perspective.REPLAY,
        sources={
            "official_close": _source(asserted_at_utc="2026-05-12T21:06:00Z")
        },
    )

    assert result.ready is True
    assert result.asserted_at_utc == CUTOFF


def test_replay_publication_exactly_at_cutoff_ready():
    result = _evaluate(
        perspective=Perspective.REPLAY,
        sources={
            "official_close": _source(publication_utc="2026-05-12T21:06:00Z")
        },
    )

    assert result.ready is True
    assert result.publication_utc == CUTOFF


def test_invalid_publication_state_not_ready():
    result = _evaluate(
        sources={"official_close": _source(publication_state="FINALISH")}
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_METADATA_INVALID"
    assert "publication_state" in (result.explanation or "")


def test_invalid_canonical_state_not_ready():
    result = _evaluate(
        sources={"official_close": _source(canonical_state="OFFICIAL")}
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_METADATA_INVALID"
    assert "canonical_state" in (result.explanation or "")


def test_invalid_timestamp_not_ready():
    result = _evaluate(
        sources={"official_close": _source(publication_utc="not-a-time")}
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_METADATA_INVALID"
    assert "valid ISO 8601" in (result.explanation or "")


def test_naive_timestamp_not_ready():
    result = _evaluate(
        sources={"official_close": _source(publication_utc="2026-05-12T21:05:00")}
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_METADATA_INVALID"
    assert "timezone-aware UTC" in (result.explanation or "")


def test_non_utc_timestamp_not_ready():
    result = _evaluate(
        sources={
            "official_close": _source(publication_utc="2026-05-12T17:05:00-04:00")
        }
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_METADATA_INVALID"
    assert "must be UTC" in (result.explanation or "")


def test_published_and_canonical_ready():
    result = _evaluate()

    assert result.ready is True
    assert result.reason_code is None
    assert result.source_name == "official_close"
    assert result.publication_state is PublicationState.PUBLISHED
    assert result.canonical_state is CanonicalState.CANONICAL
    assert result.publication_utc == datetime(2026, 5, 12, 21, 5, tzinfo=timezone.utc)
    assert result.asserted_at_utc == CUTOFF


def test_evaluator_is_deterministic_and_does_not_mutate_inputs():
    source = _source()
    sources = {"official_close": source}
    before = source.model_dump(mode="json")

    first = _evaluate(sources=sources)
    second = _evaluate(sources=sources)

    assert first == second
    assert source.model_dump(mode="json") == before
    assert sources == {"official_close": source}


def test_multiple_publication_assertions_fail_closed():
    result = _evaluate(
        sources={
            "official_close_a": _source(),
            "official_close_b": _source(),
        }
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_ASSERTION_AMBIGUOUS"


def test_conflicting_publication_assertions_fail_closed():
    result = _evaluate(
        sources={
            "official_close_a": _source(publication_state=PublicationState.PUBLISHED.value),
            "official_close_b": _source(publication_state=PublicationState.PRE_PUBLISHED.value),
        }
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_ASSERTION_AMBIGUOUS"


def test_duplicate_publication_assertions_fail_closed():
    result = _evaluate(
        sources={
            "official_close_a": _source(),
            "official_close_b": _source(),
        }
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_ASSERTION_AMBIGUOUS"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("withdrawal_utc", "2026-05-12T21:30:00Z"),
        ("withdrawal_id", "withdrawal-official-close-2026-05-12-v1"),
        ("superseded_utc", "2026-05-12T22:00:00Z"),
        ("superseded_by", "official-close-2026-05-12-v2"),
    ],
)
def test_unsupported_advanced_metadata_fails_closed(field_name, value):
    result = _evaluate(
        sources={"official_close": _source(**{field_name: value})}
    )

    assert result.ready is False
    assert result.reason_code == "PUBLICATION_METADATA_UNSUPPORTED"
    assert field_name in (result.explanation or "")


def test_null_advanced_metadata_is_ignored_until_supported():
    result = _evaluate(
        sources={
            "official_close": _source(
                withdrawal_utc=None,
                withdrawal_id=None,
                superseded_utc=None,
                superseded_by=None,
            )
        }
    )

    assert result.ready is True


def test_resolver_canonical_without_publication_metadata_fails_closed():
    request = ResolveRequest(
        perspective=Perspective.CANONICAL,
        market="XNYS",
        market_timezone="America/New_York",
    )

    with pytest.raises(ResolverError) as exc_info:
        resolve(request, {"XNYS": XNYSCalendar()})

    assert exc_info.value.reason_code is ErrorReasonCode.PUBLICATION_METADATA_MISSING
