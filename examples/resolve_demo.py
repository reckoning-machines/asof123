"""Minimal demo: resolve a LIVE AsOf using a FileProvider.

Run from the repo root after `pip install -e .`:

    python examples/resolve_demo.py

The script wires a single `FileProvider` (reading from
`examples/source_status_quotes.json`) to the in-process resolver and
prints the resulting `AsOf` as pretty-printed JSON. There
is no argparse, no network, no environment loading, and no persistence
in this script. It is intended as a 30-line reference for how the
library composes.
"""

from __future__ import annotations

import json
from pathlib import Path

from asof123.calendars import XNYSCalendar
from asof123.enums import Perspective
from asof123.providers import FileProvider
from asof123.requests import AsOfRequest
from asof123.resolver import resolve


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

    print(
        json.dumps(
            asof.model_dump(mode="json"),
            sort_keys=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
