# asof123 Quickstart

Get from `git clone` to a resolved `AsOf` quickly.

## Mental Model

External systems report facts.
asof123 resolves temporal meaning.

There is no persistence, auth, scheduler, workflow engine, OMS/EMS/PMS, broker
adapter, data warehouse, or mutable source registry in this repo.

## Install

Editable install with dev extras:

```bash
pip install -e ".[dev]"
```

For library-only use:

```bash
pip install -e .
```

For HTTP serving without the test stack:

```bash
pip install -e ".[serve]"
```

## Run Tests

```bash
python -m pytest -q
```

## Resolve An AsOf

Infrastructure timestamps stay in UTC. Market-facing output is projected from
`resolved_at_utc` through `market_timezone`.

Python:

```python
from datetime import datetime, timezone

from asof123 import AsOfRequest, XNYSCalendar, resolve

asof = resolve(
    AsOfRequest(
        perspective="PRE_TRADE_INTENT",
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc),
    ),
    calendars={"XNYS": XNYSCalendar()},
)

print(asof.resolved_at_utc)
print(asof.market_datetime)
print(asof.market_date)
print(asof.business_date)
print(asof.market_phase)
print(asof.price_basis)
```

For the pinned XNYS example above:

- `resolved_at_utc` is the UTC audit instant: `2026-05-12 14:00:00+00:00`;
- `market_datetime` is the convenience New York projection:
  `2026-05-12 10:00:00-04:00`;
- `market_date` is the market-local calendar date: `2026-05-12`;
- `business_date` is the calendar-resolved business date: `2026-05-12`.

`market_datetime` and `market_date` are derived from `resolved_at_utc` plus
`market_timezone`. They are not independent sources of temporal truth.

CLI:

```bash
asof123 resolve \
  --perspective PRE_TRADE_INTENT \
  --market XNYS \
  --market-timezone America/New_York \
  --as-of-utc 2026-05-12T14:00:00Z
```

## Add SourcePolicy

Use policy flags when shell, batch, or CI jobs need required-source and
freshness checks:

```bash
asof123 resolve \
  --perspective REPLAY \
  --market XNYS \
  --market-timezone America/New_York \
  --as-of-utc 2026-02-10T21:00:00Z \
  --knowledge-cutoff-utc 2026-02-10T21:00:00Z \
  --source-file quotes_feed=examples/source_status_quotes.json \
  --required-source quotes_feed \
  --max-age-seconds 300
```

Policy can also be supplied through the reference API wrapper:

```json
{
  "request": {
    "perspective": "PRE_TRADE_INTENT",
    "market": "XNYS",
    "market_timezone": "America/New_York",
    "as_of_utc": "2026-05-12T14:00:00Z"
  },
  "policy": {
    "required_sources": ["quotes"],
    "max_age_seconds": 300
  }
}
```

## Snapshot A Context

```bash
asof123 snapshot \
  --snapshot-id demo \
  --perspective PRE_TRADE_INTENT \
  --market XNYS \
  --market-timezone America/New_York \
  --as-of-utc 2026-05-12T14:00:00Z
```

Snapshots are deterministic audit artifacts. They are not a persisted replay
engine.

## Serve The Reference API

```bash
pip install -e ".[serve]"
asof123 serve --host 127.0.0.1 --port 8000
```

Current endpoints:

- `GET /asof/current`
- `POST /asof/resolve`
- `GET /sources/status`
- `POST /sources/report` returns 501 because the reference app is read-only.
- `POST /asof/snapshot`

The app loads no environment variables, opens no databases, and holds no
mutable state beyond the calendars and providers handed to `create_app(...)`
at construction time.

## Example Scripts

The smallest end-to-end scripts are:

```bash
python examples/resolve_demo.py
python examples/snapshot_demo.py
```

## Recipes

For practical copy-paste examples, use `docs/recipes/README.md`.

Recipes cover:

- business date;
- market phase;
- stale quotes;
- replay safety;
- canonical close;
- pre-trade checks;
- snapshot audit;
- UTC everywhere, ET nowhere;
- browser-safe market time display.

## Contract

`PRODUCT_CONTRACT.md` is canonical. README and recipes are subordinate to it.
