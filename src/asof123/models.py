"""Pydantic v2 models for the asof123 ontology.

These models enforce the rules pinned in PRODUCT_CONTRACT.md sections 7-13:
strict UTC for *_utc fields, IANA Region/City timezones (or UTC) for
market_timezone, uppercase market codes, and the fail-closed semantics that
bind Perspective to ExecutionState and CanonicalState, and that require an
explicit reason for any UNKNOWN enum value.

This module defines types only. It does not resolve, fetch, schedule,
persist, or expose anything.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from .enums import (
    CanonicalState,
    ExecutionState,
    MarketPhase,
    Perspective,
    PriceBasis,
    PublicationState,
    SourceFreshness,
)


SNAPSHOT_SCHEMA_VERSION = "asof123.snapshot.v2"
SEMANTIC_CONTRACT_VERSION = "asof123.contract.v1"
SNAPSHOT_HASH_ALGORITHM = "sha256"


class _FrozenDict(dict):
    """A dict that serializes normally but rejects mutation after validation."""

    def _blocked(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("validated mapping is immutable")

    __setitem__ = _blocked
    __delitem__ = _blocked
    clear = _blocked
    pop = _blocked
    popitem = _blocked
    setdefault = _blocked
    update = _blocked


def _freeze_json_value(value: Any, field_name: str) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} must not contain NaN or Infinity")
        return value
    if isinstance(value, list):
        return tuple(_freeze_json_value(item, field_name) for item in value)
    if isinstance(value, dict):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field_name} keys must be strings")
            frozen[key] = _freeze_json_value(item, field_name)
        return _FrozenDict(frozen)
    raise ValueError(
        f"{field_name} must contain only JSON-compatible deterministic values"
    )


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            f"{field_name} must be timezone-aware; naive datetimes are not allowed"
        )
    if value.utcoffset() != timedelta(0):
        raise ValueError(
            f"{field_name} must be in UTC (offset +00:00); "
            f"got offset {value.utcoffset()}"
        )
    return value


def _require_iana_region_city(name: str) -> str:
    if not isinstance(name, str) or not name:
        raise ValueError("market_timezone must be a non-empty string")
    if name != "UTC" and "/" not in name:
        raise ValueError(
            f"market_timezone must be an IANA Region/City identifier or 'UTC'; "
            f"got {name!r}. Abbreviations like 'EST' are not allowed."
        )
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"market_timezone {name!r} is not a known IANA timezone"
        ) from exc
    return name


def _require_uppercase_market(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("market must be a non-empty string")
    if value != value.upper():
        raise ValueError(f"market must be uppercase; got {value!r}")
    return value


class MarketIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    market: str
    market_timezone: str

    @field_validator("market")
    @classmethod
    def _check_market(cls, v: str) -> str:
        return _require_uppercase_market(v)

    @field_validator("market_timezone")
    @classmethod
    def _check_timezone(cls, v: str) -> str:
        return _require_iana_region_city(v)


class SourceStatus(BaseModel):
    """Reported state for one source.

    Publication metadata convention, used before adding any publication
    readiness evaluator:

        SourceStatus.metadata["publication"]

    Expected semantic keys are `publication_state`, `canonical_state`,
    `publication_utc`, and `asserted_at_utc`. Future semantic keys may include
    `assertion_id`, `authority_id`, `withdrawal_utc`, `withdrawal_id`,
    `superseded_utc`, `superseded_by`, and `explanation`.

    This model only stores deterministic JSON-compatible metadata. It does not
    validate publication readiness, infer canonicality, or implement canonical
    publication gating.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Optional[str] = None
    freshness: SourceFreshness
    last_update_utc: Optional[datetime] = None
    expected_publication_utc: Optional[datetime] = None
    reason_code: Optional[str] = None
    explanation: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("provider")
    @classmethod
    def _check_provider(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v:
            raise ValueError("provider, if present, must be a non-empty string")
        return v

    @field_validator("last_update_utc", "expected_publication_utc")
    @classmethod
    def _check_utc(cls, v: Optional[datetime], info: ValidationInfo) -> Optional[datetime]:
        if v is None:
            return v
        return _require_utc(v, info.field_name or "datetime")

    @field_validator("metadata")
    @classmethod
    def _check_metadata(cls, v: dict[str, Any]) -> dict[str, Any]:
        return _freeze_json_value(v, "metadata")


class AsOf(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    resolved_at_utc: datetime
    perspective: Perspective
    market: str
    market_timezone: str
    market_datetime: Optional[datetime] = None
    market_date: Optional[date] = None
    business_date: date
    market_phase: MarketPhase
    knowledge_cutoff_utc: datetime
    price_basis: PriceBasis
    execution_state: ExecutionState = ExecutionState.NOT_EXECUTED
    publication_state: PublicationState
    canonical_state: CanonicalState
    sources: dict[str, SourceStatus] = Field(default_factory=dict)
    reason_code: Optional[str] = None
    explanation: Optional[str] = None

    @field_validator("resolved_at_utc", "knowledge_cutoff_utc")
    @classmethod
    def _check_utc(cls, v: datetime, info: ValidationInfo) -> datetime:
        return _require_utc(v, info.field_name or "datetime")

    @field_validator("market_datetime")
    @classmethod
    def _check_market_datetime(
        cls, v: Optional[datetime], info: ValidationInfo
    ) -> Optional[datetime]:
        if v is None:
            return v
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError(
                f"{info.field_name or 'market_datetime'} must be timezone-aware"
            )
        return v

    @field_validator("market")
    @classmethod
    def _check_market(cls, v: str) -> str:
        return _require_uppercase_market(v)

    @field_validator("market_timezone")
    @classmethod
    def _check_timezone(cls, v: str) -> str:
        return _require_iana_region_city(v)

    @field_validator("sources")
    @classmethod
    def _check_sources(cls, v: dict[str, SourceStatus]) -> dict[str, SourceStatus]:
        for key in v:
            if not isinstance(key, str) or not key:
                raise ValueError("source names in sources must be non-empty strings")
        return _FrozenDict(v)

    @model_validator(mode="after")
    def _check_fail_closed(self) -> "AsOf":
        derived_market_datetime = self.resolved_at_utc.astimezone(
            ZoneInfo(self.market_timezone)
        )
        derived_market_date = derived_market_datetime.date()
        if self.market_datetime is None:
            object.__setattr__(
                self, "market_datetime", derived_market_datetime
            )
        elif self.market_datetime.isoformat() != derived_market_datetime.isoformat():
            raise ValueError(
                "market_datetime is derived from resolved_at_utc and "
                "market_timezone; caller-supplied values must match the "
                "derived market-local projection"
            )
        if self.market_date is None:
            object.__setattr__(self, "market_date", derived_market_date)
        elif self.market_date != derived_market_date:
            raise ValueError(
                "market_date is derived from resolved_at_utc and "
                "market_timezone; caller-supplied values must match the "
                "derived market-local date"
            )
        if (
            self.perspective == Perspective.CANONICAL
            and self.canonical_state != CanonicalState.CANONICAL
        ):
            raise ValueError(
                "perspective=CANONICAL requires canonical_state=CANONICAL "
                f"(got {self.canonical_state.value}); see PRODUCT_CONTRACT.md section 13"
            )
        if self.perspective == Perspective.EXECUTED and self.execution_state in (
            ExecutionState.INTENDED,
            ExecutionState.WORKING,
        ):
            raise ValueError(
                "perspective=EXECUTED forbids execution_state in {INTENDED, WORKING} "
                f"(got {self.execution_state.value}); "
                "see PRODUCT_CONTRACT.md section 7"
            )
        if self.price_basis == PriceBasis.UNKNOWN and not (
            self.reason_code and self.explanation
        ):
            raise ValueError(
                "price_basis=UNKNOWN requires reason_code and explanation "
                "per the fail-closed rule (PRODUCT_CONTRACT.md section 13)"
            )
        if self.publication_state == PublicationState.UNKNOWN and not (
            self.reason_code and self.explanation
        ):
            raise ValueError(
                "publication_state=UNKNOWN requires reason_code and explanation "
                "per the fail-closed rule (PRODUCT_CONTRACT.md section 13)"
            )
        if self.canonical_state == CanonicalState.UNKNOWN and not (
            self.reason_code and self.explanation
        ):
            raise ValueError(
                "canonical_state=UNKNOWN requires reason_code and explanation "
                "per the fail-closed rule (PRODUCT_CONTRACT.md section 13)"
            )
        return self


class AsOfSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str
    snapshot_schema_version: str = SNAPSHOT_SCHEMA_VERSION
    semantic_contract_version: str = SEMANTIC_CONTRACT_VERSION
    hash_algorithm: str = SNAPSHOT_HASH_ALGORITHM
    captured_at_utc: datetime
    asof: AsOf
    content_hash: Optional[str] = None

    @field_validator("snapshot_id")
    @classmethod
    def _check_snapshot_id(cls, v: str) -> str:
        if not v:
            raise ValueError("snapshot_id must be a non-empty string")
        return v

    @field_validator("snapshot_schema_version")
    @classmethod
    def _check_snapshot_schema_version(cls, v: str) -> str:
        if v != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                "snapshot_schema_version must be "
                f"{SNAPSHOT_SCHEMA_VERSION!r}"
            )
        return v

    @field_validator("semantic_contract_version")
    @classmethod
    def _check_semantic_contract_version(cls, v: str) -> str:
        if v != SEMANTIC_CONTRACT_VERSION:
            raise ValueError(
                "semantic_contract_version must be "
                f"{SEMANTIC_CONTRACT_VERSION!r}"
            )
        return v

    @field_validator("hash_algorithm")
    @classmethod
    def _check_hash_algorithm(cls, v: str) -> str:
        if v != SNAPSHOT_HASH_ALGORITHM:
            raise ValueError(
                f"hash_algorithm must be {SNAPSHOT_HASH_ALGORITHM!r}"
            )
        return v

    @field_validator("captured_at_utc")
    @classmethod
    def _check_captured_at_utc(cls, v: datetime) -> datetime:
        return _require_utc(v, "captured_at_utc")

    @field_validator("content_hash")
    @classmethod
    def _check_content_hash(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v:
            raise ValueError("content_hash, if present, must be a non-empty string")
        return v
