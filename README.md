# asof123

asof123 is a temporal authority for institutional systems.

External systems report facts. asof123 resolves temporal meaning.

The practical problem is duplicated time-state code. Wall Street developers
rewrite the same fragile checks in scripts, ETL jobs, dashboards, reports,
replay systems, research pipelines, and trading tools:

- Is "today" the calendar date, the market business date, or the prior
  session?
- Is the market pre-open, open, post-close, closed, weekend, or holiday?
- Can a replay or historical read see this source update, or did it arrive
  after the knowledge cutoff?
- Is this source fresh, stale, missing, failed, prior-close, partial, or not
  published?
- Can a canonical read proceed, or must it fail closed because the official
  publication is not available?

asof123 centralizes those decisions behind a small public ontology and a
resolver boundary. Downstream systems still fetch prices, run reports,
orchestrate jobs, and store data. They stop inventing incompatible answers to
"as of what?"

The canonical contract for this repository is `PRODUCT_CONTRACT.md`. This
README is an introduction. If the README and contract disagree, the contract
wins. The current runtime boundary is defined in
`docs/contracts/runtime_boundary_contract.md`.

For copy-paste integration patterns, see `docs/recipes/README.md`.

## What This Deletes

Without asof123, every caller tends to grow local rules:

```python
if now.tzinfo is None:
    raise ValueError("bad datetime")

if now.weekday() >= 5:
    phase = "closed"
elif local_time < time(9, 30):
    phase = "pre_open"
elif local_time < time(16, 0):
    phase = "open"
else:
    phase = "post_close"

if source_last_update > replay_cutoff:
    usable = False
```

With asof123, the caller asks for a `TemporalContext` and applies the same
source policy everywhere:

```python
ctx = resolve(request, calendars={"XNYS": XNYSCalendar()}, providers=providers)

sources = apply_source_policy(
    perspective=Perspective.REPLAY,
    knowledge_cutoff_utc=request.knowledge_cutoff_utc,
    now_utc=request.as_of_utc,
    sources=ctx.sources,
    policy=SourcePolicy(required_sources={"quotes"}, max_age_seconds=300),
)
```

The point is not less code for its own sake. The point is that business date,
market phase, perspective, source freshness, replay cutoff, and snapshot
identity are resolved through one vocabulary instead of being reimplemented
with local booleans and comments.

## What It Is Today

The open-source package currently implements the resolver/reference boundary
of a temporal authority:

- `ResolveRequest` validates the caller's requested perspective, market,
  market timezone, `as_of_utc`, and `knowledge_cutoff_utc`.
- `TemporalContext` is the resolved answer: business date, market phase,
  perspective, source statuses, knowledge cutoff, price basis, execution
  state, publication state, canonical state, and resolution instant.
- `MarketCalendar` is the calendar protocol; `XNYSCalendar` is a minimal
  deterministic reference calendar.
- `SourceProvider` is the fact-reporting boundary; `StaticProvider` and
  `FileProvider` are current concrete providers.
- `SourcePolicy` and `apply_source_policy()` cover required sources, source
  max-age checks, and replay/historical knowledge-cutoff admissibility.
- `AsOfSnapshot` and `make_snapshot()` produce deterministic snapshot hashes
  for audit identity.
- The CLI exposes `resolve`, `snapshot`, and `serve`.
- The FastAPI app is a reference API for resolve/status/snapshot calls.

In this repository, "temporal authority" means a contract-bound resolver that
returns a validated `TemporalContext` or fails closed with an explicit reason.
It does not mean this repo is a deployed production service.

## Guarantees Today

Current behavior that callers can rely on:

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
- `CANONICAL` resolution can return a canonical context only when exactly one
  caller-supplied publication assertion validates and proves
  `publication_state=PUBLISHED` plus `canonical_state=CANONICAL`.
- `CANONICAL` resolution fails closed with an explicit publication readiness
  reason when publication facts are missing, malformed, ambiguous, not
  published, not canonical, after cutoff, or include unsupported lifecycle
  metadata.
- Snapshot hashes are deterministic for the same semantic payload.

## What It Does Not Do Today

asof123 is not:

- a scheduler;
- a workflow engine;
- a data warehouse;
- a temporal database for arbitrary rows;
- an OMS or PMS;
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

- `ResolveRequest`: inbound request for temporal meaning.
- `TemporalContext`: resolved answer.
- `Perspective`: `PREVIEW`, `PRE_TRADE_INTENT`, `LIVE`, `EXECUTED`,
  `CANONICAL`, `REPLAY`, `HISTORICAL`.
- `MarketPhase`: `PRE_OPEN`, `MARKET_OPEN`, `POST_CLOSE`, `WEEKEND`,
  `HOLIDAY`, `CLOSED`.
- `SourceProvider`: caller-supplied fact reporter.
- `SourceStatus`: reported/resolved source state.
- `SourcePolicy`: optional source admissibility policy.
- `PriceBasis`: `PRIOR_CLOSE`, `LAST_TRADE`, `INDICATIVE`,
  `OFFICIAL_CLOSE`, `SETTLEMENT`, `MODEL`, `UNKNOWN`.
- `PublicationState`: current publication-state vocabulary.
- `CanonicalState`: current canonical-state vocabulary.
- `AsOfSnapshot`: immutable resolved-context audit artifact.

Do not add local replacement names in downstream code. Use these names or add
to the product contract intentionally.

## Python: Resolve A Context

This is implemented today.

```python
from datetime import datetime, timezone

from asof123 import (
    ResolveRequest,
    SourceFreshness,
    SourceStatus,
    StaticProvider,
    XNYSCalendar,
    resolve,
)

quotes = StaticProvider(
    "quotes",
    SourceStatus(
        provider="quotes",
        freshness=SourceFreshness.FRESH,
        last_update_utc=datetime(2026, 5, 12, 13, 59, 58, tzinfo=timezone.utc),
    ),
)

request = ResolveRequest(
    perspective="PRE_TRADE_INTENT",
    market="XNYS",
    market_timezone="America/New_York",
    as_of_utc=datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc),
)

ctx = resolve(
    request,
    calendars={"XNYS": XNYSCalendar()},
    providers=[quotes],
)

if ctx.market_phase != "MARKET_OPEN":
    raise RuntimeError(f"Cannot send order: market_phase={ctx.market_phase}")

if ctx.sources["quotes"].freshness != "FRESH":
    raise RuntimeError("Cannot size order from non-fresh quotes")
```

The downstream caller no longer owns market timezone conversion, phase
calculation, source status shape, or perspective naming.

## Python: Apply Source Policy

This is implemented today in Python, CLI, and the reference API.

```python
from datetime import datetime, timezone

from asof123 import (
    Perspective,
    SourceFreshness,
    SourcePolicy,
    SourceStatus,
    apply_source_policy,
)

cutoff = datetime(2026, 2, 10, 21, 0, 0, tzinfo=timezone.utc)
as_of = datetime(2026, 2, 10, 21, 0, 0, tzinfo=timezone.utc)

sources = {
    "warehouse": SourceStatus(
        provider="warehouse",
        freshness=SourceFreshness.FRESH,
        last_update_utc=datetime(2026, 2, 11, 1, 0, 0, tzinfo=timezone.utc),
    )
}

checked = apply_source_policy(
    perspective=Perspective.REPLAY,
    knowledge_cutoff_utc=cutoff,
    now_utc=as_of,
    sources=sources,
    policy=SourcePolicy(
        required_sources={"warehouse"},
        max_age_seconds_by_source={"warehouse": 3600},
    ),
)

assert checked["warehouse"].freshness == "NOT_PUBLISHED"
```

That replaces the repeated replay bug pattern:

```python
if warehouse_last_update > replay_cutoff:
    # every job invents its own behavior here
    raise RuntimeError("future data leak")
```

## Python: Resolve A Canonical Read

This is implemented today as a narrow publication-readiness gate. It is not a
full canonical authority platform.

External systems still own the facts. They report publication metadata through
`SourceStatus.metadata["publication"]`. asof123 resolves whether those facts
prove a `CANONICAL` read may proceed.

```python
from datetime import datetime, timezone

from asof123 import (
    ResolveRequest,
    SourceFreshness,
    SourceStatus,
    StaticProvider,
    XNYSCalendar,
    resolve,
)

official_close = StaticProvider(
    "official_close",
    SourceStatus(
        provider="official_close",
        freshness=SourceFreshness.FRESH,
        metadata={
            "publication": {
                "publication_state": "PUBLISHED",
                "canonical_state": "CANONICAL",
                "publication_utc": "2026-05-12T21:05:00Z",
                "asserted_at_utc": "2026-05-12T21:06:00Z",
            }
        },
    ),
)

request = ResolveRequest(
    perspective="CANONICAL",
    market="XNYS",
    market_timezone="America/New_York",
    knowledge_cutoff_utc=datetime(2026, 5, 12, 21, 6, 0, tzinfo=timezone.utc),
)

ctx = resolve(
    request,
    calendars={"XNYS": XNYSCalendar()},
    providers=[official_close],
)

assert ctx.canonical_state == "CANONICAL"
assert ctx.publication_state == "PUBLISHED"
```

This replaces repeated downstream checks like:

```python
if official_close_published and official_close_is_final:
    run_report()
else:
    fail_closed()
```

The current implementation accepts exactly one publication assertion and fails
closed for missing, malformed, ambiguous, not-published, not-canonical,
after-cutoff, withdrawn, or superseded publication metadata. It does not choose
between competing publication sources.

## Execution Admissibility

Execution systems ask a different operational question than research systems.
Research asks "what was knowable then?" Execution asks "what is admissible
now?"

asof123 already covers part of that boundary with existing primitives:
`SourcePolicy`, `Perspective`, `MarketPhase`, `PriceBasis`, `SourceStatus`,
and `TemporalContext`. It does not need execution-specific ontology to answer
basic readiness questions.

```python
from datetime import datetime, timezone

from asof123 import (
    Perspective,
    SourceFreshness,
    SourcePolicy,
    SourceStatus,
    apply_source_policy,
)

now = datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc)

sources = {
    "quotes": SourceStatus(
        provider="quotes",
        freshness=SourceFreshness.FRESH,
        last_update_utc=datetime(2026, 5, 12, 13, 59, 58, tzinfo=timezone.utc),
    ),
    "locates": SourceStatus(
        provider="locates",
        freshness=SourceFreshness.FRESH,
        last_update_utc=datetime(2026, 5, 12, 13, 55, 0, tzinfo=timezone.utc),
    ),
    "basket_file": SourceStatus(
        provider="basket_file",
        freshness=SourceFreshness.FRESH,
        last_update_utc=datetime(2026, 5, 12, 13, 58, 0, tzinfo=timezone.utc),
    ),
}

checked = apply_source_policy(
    perspective=Perspective.PRE_TRADE_INTENT,
    knowledge_cutoff_utc=now,
    now_utc=now,
    sources=sources,
    policy=SourcePolicy(
        required_sources={"quotes", "locates", "basket_file"},
        max_age_seconds_by_source={
            "quotes": 5,
            "locates": 900,
            "basket_file": 300,
        },
    ),
)
```

That replaces duplicated checks like:

```python
if market_open and quotes_fresh and locates_ready and basket_file_ready:
    send_order()
```

asof123 answers the temporal part:

- are required execution facts present?
- are they fresh enough?
- are they stale, missing, failed, or not published?
- did a replay/postmortem read try to use a source updated after the cutoff?
- what `MarketPhase`, `Perspective`, and `PriceBasis` apply to the context?

External systems still do the execution work:

- send orders;
- manage child orders;
- fetch locates;
- generate basket files;
- upload files;
- route orders;
- calculate positions;
- operate an OMS or EMS.

For replay and postmortem execution analysis, use `Perspective.REPLAY` with an
explicit `knowledge_cutoff_utc`; `SourcePolicy` marks sources whose
`last_update_utc` is after the cutoff as not admissible. That helps answer
"what execution facts were knowable then?" without building a replay engine.

## Python: Snapshot A Resolved Context

This is implemented today.

```python
from asof123 import make_snapshot

snapshot = make_snapshot(ctx, snapshot_id="report-2026-05-12T14:00:00Z")

print(snapshot.snapshot_schema_version)
print(snapshot.semantic_contract_version)
print(snapshot.content_hash)
```

Snapshots are deterministic audit artifacts. They are not a persisted replay
engine yet.

## JSON Shape

A resolved `TemporalContext` has this shape:

```json
{
  "resolved_at_utc": "2026-05-12T13:45:00Z",
  "perspective": "LIVE",
  "market": "XNYS",
  "market_timezone": "America/New_York",
  "business_date": "2026-05-12",
  "market_phase": "MARKET_OPEN",
  "knowledge_cutoff_utc": "2026-05-12T13:45:00Z",
  "price_basis": "LAST_TRADE",
  "execution_state": "NOT_EXECUTED",
  "publication_state": "PUBLISHED",
  "canonical_state": "PROVISIONAL",
  "sources": {
    "quotes": {
      "provider": "quotes",
      "freshness": "FRESH",
      "last_update_utc": "2026-05-12T13:44:58Z",
      "expected_publication_utc": null,
      "reason_code": null,
      "explanation": null,
      "metadata": {}
    }
  }
}
```

Every machine datetime is UTC. The market timezone is a named IANA timezone.
The market is an explicit market code such as `XNYS`.

## CLI

The CLI is a thin local wrapper over the resolver and snapshot helper.

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

The CLI can read file-backed `SourceStatus` fixtures through
`--source-file name=path` and can apply the small `SourcePolicy` surface with
`--required-source`, `--max-age-seconds`, and `--max-age-source name=seconds`.

Research/replay example: require prices and reject source updates after the
replay cutoff.

```bash
asof123 resolve \
  --perspective REPLAY \
  --as-of-utc 2026-02-10T21:00:00Z \
  --knowledge-cutoff-utc 2026-02-10T21:00:00Z \
  --source-file quotes_feed=examples/source_status_quotes.json \
  --required-source quotes_feed \
  --max-age-seconds 300
```

Execution example: require quotes and locates before a `PRE_TRADE_INTENT`
context, with a tighter quote freshness threshold.

```bash
asof123 resolve \
  --perspective PRE_TRADE_INTENT \
  --as-of-utc 2026-05-12T14:00:00Z \
  --knowledge-cutoff-utc 2026-05-12T14:00:00Z \
  --source-file quotes_feed=examples/source_status_quotes.json \
  --required-source quotes_feed \
  --required-source locates \
  --max-age-source quotes_feed=5
```

A minimal canonical-read fixture can be supplied the same way:

```bash
cat > /tmp/asof123_official_close.json <<'JSON'
{
  "provider": "official_close",
  "freshness": "FRESH",
  "metadata": {
    "publication": {
      "publication_state": "PUBLISHED",
      "canonical_state": "CANONICAL",
      "publication_utc": "2026-05-12T21:05:00Z",
      "asserted_at_utc": "2026-05-12T21:06:00Z"
    }
  }
}
JSON

asof123 resolve \
  --perspective CANONICAL \
  --market XNYS \
  --market-timezone America/New_York \
  --knowledge-cutoff-utc 2026-05-12T21:06:00Z \
  --source-file official_close=/tmp/asof123_official_close.json
```

That command reads one local `SourceStatus` file. It does not report into a
registry, persist publication facts, poll for official close, or publish a
report.

See `docs/quickstart.md` for runnable commands and `examples/` for example
scripts.

## FastAPI Reference App

The FastAPI app is a reference surface, not a production deployment layer.

Current endpoints:

- `GET /asof/current`
- `POST /asof/resolve`
- `GET /sources/status`
- `POST /sources/report` returns 501 because there is no mutable source
  registry.
- `POST /asof/snapshot`

The app has no auth, no persistence, no background worker, and no provider
registry. Calendars and providers are injected when the app is constructed.
Canonical success over the API requires constructing the app with a provider
that reports valid publication metadata; the reference API does not let clients
mutate a source registry at runtime.

`POST /asof/resolve` also accepts an optional wrapper with policy:

```json
{
  "request": {
    "perspective": "PRE_TRADE_INTENT",
    "market": "XNYS",
    "market_timezone": "America/New_York",
    "as_of_utc": "2026-05-12T14:00:00Z",
    "knowledge_cutoff_utc": "2026-05-12T14:00:00Z"
  },
  "policy": {
    "required_sources": ["quotes", "locates"],
    "max_age_seconds_by_source": {
      "quotes": 5
    }
  }
}
```

The original bare `ResolveRequest` body remains supported.

## Current Behavior vs Future Behavior

Implemented today:

- strict `ResolveRequest` validation;
- minimal XNYS reference calendar behavior;
- source provider reporting and provider-failure surfacing;
- optional `SourcePolicy` for required source, max-age, and replay/historical
  cutoff checks through Python, CLI, and the reference API;
- deterministic `AsOfSnapshot` hashing;
- narrow canonical publication gating from one validated caller-supplied
  publication assertion;
- CLI and reference API for resolve/status/snapshot.

Planned future hardening:

- stronger snapshot/replay identity metadata;
- CLI/API exposure for source policy if the surface remains small;
- richer calendar identity and unsupported-session metadata;
- authority identity and conflict diagnostics for official close, benchmark
  files, accounting snapshots, and similar readiness checks.

Not implemented:

- a broad canonical authority platform;
- authority hierarchy or source-authority selection;
- withdrawal or supersession handling;
- publication conflict resolution;
- a persisted replay engine;
- a scheduler or polling loop;
- a publication workflow engine;
- production calendar coverage;
- proprietary provider adapters.

Official close and report-publication examples are currently limited to the
narrow canonical-read gate described above. asof123 resolves readiness from
supplied facts; it does not own those facts.

## Open-Source Boundary

The open-source core may include generic semantics, public models, reference
providers, reference calendars, tests, CLI, and reference HTTP surfaces.

It should not include Bloomberg integrations, proprietary OMS/PMS adapters,
broker adapters, internal warehouse schemas, fund-accounting integrations,
schedulers, workflow engines, or deployment-specific auth/persistence.

Keeping that boundary clean is what lets asof123 remain the shared temporal
semantics layer those systems call.

## Status

The current package ships a Python library, pinned public enums and models, a
minimal resolver, a reference XNYS calendar, static and file-backed
`SourceProvider` implementations, `SourcePolicy`, pure
`apply_source_policy()`, deterministic snapshot helpers, a CLI, a FastAPI
reference app, examples, and tests.

The strongest value today is eliminating duplicated time-state primitives:
UTC validation, perspective rules, source status shapes, source admissibility
checks, basic market phase logic, narrow canonical publication gating, and
snapshot hashing.

The next valuable work is still small and boundary-focused: expose policy
where useful, strengthen snapshot identity, improve calendar metadata, and
add authority identity and publication lifecycle semantics without building a
scheduler or workflow engine.
