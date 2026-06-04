"""Pure publication-readiness evaluation.

This module evaluates supplied publication facts only. It does not call
providers, calendars, clocks, files, networks, registries, persistence, or the
resolver. It does not create a canonical success path.

Publication facts are read from:

    SourceStatus.metadata["publication"]

The first slice supports only `publication_state`, `canonical_state`,
`publication_utc`, and `asserted_at_utc`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .enums import CanonicalState, Perspective, PublicationState
from .models import SourceStatus


@dataclass(frozen=True)
class PublicationReadinessResult:
    """Deterministic result for supplied publication facts.

    `ready=True` means exactly one supplied publication assertion proves
    `publication_state=PUBLISHED` and `canonical_state=CANONICAL` for the
    requested perspective and cutoff rules. `ready=False` is fail-closed and
    includes a stable `reason_code` plus advisory `explanation`.
    """

    ready: bool
    reason_code: str | None = None
    explanation: str | None = None
    source_name: str | None = None
    publication_state: PublicationState | None = None
    canonical_state: CanonicalState | None = None
    publication_utc: datetime | None = None
    asserted_at_utc: datetime | None = None


@dataclass(frozen=True)
class _ParsedPublicationMetadata:
    source_name: str
    publication_state: PublicationState
    canonical_state: CanonicalState
    publication_utc: datetime
    asserted_at_utc: datetime


def evaluate_publication_readiness(
    *,
    perspective: Perspective,
    knowledge_cutoff_utc: datetime,
    sources: Mapping[str, SourceStatus],
) -> PublicationReadinessResult:
    """Evaluate whether supplied publication facts prove canonical readiness.

    Invariants:
    - Pure function: no provider calls, calendar calls, IO, retries, mutation,
      persistence, or wall-clock reads.
    - Deterministic output for the same inputs.
    - Input `sources` and contained `SourceStatus` instances are not mutated.
    - Publication facts are consumed only from
      `SourceStatus.metadata["publication"]`.
    - Cutoff admissibility applies to `CANONICAL`, `REPLAY`, and `HISTORICAL`.
    - Multiple publication assertions fail closed; conflict resolution is a
      future slice.
    """
    assertions = [
        (name, publication)
        for name, status in sources.items()
        for publication in [_publication_metadata(status)]
        if publication is not None
    ]

    if not assertions:
        return _not_ready(
            "PUBLICATION_METADATA_MISSING",
            "No SourceStatus.metadata['publication'] assertion supplied",
        )
    if len(assertions) > 1:
        return _not_ready(
            "PUBLICATION_ASSERTION_AMBIGUOUS",
            "Multiple publication assertions supplied; conflict resolution is not implemented",
        )

    source_name, publication = assertions[0]
    parsed = _parse_publication_metadata(source_name, publication)
    if isinstance(parsed, PublicationReadinessResult):
        return parsed

    if parsed.publication_state is not PublicationState.PUBLISHED:
        return _not_ready(
            "PUBLICATION_NOT_PUBLISHED",
            f"publication_state={parsed.publication_state.value} does not prove readiness",
            source_name=parsed.source_name,
            publication_state=parsed.publication_state,
            canonical_state=parsed.canonical_state,
        )
    if parsed.canonical_state is not CanonicalState.CANONICAL:
        return _not_ready(
            "CANONICAL_NOT_CANONICAL",
            f"canonical_state={parsed.canonical_state.value} does not prove readiness",
            source_name=parsed.source_name,
            publication_state=parsed.publication_state,
            canonical_state=parsed.canonical_state,
        )

    if perspective in (Perspective.CANONICAL, Perspective.REPLAY, Perspective.HISTORICAL):
        if parsed.asserted_at_utc > knowledge_cutoff_utc:
            return _not_ready(
                "PUBLICATION_ASSERTION_AFTER_CUTOFF",
                (
                    f"asserted_at_utc={parsed.asserted_at_utc.isoformat()} is after "
                    f"knowledge_cutoff_utc={knowledge_cutoff_utc.isoformat()}"
                ),
                source_name=parsed.source_name,
                publication_state=parsed.publication_state,
                canonical_state=parsed.canonical_state,
                publication_utc=parsed.publication_utc,
                asserted_at_utc=parsed.asserted_at_utc,
            )
        if parsed.publication_utc > knowledge_cutoff_utc:
            return _not_ready(
                "PUBLICATION_AFTER_CUTOFF",
                (
                    f"publication_utc={parsed.publication_utc.isoformat()} is after "
                    f"knowledge_cutoff_utc={knowledge_cutoff_utc.isoformat()}"
                ),
                source_name=parsed.source_name,
                publication_state=parsed.publication_state,
                canonical_state=parsed.canonical_state,
                publication_utc=parsed.publication_utc,
                asserted_at_utc=parsed.asserted_at_utc,
            )

    return PublicationReadinessResult(
        ready=True,
        source_name=parsed.source_name,
        publication_state=parsed.publication_state,
        canonical_state=parsed.canonical_state,
        publication_utc=parsed.publication_utc,
        asserted_at_utc=parsed.asserted_at_utc,
    )


def _publication_metadata(status: SourceStatus) -> Mapping[str, Any] | None:
    publication = status.metadata.get("publication")
    if isinstance(publication, Mapping):
        return publication
    return None


def _parse_publication_metadata(
    source_name: str,
    publication: Mapping[str, Any],
) -> _ParsedPublicationMetadata | PublicationReadinessResult:
    """Return parsed publication metadata or a fail-closed result.

    This is an internal metadata boundary, not a public ontology object.
    Unsupported lifecycle metadata with a non-null value fails closed until
    withdrawal and supersession semantics are implemented.
    """
    for field_name in (
        "withdrawal_utc",
        "withdrawal_id",
        "superseded_utc",
        "superseded_by",
    ):
        if publication.get(field_name) is not None:
            return _not_ready(
                "PUBLICATION_METADATA_UNSUPPORTED",
                f"Publication metadata field {field_name} is not supported by this evaluator slice",
                source_name=source_name,
            )

    publication_state = _enum_value(
        PublicationState,
        publication.get("publication_state"),
        "publication_state",
        source_name=source_name,
    )
    if isinstance(publication_state, PublicationReadinessResult):
        return publication_state
    canonical_state = _enum_value(
        CanonicalState,
        publication.get("canonical_state"),
        "canonical_state",
        source_name=source_name,
    )
    if isinstance(canonical_state, PublicationReadinessResult):
        return canonical_state
    publication_utc = _utc_instant(
        publication.get("publication_utc"),
        "publication_utc",
        source_name=source_name,
    )
    if isinstance(publication_utc, PublicationReadinessResult):
        return publication_utc
    asserted_at_utc = _utc_instant(
        publication.get("asserted_at_utc"),
        "asserted_at_utc",
        source_name=source_name,
    )
    if isinstance(asserted_at_utc, PublicationReadinessResult):
        return asserted_at_utc

    return _ParsedPublicationMetadata(
        source_name=source_name,
        publication_state=publication_state,
        canonical_state=canonical_state,
        publication_utc=publication_utc,
        asserted_at_utc=asserted_at_utc,
    )


def _enum_value(enum_cls, value: Any, field_name: str, *, source_name: str | None = None):
    if value is None:
        return _not_ready(
            "PUBLICATION_METADATA_INCOMPLETE",
            f"Publication metadata missing {field_name}",
            source_name=source_name,
        )
    try:
        return enum_cls(value)
    except ValueError:
        return _not_ready(
            "PUBLICATION_METADATA_INVALID",
            f"Publication metadata has invalid {field_name}={value!r}",
            source_name=source_name,
        )


def _utc_instant(
    value: Any,
    field_name: str,
    *,
    source_name: str | None = None,
) -> datetime | PublicationReadinessResult:
    if value is None:
        return _not_ready(
            "PUBLICATION_METADATA_INCOMPLETE",
            f"Publication metadata missing {field_name}",
            source_name=source_name,
        )
    if not isinstance(value, str):
        return _not_ready(
            "PUBLICATION_METADATA_INVALID",
            f"Publication metadata {field_name} must be an ISO 8601 UTC string",
            source_name=source_name,
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return _not_ready(
            "PUBLICATION_METADATA_INVALID",
            f"Publication metadata {field_name} is not a valid ISO 8601 instant",
            source_name=source_name,
        )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return _not_ready(
            "PUBLICATION_METADATA_INVALID",
            f"Publication metadata {field_name} must be timezone-aware UTC",
            source_name=source_name,
        )
    if parsed.utcoffset() != timedelta(0):
        return _not_ready(
            "PUBLICATION_METADATA_INVALID",
            f"Publication metadata {field_name} must be UTC",
            source_name=source_name,
        )
    return parsed


def _not_ready(
    reason_code: str,
    explanation: str,
    *,
    source_name: str | None = None,
    publication_state: PublicationState | None = None,
    canonical_state: CanonicalState | None = None,
    publication_utc: datetime | None = None,
    asserted_at_utc: datetime | None = None,
) -> PublicationReadinessResult:
    return PublicationReadinessResult(
        ready=False,
        reason_code=reason_code,
        explanation=explanation,
        source_name=source_name,
        publication_state=publication_state,
        canonical_state=canonical_state,
        publication_utc=publication_utc,
        asserted_at_utc=asserted_at_utc,
    )
