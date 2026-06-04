# asof123

asof123 gives notebooks, ETL jobs, dashboards, and research pipelines one
consistent answer to:

```text
As of this instant, what market date are we in?
Is the market open?
What price basis is valid?
Are the facts fresh and admissible?
Would this replay have seen future data?
```

External systems report facts. asof123 resolves temporal meaning.

Most Wall Street bugs are secretly as-of bugs.

If you have copied one of these checks into a notebook, ETL task, replay job,
dashboard, report runner, or trading script, this library is for you:

```python
if now.weekday() >= 5:
    use_previous_business_day()

if quotes_last_update < now - timedelta(seconds=5):
    block_trade()

if warehouse_update > replay_cutoff:
    reject_future_data()

if official_close_published and official_close_final:
    run_report()
```

Each check looks harmless until every system has its own answer. Then every
codebase has its own version of "as of", "fresh", "closed", "canonical", and
"safe to replay".

asof123 is a temporal authority for institutional systems. An As-Of answer is
represented by `AsOf`.

## Minimal Python

Ask for an `AsOf`; get back the decision fields your notebook or job should use.

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

print(asof.business_date)
print(asof.market_phase)
print(asof.price_basis)

print(asof.market_datetime)
print(asof.sources)
```

## What You Get Back

| Field | Meaning |
| --- | --- |
| `business_date` | The market business date resolved by the calendar. |
| `market_phase` | `PRE_OPEN`, `MARKET_OPEN`, `POST_CLOSE`, `WEEKEND`, `HOLIDAY`, or `CLOSED`. |
| `price_basis` | The price convention for the current context, such as `LAST_TRADE` or `PRIOR_CLOSE`. |
| `sources` | Freshness and admissibility state for data inputs such as quotes, locates, warehouse rows, or official close files. |
| `resolved_at_utc` | The UTC audit instant. |
| `market_datetime` | A derived market-local projection for humans reading the answer. |

`market_datetime` and `market_date` are convenience output derived from
`resolved_at_utc` and `market_timezone`. They are not a second source of truth.
Branch on `business_date`, `market_phase`, `price_basis`, `publication_state`,
`canonical_state`, and `execution_state`.

## Common Uses

- Label research rows with the correct market business date.
- Stop copying market-open checks into every notebook or dashboard.
- Block stale or missing quotes with explicit `SourceStatus` values.
- Prevent replay and historical reads from using facts after
  `knowledge_cutoff_utc`.
- Fail closed unless official publication facts prove a canonical read.
- Snapshot an analysis run with deterministic audit identity.
- Display market time without making browser code decide business meaning.

## What You Can Do Today

- Resolve market business date and market phase for a request.
- Reject naive and non-UTC datetimes at the boundary.
- Normalize provider failures into `SourceStatus(freshness=FAILED)`.
- Require sources such as `quotes`, `locates`, `warehouse`, or
  `official_close`.
- Mark stale sources with `SourcePolicy`.
- Prevent replay and historical reads from using source updates after
  `knowledge_cutoff_utc`.
- Resolve a narrow `CANONICAL` read when one supplied publication assertion
  proves `publication_state=PUBLISHED` and `canonical_state=CANONICAL`.
- Create deterministic snapshot hashes for audit identity.
- Expose derived market-time projections (`market_datetime`, `market_date`) so
  humans can read the resolved AsOf without every UI, report, ETL job, or
  notebook reimplementing timezone conversion.
- Use the same semantics from Python, CLI, or the reference FastAPI app.

## SourcePolicy

Use `SourcePolicy` when the repeated code is really:

```python
if quotes_missing or quotes_stale or update_after_cutoff:
    fail_closed()
```

CLI:

```bash
asof123 resolve \
  --perspective REPLAY \
  --market XNYS \
  --market-timezone America/New_York \
  --as-of-utc 2026-02-10T21:00:00Z \
  --knowledge-cutoff-utc 2026-02-10T21:00:00Z \
  --source-file quotes=examples/source_status_quotes.json \
  --required-source quotes \
  --max-age-seconds 300
```

API wrapper:

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

## Recipes

Copy-paste examples live in `docs/recipes/README.md`.

Core authority recipes:

- business date;
- market phase;
- stale quotes;
- replay safety;
- canonical close;
- pre-trade checks;
- snapshot audit.

Display and integration recipes:

- UTC everywhere, ET nowhere;
- browser-safe market time display.

`docs/quickstart.md` has the shortest clone-to-running path.

## Boundary

asof123 does not fetch your data or run your platform.

It is not:

- a scheduler;
- a workflow engine;
- a data warehouse;
- an OMS, EMS, or PMS;
- an order router;
- a broker adapter;
- a Bloomberg adapter;
- a mutable source registry;
- an auth, persistence, or deployment layer;
- a production exchange-calendar authority;
- a persisted replay engine;
- a full canonical publication authority.

Those systems can call asof123. They are not implemented by asof123.

## Current Surfaces

- Python package.
- CLI: `resolve`, `snapshot`, `serve`.
- Reference FastAPI app:
  - `GET /asof/current`
  - `POST /asof/resolve`
  - `GET /sources/status`
  - `POST /sources/report` returns 501; the reference app is read-only.
  - `POST /asof/snapshot`
- `StaticProvider` and `FileProvider`.
- Minimal `XNYSCalendar`.
- Deterministic snapshot helper.

The open-source boundary is intentionally boring. No proprietary adapters, no
workflow runtime, no database dependency, no broker dependency. Bring your
facts; get back temporal meaning.

The contract is `PRODUCT_CONTRACT.md`. If this README and the contract ever
disagree, the contract wins.
