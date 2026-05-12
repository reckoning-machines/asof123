"""Resolver request model for asof123.

`ResolveRequest` is the inbound shape for any caller asking for a
`TemporalContext`. It enforces the contract's preconditions before any
resolver logic runs:

- UTC for *_utc fields (timezone-aware, offset must be +00:00)
- IANA Region/City (or 'UTC') for `market_timezone`
- uppercase non-empty `market` code
- per-Perspective cross-field rules binding which datetime fields are
  required or forbidden, per PRODUCT_CONTRACT.md sections 4, 12, and 13

This module defines a request type only. It does not resolve, schedule,
or persist anything.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationInfo,
    field_validator,
    model_validator,
)

from .enums import Perspective
from .models import (
    _require_iana_region_city,
    _require_uppercase_market,
    _require_utc,
)


class ResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    perspective: Perspective
    market: str
    market_timezone: str
    as_of_utc: Optional[datetime] = None
    knowledge_cutoff_utc: Optional[datetime] = None

    @field_validator("market")
    @classmethod
    def _check_market(cls, v: str) -> str:
        return _require_uppercase_market(v)

    @field_validator("market_timezone")
    @classmethod
    def _check_timezone(cls, v: str) -> str:
        return _require_iana_region_city(v)

    @field_validator("as_of_utc", "knowledge_cutoff_utc")
    @classmethod
    def _check_utc(
        cls, v: Optional[datetime], info: ValidationInfo
    ) -> Optional[datetime]:
        if v is None:
            return v
        return _require_utc(v, info.field_name or "datetime")

    @model_validator(mode="after")
    def _check_cross_field_rules(self) -> "ResolveRequest":
        p = self.perspective

        if p in (Perspective.REPLAY, Perspective.HISTORICAL):
            if self.as_of_utc is None:
                raise ValueError(
                    f"perspective={p.value} requires as_of_utc; "
                    "see PRODUCT_CONTRACT.md section 4"
                )
            if self.knowledge_cutoff_utc is None:
                raise ValueError(
                    f"perspective={p.value} requires knowledge_cutoff_utc; "
                    "see PRODUCT_CONTRACT.md section 4"
                )

        if p == Perspective.LIVE:
            if self.as_of_utc is not None:
                raise ValueError(
                    "perspective=LIVE must not provide as_of_utc; "
                    "LIVE resolves to the current instant by definition. "
                    "See PRODUCT_CONTRACT.md section 4."
                )
            if self.knowledge_cutoff_utc is not None:
                raise ValueError(
                    "perspective=LIVE must not provide knowledge_cutoff_utc; "
                    "LIVE has no knowledge cutoff. "
                    "See PRODUCT_CONTRACT.md section 4."
                )

        if p == Perspective.CANONICAL:
            if self.as_of_utc is not None:
                raise ValueError(
                    "perspective=CANONICAL must not provide as_of_utc; "
                    "CANONICAL resolves against the system of record's "
                    "publication, not an arbitrary past instant. "
                    "See PRODUCT_CONTRACT.md section 4."
                )

        # PREVIEW and PRE_TRADE_INTENT: as_of_utc may be omitted, and
        # knowledge_cutoff_utc may be supplied. No additional rejection.
        # EXECUTED: both optional fields are allowed. No additional rejection.

        if (
            self.knowledge_cutoff_utc is not None
            and self.as_of_utc is not None
            and self.knowledge_cutoff_utc > self.as_of_utc
        ):
            raise ValueError(
                "knowledge_cutoff_utc must be <= as_of_utc when both are "
                "provided; future-dated knowledge must not leak into past "
                "contexts (PRODUCT_CONTRACT.md section 13)"
            )

        return self
