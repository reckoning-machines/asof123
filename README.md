# asof123

asof123 is a temporal authority for institutional systems.

External systems report facts. asof123 resolves temporal meaning.

The practical problem is duplicated time-state code. Wall Street developers
and data scientists keep rewriting the same checks across scripts, ETL jobs,
dashboards, reports, replay systems, research pipelines, and trading tools:

- What business date applies?
- Is the market pre-open, open, post-close, weekend, holiday, or closed?
- Which source facts are fresh, stale, missing, failed, partial, or not
  published?
- Can replay or historical code see this update, or did it arrive after the
  knowledge cutoff?
- Can a canonical read proceed, or must it fail closed because publication
  facts do not prove readiness?

asof123 centralizes those decisions behind a small public ontology and resolver
boundary. Downstream systems still fetch prices, run reports, store data,
route orders, and orchestrate jobs. They stop inventing incompatible answers to
"as of what?"

The canonical contract is `PRODUCT_CONTRACT.md`. This README is an
introduction. If the README and contract disagree, the contract wins.

## Where To Start

- `docs/quickstart.md`: shortest path from clone to a resolved
  `TemporalContext`.
- `docs/recipes/README.md`: practical copy-paste recipes for business dates,
  market phase, stale quotes, replay safety, canonical close checks,
  pre-trade checks, and snapshot audit identity.
- `PRODUCT_CONTRACT.md`: canonical ontology, fail-closed rules, API surface,
  error contract, snapshot contract, and open-source boundary.

## What It Is Today

The open-source package implements the resolver/reference boundary of a
temporal authority:

- `ResolveRequest` validates the requested perspective, market, market
  timezone, `as_of_utc`, and `knowledge_cutoff_utc`.
- `TemporalContext` is the resolved answer: business date, market phase,
  perspective, source statuses, knowledge cutoff, price basis, execution
  state, publication state, canonical state, and resolution instant.
- `MarketCalendar` is the calendar protocol; `XNYSCalendar` is a minimal
  deterministic reference calendar.
- `SourceProvider` is the fact-reporting boundary; `StaticProvider` and
  `FileProvider` are concrete reference providers.
- `SourcePolicy` and `apply_source_policy()` cover required sources, source
  max-age checks, and replay/historical knowledge-cutoff admissibility.
- The canonical publication gate can return a `CANONICAL` context only when
  exactly one caller-supplied publication assertion validates and proves
  `publication_state=PUBLISHED` plus `canonical_state=CANONICAL`.
- `AsOfSnapshot` and `make_snapshot()` produce deterministic snapshot hashes
  for audit identity.
- The CLI exposes `resolve`, `snapshot`, and `serve`.
- The FastAPI app is a reference API for resolve/status/snapshot calls.

In this repository, "temporal authority" means a contract-bound resolver that
returns a validated `TemporalContext` or fails closed with an explicit reason.
It does not mean this repo is a deployed production service.

## Guarantees Today

Current behavior callers can rely on:

- Naive datetimes are rejected in public request/model paths.
- Machine instants must be UTC-aware.
- Market timezones must be explicit IANA names such as
  `America/New_York`.
- `LIVE` requests cannot provide `as_of_utc` or `knowledge_cutoff_utc`.
- `REPLAY` and `HISTORICAL` requests must provide both `as_of_utc` and
  `knowledge_cutoff_utc`.
- `knowledge_cutoff_utc` cannot be after `as_of_utc` when both are supplied.
- Unknown markets, calendar mismatches, timezone mismatches, and duplicate
  providers fail closed through `ResolverError`.
- Provider reporting failures become `SourceStatus(freshness=FAILED)` instead
  of disappearing.
- Optional `SourcePolicy` makes missing required sources explicit, marks
  replay/historical sources updated after the cutoff as `NOT_PUBLISHED`, and
  marks sources older than configured thresholds as `STALE`.
- `CANONICAL` resolution fails closed unless one validated publication
  assertion proves publication and canonical readiness.
- Snapshot hashes are deterministic for the same semantic payload.

## What It Does Not Do

asof123 is not:

- a scheduler;
- a workflow engine;
- a data warehouse;
- a temporal database for arbitrary rows;
- an OMS, EMS, or PMS;
- an order router;
- a broker adapter;
- a Bloomberg adapter;
- a mutable source registry;
- an auth, persistence, or deployment platform;
- a production exchange-calendar authority;
- a persisted replay engine;
- a full canonical publication authority.

Those systems can call asof123. They are not implemented by asof123.

## Current Vocabulary

The public ontology is defined by `PRODUCT_CONTRACT.md`. The main nouns in the
current runtime are:

- `ResolveRequest`
- `TemporalContext`
- `Perspective`
- `MarketPhase`
- `SourceProvider`
- `SourceStatus`
- `SourcePolicy`
- `SourceFreshness`
- `PriceBasis`
- `PublicationState`
- `CanonicalState`
- `AsOfSnapshot`

Use these names in downstream code instead of local replacement names.

## Minimal Python Use

```python
from datetime import datetime, timezone

from asof123 import ResolveRequest, XNYSCalendar, resolve

ctx = resolve(
    ResolveRequest(
        perspective="PRE_TRADE_INTENT",
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc),
    ),
    calendars={"XNYS": XNYSCalendar()},
)

print(ctx.business_date)
print(ctx.market_phase)
print(ctx.price_basis)
```

For practical examples, use `docs/recipes/README.md`. The recipes cover:

- business date;
- market phase;
- stale quotes;
- replay safety;
- canonical close;
- pre-trade checks;
- snapshot audit.

## CLI

```bash
asof123 resolve \
  --perspective PRE_TRADE_INTENT \
  --market XNYS \
  --market-timezone America/New_York \
  --as-of-utc 2026-05-12T14:00:00Z

asof123 snapshot \
  --snapshot-id demo-001 \
  --perspective PRE_TRADE_INTENT \
  --market XNYS \
  --market-timezone America/New_York \
  --as-of-utc 2026-05-12T14:00:00Z
```

The CLI can read file-backed `SourceStatus` fixtures with
`--source-file name=path` and can apply `SourcePolicy` with
`--required-source`, `--max-age-seconds`, and
`--max-age-source name=seconds`.

See `docs/quickstart.md` for runnable commands.

## FastAPI Reference App

The FastAPI app is a reference surface, not a production deployment layer.

Current endpoints:

- `GET /asof/current`
- `POST /asof/resolve`
- `GET /sources/status`
- `POST /sources/report` returns 501 because there is no mutable source
  registry.
- `POST /asof/snapshot`

`POST /asof/resolve` accepts either a bare `ResolveRequest` or an optional
wrapper:

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

The app has no auth, no persistence, no background worker, and no provider
registry. Calendars and providers are injected when the app is constructed.

## Open-Source Boundary

The open-source core may include generic semantics, public models, reference
providers, reference calendars, tests, CLI, recipes, and reference HTTP
surfaces.

It must not include Bloomberg integrations, proprietary OMS/PMS adapters,
broker adapters, internal warehouse schemas, fund-accounting integrations,
schedulers, workflow engines, or deployment-specific auth/persistence.

Keeping that boundary clean is what lets asof123 remain the shared temporal
semantics layer those systems call.
