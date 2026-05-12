"""Tests for the SourceProvider protocol and ProviderReportError.

These tests assert protocol shape only. They do not exercise any real
provider implementation, and they intentionally do not depend on
network or filesystem state.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from asof123.enums import SourceFreshness
from asof123.models import SourceStatus
from asof123.providers import ProviderReportError, SourceProvider


UTC_NOW = datetime(2026, 5, 12, 13, 45, 0, tzinfo=timezone.utc)


class _FakeProvider:
    """Tiny inline provider used only to verify the protocol shape.

    Lives in the test module on purpose. The package itself ships no
    provider implementations per PRODUCT_CONTRACT.md sections 12 and 15.
    """

    name: str

    def __init__(self, name: str) -> None:
        if not name:
            raise ValueError("provider name must be non-empty")
        self.name = name

    def report(self, now_utc: datetime) -> SourceStatus:
        return SourceStatus(
            provider=self.name,
            freshness=SourceFreshness.FRESH,
            last_update_utc=now_utc,
        )


def test_fake_provider_is_instance_of_protocol():
    provider = _FakeProvider("vendor_a_equities")
    assert isinstance(provider, SourceProvider)


def test_fake_provider_report_returns_source_status():
    provider = _FakeProvider("vendor_a_equities")
    status = provider.report(UTC_NOW)
    assert isinstance(status, SourceStatus)
    assert status.provider == "vendor_a_equities"
    assert status.freshness is SourceFreshness.FRESH
    assert status.last_update_utc == UTC_NOW


def test_provider_report_error_is_exception_subclass():
    assert issubclass(ProviderReportError, Exception)


def test_provider_report_error_is_raisable_and_catchable():
    with pytest.raises(ProviderReportError, match="upstream unreachable"):
        raise ProviderReportError("upstream unreachable")


def test_fake_provider_name_must_be_non_empty():
    with pytest.raises(ValueError, match="non-empty"):
        _FakeProvider("")


def test_dict_is_not_a_source_provider():
    assert not isinstance({}, SourceProvider)


def test_object_without_report_is_not_a_source_provider():
    class _NameOnly:
        name = "incomplete"

    assert not isinstance(_NameOnly(), SourceProvider)
