"""Source admissibility policy for the resolver.

`SourcePolicy` is an optional resolver input. When omitted, resolver behavior
is unchanged: caller-supplied providers are reported and no required-source,
freshness-threshold, or cutoff-admissibility checks are applied.

The policy is deliberately small. It does not discover providers, persist
source state, manage SLAs, retry providers, or implement a mutable registry.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import Perspective, SourceFreshness
from .errors import ErrorReasonCode
from .models import SourceStatus


def _check_source_name(value: str, field_name: str = "source name") -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _check_positive_seconds(value: Optional[int], field_name: str) -> Optional[int]:
    if value is None:
        return value
    if value <= 0:
        raise ValueError(f"{field_name} must be positive seconds")
    return value


class _FrozenDict(dict):
    """A dict-shaped mapping that rejects mutation after validation."""

    def _blocked(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("validated mapping is immutable")

    __setitem__ = _blocked
    __delitem__ = _blocked
    clear = _blocked
    pop = _blocked
    popitem = _blocked
    setdefault = _blocked
    update = _blocked


class SourcePolicy(BaseModel):
    """Optional policy for required sources and source admissibility.

    Fields:
    - `required_sources`: source names that must appear in the resolved
      AsOf. Missing required sources become explicit `MISSING` statuses.
    - `max_age_seconds`: default maximum age for any source with
      `last_update_utc`.
    - `max_age_seconds_by_source`: per-source maximum age overrides.

    Knowledge-cutoff admissibility is implicit for `REPLAY` and `HISTORICAL`:
    if a source reports `last_update_utc > knowledge_cutoff_utc`, the resolver
    marks that source `NOT_PUBLISHED` with reason metadata under this policy.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    required_sources: frozenset[str] = Field(default_factory=frozenset)
    max_age_seconds: Optional[int] = None
    max_age_seconds_by_source: dict[str, int] = Field(default_factory=_FrozenDict)

    @field_validator("required_sources", mode="before")
    @classmethod
    def _check_required_sources(cls, v) -> frozenset[str]:
        if v is None:
            return frozenset()
        if isinstance(v, str):
            raise ValueError("required_sources must be an iterable of strings")
        try:
            values = frozenset(v)
        except TypeError as exc:
            raise ValueError("required_sources must be an iterable of strings") from exc
        for name in values:
            _check_source_name(name)
        return values

    @field_validator("max_age_seconds")
    @classmethod
    def _check_max_age_seconds(cls, v: Optional[int]) -> Optional[int]:
        return _check_positive_seconds(v, "max_age_seconds")

    @field_validator("max_age_seconds_by_source")
    @classmethod
    def _check_max_age_seconds_by_source(cls, v: dict[str, int]) -> dict[str, int]:
        for name, seconds in v.items():
            _check_source_name(name, "max_age_seconds_by_source key")
            _check_positive_seconds(seconds, f"max_age_seconds_by_source[{name!r}]")
        return _FrozenDict(v)

    def max_age_for(self, source_name: str) -> Optional[int]:
        """Return the configured max age in seconds for `source_name`."""
        return self.max_age_seconds_by_source.get(source_name, self.max_age_seconds)


def _with_source_policy_status(
    status: SourceStatus,
    *,
    freshness: SourceFreshness,
    reason_code: ErrorReasonCode,
    explanation: str,
) -> SourceStatus:
    metadata = dict(status.metadata)
    # Policy status is the active resolver decision. Preserve the provider's
    # original diagnostic fields under metadata so audits can reconstruct both
    # layers without adding new ontology fields.
    metadata["policy"] = {
        "previous_freshness": status.freshness.value,
        "previous_reason_code": status.reason_code,
        "previous_explanation": status.explanation,
        "reason_code": reason_code.value,
        "explanation": explanation,
    }
    payload = status.model_dump()
    payload.update(
        {
            "freshness": freshness,
            "reason_code": reason_code.value,
            "explanation": explanation,
            "metadata": metadata,
        }
    )
    return SourceStatus(**payload)


def apply_source_policy(
    *,
    perspective: Perspective,
    knowledge_cutoff_utc: datetime,
    now_utc: datetime,
    sources: dict[str, SourceStatus],
    policy: SourcePolicy,
) -> dict[str, SourceStatus]:
    """Return a new source map with `policy` applied.

    Invariants:
    - Pure function: no provider calls, calendar calls, IO, retries, mutation,
      persistence, or wall-clock reads.
    - Deterministic output for the same inputs.
    - Input `sources` and contained `SourceStatus` instances are not mutated.
    - Missing required sources become explicit `MISSING` statuses.
    - Cutoff admissibility applies only to `REPLAY` and `HISTORICAL`.
    - Max-age checks skip sources without `last_update_utc` and preserve
      provider-supplied `FAILED`, `MISSING`, `STALE`, and `NOT_PUBLISHED`.
    """
    resolved = dict(sources)

    for name in sorted(policy.required_sources):
        if name not in resolved:
            resolved[name] = SourceStatus(
                provider=name,
                freshness=SourceFreshness.MISSING,
                reason_code=ErrorReasonCode.REQUIRED_SOURCE_MISSING.value,
                explanation=f"Required source {name!r} did not report",
            )

    for name, status in list(resolved.items()):
        if (
            perspective in (Perspective.REPLAY, Perspective.HISTORICAL)
            and status.last_update_utc is not None
            and status.last_update_utc > knowledge_cutoff_utc
        ):
            resolved[name] = _with_source_policy_status(
                status,
                freshness=SourceFreshness.NOT_PUBLISHED,
                reason_code=ErrorReasonCode.SOURCE_NOT_ADMISSIBLE,
                explanation=(
                    f"Source {name!r} last_update_utc="
                    f"{status.last_update_utc.isoformat()} is after "
                    f"knowledge_cutoff_utc={knowledge_cutoff_utc.isoformat()}"
                ),
            )
            continue

        max_age_seconds = policy.max_age_for(name)
        if (
            max_age_seconds is not None
            and status.last_update_utc is not None
            and status.freshness not in (
                SourceFreshness.FAILED,
                SourceFreshness.MISSING,
                SourceFreshness.STALE,
                SourceFreshness.NOT_PUBLISHED,
            )
        ):
            age_seconds = (now_utc - status.last_update_utc).total_seconds()
            if age_seconds > max_age_seconds:
                resolved[name] = _with_source_policy_status(
                    status,
                    freshness=SourceFreshness.STALE,
                    reason_code=ErrorReasonCode.SOURCE_STALE,
                    explanation=(
                        f"Source {name!r} age {age_seconds:.0f}s exceeds "
                        f"max_age_seconds={max_age_seconds}"
                    ),
                )

    return resolved
