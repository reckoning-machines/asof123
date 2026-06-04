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
from asof123.models import SourceStatus, AsOf
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


def _sample_asof() -> AsOf:
    return AsOf(
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
    assert body["market_datetime"] == "2026-02-10T16:00:00-05:00"
    assert body["market_date"] == "2026-02-10"


def test_post_asof_resolve_market_datetime_crosses_utc_date_boundary():
    app = create_app()
    client = TestClient(app)
    payload = {
        "perspective": "PRE_TRADE_INTENT",
        "market": "XNYS",
        "market_timezone": "America/New_York",
        "as_of_utc": "2026-05-13T04:00:00Z",
        "knowledge_cutoff_utc": "2026-05-13T04:00:00Z",
    }
    response = client.post("/asof/resolve", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["resolved_at_utc"].startswith("2026-05-13T04:00:00")
    assert body["market_datetime"] == "2026-05-13T00:00:00-04:00"
    assert body["market_date"] == "2026-05-13"
    assert body["business_date"] == "2026-05-13"


def test_post_asof_resolve_market_datetime_respects_dst_offsets():
    app = create_app()
    client = TestClient(app)

    spring = client.post(
        "/asof/resolve",
        json={
            "perspective": "PRE_TRADE_INTENT",
            "market": "XNYS",
            "market_timezone": "America/New_York",
            "as_of_utc": "2026-03-09T14:00:00Z",
            "knowledge_cutoff_utc": "2026-03-09T14:00:00Z",
        },
    )
    assert spring.status_code == 200, spring.text
    assert spring.json()["market_datetime"] == "2026-03-09T10:00:00-04:00"

    fall = client.post(
        "/asof/resolve",
        json={
            "perspective": "PRE_TRADE_INTENT",
            "market": "XNYS",
            "market_timezone": "America/New_York",
            "as_of_utc": "2026-11-02T15:00:00Z",
            "knowledge_cutoff_utc": "2026-11-02T15:00:00Z",
        },
    )
    assert fall.status_code == 200, fall.text
    assert fall.json()["market_datetime"] == "2026-11-02T10:00:00-05:00"


def test_post_asof_resolve_rejects_est_at_api_boundary():
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/asof/resolve",
        json={
            "perspective": "LIVE",
            "market": "XNYS",
            "market_timezone": "EST",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "VALIDATION_ERROR"
    assert body["reason_code"] == "VALIDATION_ERROR"
    assert "EST" in response.text


def test_post_asof_resolve_policy_wrapper_without_policy_is_backward_compatible():
    app = create_app()
    client = TestClient(app)
    payload = {
        "request": {
            "perspective": "REPLAY",
            "market": "XNYS",
            "market_timezone": "America/New_York",
            "as_of_utc": "2026-02-10T21:00:00Z",
            "knowledge_cutoff_utc": "2026-02-10T21:00:00Z",
        }
    }

    response = client.post("/asof/resolve", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["perspective"] == "REPLAY"
    assert body["sources"] == {}


def test_post_asof_resolve_policy_marks_missing_required_source():
    app = create_app()
    client = TestClient(app)
    payload = {
        "request": {
            "perspective": "PRE_TRADE_INTENT",
            "market": "XNYS",
            "market_timezone": "America/New_York",
            "as_of_utc": "2026-05-12T12:00:00Z",
            "knowledge_cutoff_utc": "2026-05-12T12:00:00Z",
        },
        "policy": {
            "required_sources": ["quotes"],
        },
    }

    response = client.post("/asof/resolve", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sources"]["quotes"]["freshness"] == "MISSING"
    assert body["sources"]["quotes"]["reason_code"] == "REQUIRED_SOURCE_MISSING"


def test_post_asof_resolve_policy_deduplicates_required_sources():
    app = create_app()
    client = TestClient(app)
    payload = {
        "request": {
            "perspective": "PRE_TRADE_INTENT",
            "market": "XNYS",
            "market_timezone": "America/New_York",
            "as_of_utc": "2026-05-12T12:00:00Z",
            "knowledge_cutoff_utc": "2026-05-12T12:00:00Z",
        },
        "policy": {
            "required_sources": ["quotes", "quotes"],
        },
    }

    response = client.post("/asof/resolve", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert list(body["sources"]) == ["quotes"]
    assert body["sources"]["quotes"]["freshness"] == "MISSING"
    assert body["sources"]["quotes"]["reason_code"] == "REQUIRED_SOURCE_MISSING"


def test_post_asof_resolve_policy_marks_stale_source():
    static = StaticProvider(
        "quotes",
        SourceStatus(
            provider="quotes",
            freshness=SourceFreshness.FRESH,
            last_update_utc=datetime(2026, 5, 12, 11, 59, 0, tzinfo=timezone.utc),
        ),
    )
    app = create_app(providers=[static])
    client = TestClient(app)
    payload = {
        "request": {
            "perspective": "PRE_TRADE_INTENT",
            "market": "XNYS",
            "market_timezone": "America/New_York",
            "as_of_utc": "2026-05-12T12:00:00Z",
            "knowledge_cutoff_utc": "2026-05-12T12:00:00Z",
        },
        "policy": {
            "max_age_seconds": 5,
        },
    }

    response = client.post("/asof/resolve", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sources"]["quotes"]["freshness"] == "STALE"
    assert body["sources"]["quotes"]["reason_code"] == "SOURCE_STALE"


def test_post_asof_resolve_policy_per_source_max_age_override():
    static = StaticProvider(
        "quotes",
        SourceStatus(
            provider="quotes",
            freshness=SourceFreshness.FRESH,
            last_update_utc=datetime(2026, 5, 12, 11, 59, 0, tzinfo=timezone.utc),
        ),
    )
    app = create_app(providers=[static])
    client = TestClient(app)
    payload = {
        "request": {
            "perspective": "PRE_TRADE_INTENT",
            "market": "XNYS",
            "market_timezone": "America/New_York",
            "as_of_utc": "2026-05-12T12:00:00Z",
            "knowledge_cutoff_utc": "2026-05-12T12:00:00Z",
        },
        "policy": {
            "max_age_seconds": 5,
            "max_age_seconds_by_source": {
                "quotes": 120,
            },
        },
    }

    response = client.post("/asof/resolve", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sources"]["quotes"]["freshness"] == "FRESH"
    assert body["sources"]["quotes"]["reason_code"] is None


def test_post_asof_resolve_invalid_policy_returns_422():
    app = create_app()
    client = TestClient(app)
    payload = {
        "request": {
            "perspective": "PRE_TRADE_INTENT",
            "market": "XNYS",
            "market_timezone": "America/New_York",
            "as_of_utc": "2026-05-12T12:00:00Z",
            "knowledge_cutoff_utc": "2026-05-12T12:00:00Z",
        },
        "policy": {
            "max_age_seconds": 0,
        },
    }

    response = client.post("/asof/resolve", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "VALIDATION_ERROR"
    assert body["reason_code"] == "VALIDATION_ERROR"
    assert "max_age_seconds" in response.text


def test_post_asof_resolve_malformed_wrapper_returns_422():
    app = create_app()
    client = TestClient(app)
    payload = {
        "perspective": "LIVE",
        "request": {
            "perspective": "LIVE",
            "market": "XNYS",
            "market_timezone": "America/New_York",
        },
    }

    response = client.post("/asof/resolve", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "VALIDATION_ERROR"
    assert body["reason_code"] == "VALIDATION_ERROR"
    assert "Request validation failed" in body["explanation"]


def test_post_asof_resolve_wrapper_extra_field_returns_422():
    app = create_app()
    client = TestClient(app)
    payload = {
        "request": {
            "perspective": "LIVE",
            "market": "XNYS",
            "market_timezone": "America/New_York",
        },
        "extra": "not allowed",
    }

    response = client.post("/asof/resolve", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "VALIDATION_ERROR"
    assert body["reason_code"] == "VALIDATION_ERROR"
    assert "extra" in response.text


def test_post_asof_resolve_policy_extra_field_returns_422():
    app = create_app()
    client = TestClient(app)
    payload = {
        "request": {
            "perspective": "LIVE",
            "market": "XNYS",
            "market_timezone": "America/New_York",
        },
        "policy": {
            "required_sources": ["quotes"],
            "unexpected": "not allowed",
        },
    }

    response = client.post("/asof/resolve", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "VALIDATION_ERROR"
    assert body["reason_code"] == "VALIDATION_ERROR"
    assert "unexpected" in response.text


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
    body = response.json()
    assert body["error"] == "VALIDATION_ERROR"
    assert body["reason_code"] == "VALIDATION_ERROR"
    assert body["explanation"] == "Request validation failed"
    assert "details" in body


def test_post_asof_resolve_canonical_fails_closed_without_publication_metadata():
    app = create_app()
    client = TestClient(app)
    payload = {
        "perspective": "CANONICAL",
        "market": "XNYS",
        "market_timezone": "America/New_York",
    }
    response = client.post("/asof/resolve", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "RESOLVER_ERROR"
    assert body["reason_code"] == "PUBLICATION_METADATA_MISSING"
    assert "publication" in body["explanation"]
    assert "PUBLICATION_METADATA_MISSING" in body["message"]


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
    assert body["reason_code"] == "UNKNOWN_MARKET"
    assert "No calendar registered" in body["explanation"]
    assert "UNKNOWN_MARKET" in body["message"]
    assert "XNYS" in body["message"]


def test_get_sources_status_returns_static_provider_status():
    static = StaticProvider(
        "quotes_feed",
        SourceStatus(
            provider="quotes_feed",
            freshness=SourceFreshness.FRESH,
            timestamp_utc=UTC_NOW,
            timestamp_name="vendor_updated_at",
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
    assert body["quotes_feed"]["timestamp_utc"].startswith("2026-05-12T13:45:00")
    assert body["quotes_feed"]["timestamp_name"] == "vendor_updated_at"


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
    assert body["reason_code"] == "DUPLICATE_PROVIDER_NAME"
    assert "vendor_a" in body["explanation"]
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
    assert body["reason_code"] == "NOT_IMPLEMENTED"
    assert "read-only" in body["explanation"]
    assert "read-only" in body["message"]


def test_post_asof_snapshot_returns_as_of_snapshot_with_content_hash():
    app = create_app()
    client = TestClient(app)
    asof = _sample_asof()
    payload = {
        "snapshot_id": "snap-1",
        "asof": asof.model_dump(mode="json"),
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
    asof = _sample_asof()
    payload = {"snapshot_id": "", "asof": asof.model_dump(mode="json")}
    response = client.post("/asof/snapshot", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "VALIDATION_ERROR"
    assert body["reason_code"] == "VALIDATION_ERROR"
