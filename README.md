# asof123

asof123 is a temporal authority for institutional systems.

External systems report facts. asof123 resolves temporal meaning.

Most Wall Street bugs are secretly "as of" bugs.

If you have ever copied one of these checks into a notebook, ETL task, replay
job, dashboard, report runner, or trading script, this library is for you:

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

Those checks are small until they are everywhere. Then every codebase has its
own version of "as of", "fresh", "closed", "canonical", and "safe to replay".

asof123 gives those decisions one vocabulary:

- `AsOfRequest`
- `AsOf`
- `Perspective`
- `MarketPhase`
- `SourceStatus`
- `SourcePolicy`
- `PriceBasis`
- `PublicationState`
- `CanonicalState`
- `AsOfSnapshot`

An As-Of answer is represented by `AsOf`.

The contract is `PRODUCT_CONTRACT.md`. If this README and the contract ever
disagree, the contract wins.

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
- Use the same semantics from Python, CLI, or the reference FastAPI app.

## Minimal Python

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
```

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

Start there for:

- business date;
- market phase;
- stale quotes;
- replay safety;
- canonical close;
- pre-trade checks;
- snapshot audit.

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
