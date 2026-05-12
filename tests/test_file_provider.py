"""Tests for `FileProvider`.

All filesystem access goes through `tmp_path`. No network, no real-world
filesystem paths, no external services.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from asof123.enums import SourceFreshness
from asof123.models import SourceStatus
from asof123.providers import FileProvider, ProviderReportError, SourceProvider


UTC_NOW = datetime(2026, 5, 12, 13, 45, 0, tzinfo=timezone.utc)


def _write_json(tmp_path: Path, name: str, payload: dict) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(payload))
    return p


def _write_text(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


def test_happy_path_reads_valid_json_file(tmp_path):
    p = _write_json(
        tmp_path,
        "status.json",
        {
            "provider": "quotes_feed",
            "freshness": "FRESH",
            "last_update_utc": "2026-05-12T13:44:58Z",
        },
    )
    provider = FileProvider("quotes_feed", p)
    status = provider.report(UTC_NOW)
    assert isinstance(status, SourceStatus)
    assert status.provider == "quotes_feed"
    assert status.freshness is SourceFreshness.FRESH
    assert status.last_update_utc == datetime(
        2026, 5, 12, 13, 44, 58, tzinfo=timezone.utc
    )


def test_provider_field_auto_filled_when_absent_from_file(tmp_path):
    p = _write_json(
        tmp_path,
        "status.json",
        {"freshness": "STALE", "last_update_utc": "2026-05-12T13:00:00Z"},
    )
    provider = FileProvider("quotes_feed", p)
    status = provider.report(UTC_NOW)
    assert status.provider == "quotes_feed"
    assert status.freshness is SourceFreshness.STALE


def test_missing_file_raises_provider_report_error(tmp_path):
    provider = FileProvider("quotes_feed", tmp_path / "does_not_exist.json")
    with pytest.raises(ProviderReportError, match="not found"):
        provider.report(UTC_NOW)


def test_empty_file_raises_provider_report_error(tmp_path):
    p = _write_text(tmp_path, "empty.json", "")
    provider = FileProvider("quotes_feed", p)
    with pytest.raises(ProviderReportError, match="empty"):
        provider.report(UTC_NOW)


def test_whitespace_only_file_raises_provider_report_error(tmp_path):
    p = _write_text(tmp_path, "ws.json", "   \n\t  \n")
    provider = FileProvider("quotes_feed", p)
    with pytest.raises(ProviderReportError, match="empty"):
        provider.report(UTC_NOW)


def test_invalid_json_raises_provider_report_error(tmp_path):
    p = _write_text(tmp_path, "bad.json", "{ not valid json")
    provider = FileProvider("quotes_feed", p)
    with pytest.raises(ProviderReportError, match="invalid JSON"):
        provider.report(UTC_NOW)


def test_non_object_json_raises_provider_report_error(tmp_path):
    p = _write_text(tmp_path, "arr.json", "[1, 2, 3]")
    provider = FileProvider("quotes_feed", p)
    with pytest.raises(ProviderReportError, match="must be an object"):
        provider.report(UTC_NOW)


def test_invalid_freshness_raises_provider_report_error(tmp_path):
    p = _write_json(
        tmp_path, "status.json", {"freshness": "NOT_A_REAL_FRESHNESS"}
    )
    provider = FileProvider("quotes_feed", p)
    with pytest.raises(ProviderReportError, match="invalid SourceStatus"):
        provider.report(UTC_NOW)


def test_invalid_utc_datetime_raises_provider_report_error(tmp_path):
    p = _write_json(
        tmp_path,
        "status.json",
        {"freshness": "FRESH", "last_update_utc": "2026-05-12T13:44:58"},
    )
    provider = FileProvider("quotes_feed", p)
    with pytest.raises(ProviderReportError, match="invalid SourceStatus"):
        provider.report(UTC_NOW)


def test_mismatched_provider_name_raises_provider_report_error(tmp_path):
    p = _write_json(
        tmp_path,
        "status.json",
        {"provider": "other_feed", "freshness": "FRESH"},
    )
    provider = FileProvider("quotes_feed", p)
    with pytest.raises(ProviderReportError, match="does not match"):
        provider.report(UTC_NOW)


def test_report_returns_a_source_status_instance(tmp_path):
    p = _write_json(tmp_path, "status.json", {"freshness": "PRIOR_CLOSE"})
    provider = FileProvider("quotes_feed", p)
    assert isinstance(provider.report(UTC_NOW), SourceStatus)


def test_file_provider_satisfies_source_provider_protocol(tmp_path):
    p = _write_json(tmp_path, "status.json", {"freshness": "FRESH"})
    provider = FileProvider("quotes_feed", p)
    assert isinstance(provider, SourceProvider)


def test_empty_name_rejected(tmp_path):
    with pytest.raises(ValueError, match="non-empty"):
        FileProvider("", tmp_path / "x.json")


def test_file_is_re_read_on_each_report(tmp_path):
    p = _write_json(tmp_path, "status.json", {"freshness": "FRESH"})
    provider = FileProvider("quotes_feed", p)
    first = provider.report(UTC_NOW)
    assert first.freshness is SourceFreshness.FRESH
    # Mutate the file on disk between calls; the provider must see the new
    # contents, since there is no caching.
    _write_json(tmp_path, "status.json", {"freshness": "STALE"})
    second = provider.report(UTC_NOW)
    assert second.freshness is SourceFreshness.STALE
