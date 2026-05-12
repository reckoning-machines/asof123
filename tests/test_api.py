"""Tests for the FastAPI reference surface.

All tests run in-process via `fastapi.testclient.TestClient`. No real
network, no external services, no disk reads other than `tmp_path` (not
used in this file).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from asof123.api import create_app
from asof123.calendars import XNYSCalendar
from asof123.enums import (
    CanonicalState,
    ExecutionState,
    MarketPhase,
    Perspective,
    PriceBasis,
    PublicationState,
    SourceFreshness,
)
from asof123.models import SourceStatus, TemporalContext
from asof123.providers import ProviderReportError, StaticProvider


UTC_NOW = datetime(2026, 5, 12, 13, 45, 0, tzinfo=timezone.utc)
PRE_OPEN_UTC = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)
REPLAY_UTC = datetime(2026, 2, 10, 21, 0, 0, tzinfo=timezone.utc)


class _FailingProvider:
    def __init__(self, name: str, message: str = "upstream unreachable") -> None:
        self.name = name
        self._message = message

    def report(self, now_utc):
        raise ProviderReportError(self._message)


def _sample_context() -> TemporalContext:
    return TemporalContext(
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


def test_create_app_default_calendar_registers_xnys():
    app = create_app()
    assert "XNYS" in app.state.calendars
    assert isinstance(app.state.calendars["XNYS"], XNYSCalendar)
    assert app.state.providers == []


def test_get_asof_current_defaults_to_live_xnys_new_york():
    app = create_app()
    client = TestClient(app)
    response = client.get("/asof/current")
    assert response.status_code == 200
    body = response.json()
    assert body["perspective"] == "LIVE"
    assert body["market"] == "XNYS"
    assert body["market_timezone"] == "America/New_York"


def test_get_asof_current_with_pre_trade_intent_returns_valid_response():
    app = create_app()
    client = TestClient(app)
    response = client.get(
        "/asof/current",
        params={"perspective": "PRE_TRADE_INTENT"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["perspective"] == "PRE_TRADE_INTENT"
    # market_phase is whatever it is right now; we just confirm it parses.
    assert body["market_phase"] in {
        "PRE_OPEN", "MARKET_OPEN", "POST_CLOSE", "WEEKEND", "HOLIDAY", "CLOSED"
    }


def test_post_asof_resolve_with_replay_pinned_utc_returns_valid_response():
    app = create_app()
    client = TestClient(app)
    payload = {
        "perspective": "REPLAY",
        "market": "XNYS",
        "market_timezone": "America/New_York",
        "as_of_utc": "2026-02-10T21:00:00Z",
        "knowledge_cutoff_utc": "2026-02-10T21:00:00Z",
    }
    response = client.post("/asof/resolve", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["perspective"] == "REPLAY"
    assert body["resolved_at_utc"].startswith("2026-02-10T21:00:00")
    assert body["knowledge_cutoff_utc"].startswith("2026-02-10T21:00:00")


def test_post_asof_resolve_with_invalid_live_as_of_utc_returns_422():
    app = create_app()
    client = TestClient(app)
    payload = {
        "perspective": "LIVE",
        "market": "XNYS",
        "market_timezone": "America/New_York",
        "as_of_utc": "2026-02-10T21:00:00Z",
    }
    response = client.post("/asof/resolve", json=payload)
    assert response.status_code == 422


def test_missing_calendar_returns_400_with_resolver_error():
    app = create_app(calendars={})
    client = TestClient(app)
    payload = {
        "perspective": "LIVE",
        "market": "XNYS",
        "market_timezone": "America/New_York",
    }
    response = client.post("/asof/resolve", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "RESOLVER_ERROR"
    assert "XNYS" in body["message"]


def test_get_sources_status_returns_static_provider_status():
    static = StaticProvider(
        "quotes_feed",
        SourceStatus(
            provider="quotes_feed",
            freshness=SourceFreshness.FRESH,
            last_update_utc=UTC_NOW,
        ),
    )
    app = create_app(providers=[static])
    client = TestClient(app)
    response = client.get("/sources/status")
    assert response.status_code == 200
    body = response.json()
    assert "quotes_feed" in body
    assert body["quotes_feed"]["freshness"] == "FRESH"
    assert body["quotes_feed"]["provider"] == "quotes_feed"


def test_get_sources_status_converts_provider_report_error_to_failed():
    failing = _FailingProvider("vendor_b", "connection refused")
    app = create_app(providers=[failing])
    client = TestClient(app)
    response = client.get("/sources/status")
    assert response.status_code == 200
    body = response.json()
    assert body["vendor_b"]["freshness"] == "FAILED"
    assert body["vendor_b"]["reason_code"] == "PROVIDER_REPORT_FAILED"
    assert "connection refused" in body["vendor_b"]["explanation"]


def test_get_sources_status_with_duplicate_provider_names_returns_409():
    p1 = StaticProvider(
        "vendor_a",
        SourceStatus(provider="vendor_a", freshness=SourceFreshness.FRESH),
    )
    p2 = StaticProvider(
        "vendor_a",
        SourceStatus(provider="vendor_a", freshness=SourceFreshness.STALE),
    )
    app = create_app(providers=[p1, p2])
    client = TestClient(app)
    response = client.get("/sources/status")
    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "DUPLICATE_PROVIDER_NAME"
    assert "vendor_a" in body["message"]


def test_post_sources_report_returns_501_with_explanation():
    app = create_app()
    client = TestClient(app)
    payload = {
        "name": "quotes_feed",
        "status": {
            "provider": "quotes_feed",
            "freshness": "FRESH",
            "last_update_utc": "2026-05-12T13:44:58Z",
        },
    }
    response = client.post("/sources/report", json=payload)
    assert response.status_code == 501
    body = response.json()
    assert body["error"] == "NOT_IMPLEMENTED"
    assert "read-only" in body["message"]


def test_post_asof_snapshot_returns_as_of_snapshot_with_content_hash():
    app = create_app()
    client = TestClient(app)
    ctx = _sample_context()
    payload = {
        "snapshot_id": "snap-1",
        "context": ctx.model_dump(mode="json"),
    }
    response = client.post("/asof/snapshot", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["snapshot_id"] == "snap-1"
    assert isinstance(body["content_hash"], str)
    assert len(body["content_hash"]) == 64
    int(body["content_hash"], 16)  # valid hex
    # captured_at_utc is timezone-aware UTC in the serialized form.
    assert body["captured_at_utc"].endswith("Z") or "+00:00" in body[
        "captured_at_utc"
    ]


def test_post_asof_snapshot_rejects_empty_snapshot_id_via_422():
    app = create_app()
    client = TestClient(app)
    ctx = _sample_context()
    payload = {"snapshot_id": "", "context": ctx.model_dump(mode="json")}
    response = client.post("/asof/snapshot", json=payload)
    assert response.status_code == 422
