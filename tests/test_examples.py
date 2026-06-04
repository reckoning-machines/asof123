"""Tests for the example fixtures, demo scripts, and the quickstart doc.

The two demo scripts are exercised in-process via `runpy.run_path`
with `run_name="__main__"` so the scripts' `if __name__ == "__main__"`
blocks execute and their `print(...)` output is captured by `capsys`.
"""

from __future__ import annotations

import json
import runpy
from datetime import datetime, timezone
from pathlib import Path

from asof123.providers import FileProvider


REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
QUICKSTART_PATH = REPO_ROOT / "docs" / "quickstart.md"


def test_source_status_quotes_json_validates_via_file_provider():
    path = EXAMPLES_DIR / "source_status_quotes.json"
    assert path.exists(), f"missing fixture: {path}"

    provider = FileProvider("quotes_feed", path)
    now = datetime(2026, 5, 12, 13, 45, 0, tzinfo=timezone.utc)
    status = provider.report(now)

    assert status.provider == "quotes_feed"
    assert status.freshness.value == "FRESH"
    assert status.last_update_utc is not None
    assert status.last_update_utc.utcoffset().total_seconds() == 0
    assert "row_count" in status.metadata
    assert "symbol_count" in status.metadata


def test_resolve_demo_runs_and_emits_valid_asof_json(capsys):
    runpy.run_path(
        str(EXAMPLES_DIR / "resolve_demo.py"), run_name="__main__"
    )
    captured = capsys.readouterr()

    body = json.loads(captured.out)
    assert body["market"] == "XNYS"
    assert body["market_timezone"] == "America/New_York"
    assert body["perspective"] == "LIVE"
    assert "quotes_feed" in body["sources"]
    assert body["sources"]["quotes_feed"]["provider"] == "quotes_feed"
    assert body["sources"]["quotes_feed"]["freshness"] == "FRESH"


def test_snapshot_demo_runs_and_emits_snapshot_json(capsys):
    runpy.run_path(
        str(EXAMPLES_DIR / "snapshot_demo.py"), run_name="__main__"
    )
    captured = capsys.readouterr()

    body = json.loads(captured.out)
    assert body["snapshot_id"] == "demo_snapshot"
    assert isinstance(body["content_hash"], str)
    assert len(body["content_hash"]) == 64
    int(body["content_hash"], 16)  # valid hex
    assert body["captured_at_utc"].endswith("Z") or "+00:00" in body[
        "captured_at_utc"
    ]
    assert body["asof"]["market"] == "XNYS"


def test_quickstart_md_contains_key_commands_and_example_paths():
    text = QUICKSTART_PATH.read_text(encoding="utf-8")
    assert "asof123 resolve" in text
    assert "asof123 snapshot" in text
    assert "asof123 serve" in text
    assert "examples/resolve_demo.py" in text
    assert "examples/snapshot_demo.py" in text
    assert "pip install -e" in text
