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
    # LIVE forbids as_of_utc; ResolveRequest's validator rejects it.
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


def test_resolve_canonical_fails_closed_without_authority(capsys):
    exit_code = main(["resolve", "--perspective", "CANONICAL"])
    assert exit_code == 2
    captured = capsys.readouterr()
    body = json.loads(captured.err)
    assert body["error"] == "RESOLVER_ERROR"
    assert body["reason_code"] == "CANONICAL_UNSUPPORTED"


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
