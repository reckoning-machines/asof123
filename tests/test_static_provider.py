"""Tests for `StaticProvider`."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from asof123.enums import SourceFreshness
from asof123.models import SourceStatus
from asof123.providers import SourceProvider, StaticProvider


UTC_NOW = datetime(2026, 5, 12, 13, 45, 0, tzinfo=timezone.utc)


def test_happy_path_report_returns_stored_status():
    status = SourceStatus(
        provider="vendor_a",
        freshness=SourceFreshness.FRESH,
        last_update_utc=UTC_NOW,
    )
    provider = StaticProvider("vendor_a", status)
    result = provider.report(UTC_NOW)
    assert isinstance(result, SourceStatus)
    assert result.provider == "vendor_a"
    assert result.freshness is SourceFreshness.FRESH
    assert result.last_update_utc == UTC_NOW


def test_constructor_auto_fills_provider_name_if_absent():
    status = SourceStatus(freshness=SourceFreshness.FRESH, last_update_utc=UTC_NOW)
    provider = StaticProvider("vendor_b", status)
    result = provider.report(UTC_NOW)
    assert result.provider == "vendor_b"


def test_mismatched_provider_name_rejected():
    status = SourceStatus(
        provider="vendor_a",
        freshness=SourceFreshness.FRESH,
        last_update_utc=UTC_NOW,
    )
    with pytest.raises(ValueError, match="vendor_a"):
        StaticProvider("vendor_b", status)


def test_empty_name_rejected():
    status = SourceStatus(freshness=SourceFreshness.FRESH)
    with pytest.raises(ValueError, match="non-empty"):
        StaticProvider("", status)


def test_returned_source_status_is_a_source_status():
    status = SourceStatus(
        provider="vendor_a",
        freshness=SourceFreshness.PRIOR_CLOSE,
        last_update_utc=UTC_NOW,
    )
    provider = StaticProvider("vendor_a", status)
    result = provider.report(UTC_NOW)
    assert isinstance(result, SourceStatus)
    assert result.freshness is SourceFreshness.PRIOR_CLOSE


def test_static_provider_satisfies_source_provider_protocol():
    provider = StaticProvider(
        "vendor_a",
        SourceStatus(provider="vendor_a", freshness=SourceFreshness.FRESH),
    )
    assert isinstance(provider, SourceProvider)


def test_report_is_independent_of_now_utc():
    status = SourceStatus(provider="vendor_a", freshness=SourceFreshness.FRESH)
    provider = StaticProvider("vendor_a", status)
    other_time = datetime(2030, 1, 1, tzinfo=timezone.utc)
    assert provider.report(UTC_NOW) is provider.report(other_time)
