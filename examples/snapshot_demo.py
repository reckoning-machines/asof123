"""Minimal demo: resolve and snapshot an AsOf using a FileProvider.

Run from the repo root after `pip install -e .`:

    python examples/snapshot_demo.py

The script runs the same resolve flow as `resolve_demo.py` and wraps
the result in an `AsOfSnapshot` via `make_snapshot(asof,
snapshot_id="demo_snapshot")`. The snapshot's `content_hash` is a
deterministic SHA256 over the versioned snapshot payload. There is no
argparse, no network, no environment loading, and no persistence in
this script.
"""

from __future__ import annotations

import json
from pathlib import Path

from asof123.calendars import XNYSCalendar
from asof123.enums import Perspective
from asof123.providers import FileProvider
from asof123.requests import AsOfRequest
from asof123.resolver import resolve
from asof123.snapshot import make_snapshot


def main() -> None:
    here = Path(__file__).resolve().parent
    quotes_file = here / "source_status_quotes.json"

    provider = FileProvider("quotes_feed", quotes_file)
    request = AsOfRequest(
        perspective=Perspective.LIVE,
        market="XNYS",
        market_timezone="America/New_York",
    )
    asof = resolve(request, {"XNYS": XNYSCalendar()}, [provider])
    snapshot = make_snapshot(asof, snapshot_id="demo_snapshot")

    print(
        json.dumps(
            snapshot.model_dump(mode="json"),
            sort_keys=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
