"""FastAPI reference surface for asof123.

Exposes the in-process resolver and snapshot helper over HTTP. Calendars
and providers are injected at app construction time and stored on
`app.state`; nothing is loaded from the environment, from disk, or from
a database. There is no auth, no persistence, no scheduler, no
background work, and no mutable source registry.

`POST /sources/report` is intentionally a 501. The contract names it
(PRODUCT_CONTRACT.md section 14) but this pass deliberately does not
introduce a mutable registry; the endpoint exists so that the OpenAPI
shape matches the contract and so callers can detect that this
reference app is read-only.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator

from .calendar import MarketCalendar
from .calendars import XNYSCalendar
from .enums import Perspective, SourceFreshness
from .errors import ErrorReasonCode, ErrorResponse
from .models import AsOf, AsOfSnapshot, SourceStatus
from .policy import SourcePolicy
from .providers import ProviderReportError, SourceProvider
from .requests import AsOfRequest
from .resolver import ResolverError, resolve
from .snapshot import make_snapshot


class SnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    asof: AsOf

    @field_validator("snapshot_id")
    @classmethod
    def _check_snapshot_id(cls, v: str) -> str:
        if not v:
            raise ValueError("snapshot_id must be a non-empty string")
        return v


class SourceReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: SourceStatus

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        if not v:
            raise ValueError("name must be a non-empty string")
        return v


class AsOfWithPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: AsOfRequest
    policy: Optional[SourcePolicy] = None


def _validation_details(exc: RequestValidationError) -> list[dict]:
    details = []
    for item in exc.errors():
        if isinstance(item, dict):
            details.append({k: v for k, v in item.items() if k != "asof"})
    return details


def create_app(
    calendars: Optional[Mapping[str, MarketCalendar]] = None,
    providers: Optional[Iterable[SourceProvider]] = None,
) -> FastAPI:
    """Build a FastAPI app that exposes asof123 over HTTP.

    `calendars` defaults to `{"XNYS": XNYSCalendar()}` so a freshly
    constructed app is immediately usable for US equities. `providers`
    defaults to an empty list. Both are stored on `app.state` and are
    not refreshed for the lifetime of the app; this is by design (no
    mutable registry, no background work).
    """
    app = FastAPI(title="asof123 reference API")

    app.state.calendars = (
        dict(calendars) if calendars is not None else {"XNYS": XNYSCalendar()}
    )
    app.state.providers = list(providers) if providers is not None else []

    @app.exception_handler(ResolverError)
    async def _resolver_error_handler(
        request: Request, exc: ResolverError
    ) -> JSONResponse:
        payload = ErrorResponse(
            error="RESOLVER_ERROR",
            reason_code=exc.reason_code,
            explanation=exc.explanation,
            message=str(exc),
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=payload.model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        payload = ErrorResponse(
            error="VALIDATION_ERROR",
            reason_code=ErrorReasonCode.VALIDATION_ERROR,
            explanation="Request validation failed",
            message="Request validation failed",
            details=jsonable_encoder(_validation_details(exc)),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=payload.model_dump(mode="json"),
        )

    @app.get("/asof/current", response_model=AsOf)
    def get_current(
        perspective: Perspective = Perspective.LIVE,
        market: str = "XNYS",
        market_timezone: str = "America/New_York",
    ) -> AsOf:
        req = AsOfRequest(
            perspective=perspective,
            market=market,
            market_timezone=market_timezone,
        )
        return resolve(req, app.state.calendars, app.state.providers)

    @app.post("/asof/resolve", response_model=AsOf)
    def post_resolve(
        body: AsOfRequest | AsOfWithPolicyRequest,
    ) -> AsOf:
        if isinstance(body, AsOfWithPolicyRequest):
            return resolve(
                body.request,
                app.state.calendars,
                app.state.providers,
                policy=body.policy,
            )
        return resolve(body, app.state.calendars, app.state.providers)

    @app.get("/sources/status")
    def get_sources_status():
        providers = list(app.state.providers)

        seen: set[str] = set()
        for p in providers:
            if p.name in seen:
                return JSONResponse(
                    status_code=status.HTTP_409_CONFLICT,
                    content=ErrorResponse(
                        error="DUPLICATE_PROVIDER_NAME",
                        reason_code=ErrorReasonCode.DUPLICATE_PROVIDER_NAME,
                        explanation=(
                            f"Duplicate provider name {p.name!r}; each "
                            "SourceProvider must have a unique name"
                        ),
                        message=(
                            f"{ErrorReasonCode.DUPLICATE_PROVIDER_NAME.value}: "
                            f"Duplicate provider name {p.name!r}; each "
                            "SourceProvider must have a unique name"
                        ),
                    ).model_dump(mode="json"),
                )
            seen.add(p.name)

        now = datetime.now(timezone.utc)
        result: dict[str, SourceStatus] = {}
        for p in providers:
            try:
                result[p.name] = p.report(now)
            except ProviderReportError as exc:
                message = (
                    str(exc) or "ProviderReportError raised with no message"
                )
                result[p.name] = SourceStatus(
                    provider=p.name,
                    freshness=SourceFreshness.FAILED,
                    reason_code=ErrorReasonCode.PROVIDER_REPORT_FAILED.value,
                    explanation=message,
                )
        return result

    @app.post("/sources/report")
    def post_sources_report(body: SourceReportRequest) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            content=ErrorResponse(
                error="NOT_IMPLEMENTED",
                reason_code=ErrorReasonCode.NOT_IMPLEMENTED,
                explanation=(
                    "The reference app is read-only. Source reporting "
                    "requires a registry or persistence layer outside "
                    "this pass."
                ),
                message=(
                    "The reference app is read-only. Source reporting "
                    "requires a registry or persistence layer outside "
                    "this pass."
                ),
            ).model_dump(mode="json"),
        )

    @app.post("/asof/snapshot", response_model=AsOfSnapshot)
    def post_snapshot(req: SnapshotRequest) -> AsOfSnapshot:
        return make_snapshot(req.asof, req.snapshot_id)

    return app
