"""Tests for the asof123 CLI.

All tests invoke `main(argv=...)` directly. No subprocess, no shell, no
network. `serve` is exercised via `monkeypatch.setitem(sys.modules,
"uvicorn", ...)` so the test never opens a real socket.
"""

from __future__ import annotations

import json
import sys
import types

import pytest

from asof123.cli import main


def test_resolve_happy_path_prints_xnys_context(capsys):
    exit_code = main(["resolve"])
    assert exit_code == 0
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert body["market"] == "XNYS"
    assert body["market_timezone"] == "America/New_York"
    assert body["perspective"] == "LIVE"
    assert body["resolved_at_utc"].endswith("Z") or "+00:00" in body[
        "resolved_at_utc"
    ]


def test_resolve_pre_trade_intent_with_pinned_utc_yields_pre_open(capsys):
    exit_code = main([
        "resolve",
        "--perspective", "PRE_TRADE_INTENT",
        "--as-of-utc", "2026-05-12T12:00:00Z",
        "--knowledge-cutoff-utc", "2026-05-12T12:00:00Z",
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert body["perspective"] == "PRE_TRADE_INTENT"
    assert body["market_phase"] == "PRE_OPEN"
    assert body["price_basis"] == "PRIOR_CLOSE"
    assert body["market_datetime"] == "2026-05-12T08:00:00-04:00"
    assert body["market_date"] == "2026-05-12"


def test_resolve_market_datetime_crosses_utc_date_boundary_in_json(capsys):
    exit_code = main([
        "resolve",
        "--perspective", "PRE_TRADE_INTENT",
        "--as-of-utc", "2026-05-13T04:00:00Z",
        "--knowledge-cutoff-utc", "2026-05-13T04:00:00Z",
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert body["resolved_at_utc"].startswith("2026-05-13T04:00:00")
    assert body["market_datetime"] == "2026-05-13T00:00:00-04:00"
    assert body["market_date"] == "2026-05-13"
    assert body["business_date"] == "2026-05-13"


def test_resolve_with_source_file_includes_source_status(tmp_path, capsys):
    f = tmp_path / "quotes.json"
    f.write_text(
        json.dumps(
            {
                "provider": "quotes_feed",
                "freshness": "FRESH",
                "last_update_utc": "2026-05-12T12:00:00Z",
            }
        )
    )
    exit_code = main(
        [
            "resolve",
            "--perspective", "PRE_TRADE_INTENT",
            "--as-of-utc", "2026-05-12T12:00:00Z",
            "--knowledge-cutoff-utc", "2026-05-12T12:00:00Z",
            "--source-file", f"quotes_feed={f}",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert "quotes_feed" in body["sources"]
    assert body["sources"]["quotes_feed"]["freshness"] == "FRESH"
    assert body["sources"]["quotes_feed"]["provider"] == "quotes_feed"


def test_resolve_required_source_adds_missing_status(capsys):
    exit_code = main(
        [
            "resolve",
            "--perspective", "PRE_TRADE_INTENT",
            "--as-of-utc", "2026-05-12T12:00:00Z",
            "--knowledge-cutoff-utc", "2026-05-12T12:00:00Z",
            "--required-source", "quotes",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert body["sources"]["quotes"]["freshness"] == "MISSING"
    assert body["sources"]["quotes"]["reason_code"] == "REQUIRED_SOURCE_MISSING"


def test_resolve_duplicate_required_sources_are_deduplicated(capsys):
    exit_code = main(
        [
            "resolve",
            "--perspective", "PRE_TRADE_INTENT",
            "--as-of-utc", "2026-05-12T12:00:00Z",
            "--knowledge-cutoff-utc", "2026-05-12T12:00:00Z",
            "--required-source", "quotes",
            "--required-source", "quotes",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert list(body["sources"]) == ["quotes"]
    assert body["sources"]["quotes"]["freshness"] == "MISSING"
    assert body["sources"]["quotes"]["reason_code"] == "REQUIRED_SOURCE_MISSING"


def test_resolve_max_age_marks_stale_source(tmp_path, capsys):
    f = tmp_path / "quotes.json"
    f.write_text(
        json.dumps(
            {
                "provider": "quotes",
                "freshness": "FRESH",
                "last_update_utc": "2026-05-12T11:59:00Z",
            }
        )
    )

    exit_code = main(
        [
            "resolve",
            "--perspective", "PRE_TRADE_INTENT",
            "--as-of-utc", "2026-05-12T12:00:00Z",
            "--knowledge-cutoff-utc", "2026-05-12T12:00:00Z",
            "--source-file", f"quotes={f}",
            "--max-age-seconds", "5",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert body["sources"]["quotes"]["freshness"] == "STALE"
    assert body["sources"]["quotes"]["reason_code"] == "SOURCE_STALE"


def test_resolve_max_age_source_overrides_default(tmp_path, capsys):
    f = tmp_path / "quotes.json"
    f.write_text(
        json.dumps(
            {
                "provider": "quotes",
                "freshness": "FRESH",
                "last_update_utc": "2026-05-12T11:59:00Z",
            }
        )
    )

    exit_code = main(
        [
            "resolve",
            "--perspective", "PRE_TRADE_INTENT",
            "--as-of-utc", "2026-05-12T12:00:00Z",
            "--knowledge-cutoff-utc", "2026-05-12T12:00:00Z",
            "--source-file", f"quotes={f}",
            "--max-age-seconds", "5",
            "--max-age-source", "quotes=120",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert body["sources"]["quotes"]["freshness"] == "FRESH"
    assert body["sources"]["quotes"]["reason_code"] is None


def test_resolve_duplicate_max_age_source_is_rejected(capsys):
    exit_code = main(
        [
            "resolve",
            "--perspective", "PRE_TRADE_INTENT",
            "--as-of-utc", "2026-05-12T12:00:00Z",
            "--knowledge-cutoff-utc", "2026-05-12T12:00:00Z",
            "--max-age-source", "quotes=5",
            "--max-age-source", "quotes=10",
        ]
    )

    assert exit_code == 2
    captured = capsys.readouterr()
    body = json.loads(captured.err)
    assert body["error"] == "VALIDATION_ERROR"
    assert body["reason_code"] == "INVALID_PROVIDER"
    assert "Duplicate --max-age-source" in body["explanation"]


def test_resolve_invalid_max_age_argparse_error(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["resolve", "--max-age-seconds", "0"])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "positive integer" in captured.err


@pytest.mark.parametrize(
    "value",
    [
        "quotes",
        "=5",
        "quotes=",
        "quotes=five",
        "quotes=0",
        "quotes=-1",
    ],
)
def test_resolve_invalid_max_age_source_argparse_error(value, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["resolve", "--max-age-source", value])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--max-age-source" in captured.err or "positive integer" in captured.err


def test_resolve_invalid_datetime_argparse_error(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["resolve", "--as-of-utc", "not-a-datetime"])
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "ISO 8601" in captured.err or "invalid" in captured.err.lower()


def test_resolve_naive_datetime_rejected_at_argparse(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["resolve", "--as-of-utc", "2026-05-12T12:00:00"])
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "timezone-aware" in captured.err or "naive" in captured.err.lower()


def test_resolve_non_utc_datetime_rejected_at_argparse(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["resolve", "--as-of-utc", "2026-05-12T12:00:00+02:00"])
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "UTC" in captured.err


def test_resolve_live_with_as_of_utc_returns_nonzero_validation_error(capsys):
    # LIVE forbids as_of_utc; AsOfRequest's validator rejects it.
    exit_code = main(
        [
            "resolve",
            "--perspective", "LIVE",
            "--as-of-utc", "2026-05-12T12:00:00Z",
        ]
    )
    assert exit_code == 2
    captured = capsys.readouterr()
    body = json.loads(captured.err)
    assert body["error"] == "VALIDATION_ERROR"
    assert body["reason_code"] == "INVALID_REQUEST"
    assert body["explanation"] == "Invalid resolve request"
    assert "LIVE" in captured.err


def test_resolve_canonical_fails_closed_without_publication_metadata(capsys):
    exit_code = main(["resolve", "--perspective", "CANONICAL"])
    assert exit_code == 2
    captured = capsys.readouterr()
    body = json.loads(captured.err)
    assert body["error"] == "RESOLVER_ERROR"
    assert body["reason_code"] == "PUBLICATION_METADATA_MISSING"


def test_resolve_unknown_market_fails_closed_with_reason_code(capsys):
    exit_code = main(["resolve", "--market", "XNAS"])
    assert exit_code == 2
    captured = capsys.readouterr()
    body = json.loads(captured.err)
    assert body["error"] == "RESOLVER_ERROR"
    assert body["reason_code"] == "UNKNOWN_MARKET"


def test_snapshot_happy_path_returns_content_hash(capsys):
    exit_code = main(
        [
            "snapshot",
            "--snapshot-id", "demo-1",
            "--perspective", "PRE_TRADE_INTENT",
            "--as-of-utc", "2026-05-12T12:00:00Z",
            "--knowledge-cutoff-utc", "2026-05-12T12:00:00Z",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert body["snapshot_id"] == "demo-1"
    assert isinstance(body["content_hash"], str)
    assert len(body["content_hash"]) == 64
    int(body["content_hash"], 16)  # valid hex


def test_snapshot_missing_snapshot_id_returns_nonzero(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["snapshot"])
    assert exc_info.value.code == 2


def test_source_file_malformed_value_returns_nonzero(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["resolve", "--source-file", "noequalsign"])
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "name=path" in captured.err


def test_source_file_missing_file_yields_failed_source_status(tmp_path, capsys):
    nonexistent = tmp_path / "does_not_exist.json"
    exit_code = main(
        [
            "resolve",
            "--perspective", "PRE_TRADE_INTENT",
            "--as-of-utc", "2026-05-12T12:00:00Z",
            "--knowledge-cutoff-utc", "2026-05-12T12:00:00Z",
            "--source-file", f"quotes={nonexistent}",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert body["sources"]["quotes"]["freshness"] == "FAILED"
    assert body["sources"]["quotes"]["reason_code"] == "PROVIDER_REPORT_FAILED"


def test_serve_missing_uvicorn_returns_nonzero(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "uvicorn", None)
    exit_code = main(["serve", "--port", "0"])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "uvicorn" in captured.err


def test_serve_calls_uvicorn_run_when_available(monkeypatch):
    calls: dict[str, object] = {}

    def _fake_run(app, host="127.0.0.1", port=8000, **kw):
        calls["app"] = app
        calls["host"] = host
        calls["port"] = port

    fake_uvicorn = types.SimpleNamespace(run=_fake_run)
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

    exit_code = main(["serve", "--host", "0.0.0.0", "--port", "9000"])
    assert exit_code == 0
    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 9000
    assert calls["app"] is not None


def test_resolve_output_is_valid_json(capsys):
    main(["resolve"])
    captured = capsys.readouterr()
    json.loads(captured.out)  # raises if not valid JSON


def test_no_command_returns_argparse_error(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2
