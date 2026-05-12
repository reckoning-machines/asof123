# asof123

Every bug in finance software is secretly an "as of" bug.

asof123 is an open-source temporal semantics layer for financial and
institutional systems. It is a library and an API that resolves what
"as of" means for a given call: which business date, which market phase,
which perspective, which sources are fresh or stale or not yet published,
and which knowledge cutoff and price basis apply.

The canonical contract for this repository is `PRODUCT_CONTRACT.md`. This
README is a working introduction; if it ever disagrees with the contract,
the contract wins.

---

## The Problem

Most "data bugs" in institutional finance software are not data bugs. They
are disagreements about "as of". The same trade, the same position, the
same NAV, the same chart, will be reported differently by different
services in the same firm because each service has quietly invented its
own answer to a small set of temporal questions:

- What business date are we in?
- What market phase are we in (pre-open, open, post-close, weekend,
  holiday, fully closed)?
- Which sources are fresh, which are stale, which are missing, which have
  failed, which are only available at prior close, which are partial, and
  which have not yet been published?
- Is this call a preview, a pre-trade intent, a live read, an executed
  read, a canonical read, a replay, or a historical read?
- What knowledge cutoff is admissible for this call? Can we see data that
  arrived after the business date we are asking about?
- Which timezone governs the interpretation of "today", "yesterday",
  "open", and "close" for the market the caller cares about?
- What publication state and canonical state apply to the answer being
  produced?

Each of these is small in isolation. Together, they produce the bugs that
get blamed on "data quality": a pre-open dashboard quoting last night's
close as if it were live, a replay job that silently sees data from after
the date being replayed, an end-of-day report shipped before the official
close print arrives, an intraday position view that mixes filled orders
with intended orders, an ETL that finishes on time but reads from a stale
upstream.

asof123 exists so that every one of these systems can ask the same
authority the same question and get the same answer.

> External systems report facts.
> asof123 resolves temporal meaning.

That sentence is the entire mental model. It is repeated throughout this
project on purpose.

## What asof123 Is

asof123 is:

- A temporal semantics layer.
- A semantic "as of" resolver.
- A temporal authority for institutional systems.
- A library, callable in-process, plus a small HTTP API for cross-service
  use.

asof123 sits above existing tools and tells them what "as of" means for a
given call. It is intended to sit above:

- pandas and numpy
- market calendar libraries (for example pandas-market-calendars,
  exchange_calendars)
- ETL systems (for example Airflow, Dagster, Prefect, dbt)
- OMS and PMS systems
- dashboards and reporting front ends
- replay and backtest systems
- AI and LLM-driven analytical systems

It does not replace any of those tools. It coordinates how they answer
temporal questions.

External systems report facts. asof123 resolves temporal meaning.

## What asof123 Is Not

asof123 is not, and must not become:

- Not a scheduler. It does not run jobs or fire triggers.
- Not a workflow engine. It does not coordinate DAGs, retries, or task
  graphs.
- Not a distributed clock system. It does not replace NTP, PTP, TrueTime,
  or hybrid logical clocks.
- Not a data warehouse. It does not store historical fact tables for
  analytics.
- Not a temporal database. It does not provide bitemporal storage or
  system-time versioning of arbitrary rows.
- Not an OMS or PMS.
- Not a replacement for pandas, numpy, or any market calendar library.

If a feature request would push asof123 into any of these roles, it
belongs in a different system that calls asof123, not inside asof123.

## Initial Ontology

asof123 exposes a small, fixed vocabulary. The full list is in
`PRODUCT_CONTRACT.md` section 3. The most important nouns:

- TemporalContext
  The resolved answer. Bundles business date, market phase, perspective,
  source statuses, knowledge cutoff, price basis, publication state,
  canonical state, and the UTC instant of resolution.

- Perspective
  The named temporal viewpoint of the caller. For example PREVIEW, LIVE,
  REPLAY.

- MarketPhase
  The current phase of the relevant market or session. For example
  PRE_OPEN, MARKET_OPEN, POST_CLOSE.

- SourceProvider
  A named external system that reports facts to asof123 (a price feed, an
  OMS connector, an internal warehouse).

- SourceStatus
  The resolved state of a SourceProvider at the resolution instant.
  Carries a freshness value plus optional metadata (last update,
  publication state, partial or complete, failure reason).

- KnowledgeCutoff
  The latest UTC instant for which information is considered admissible
  in this TemporalContext. Used to keep future-dated facts out of
  preview, replay, and historical reads.

- AsOfSnapshot
  An immutable, serializable record of a resolved TemporalContext.
  Intended for replay, audit, and reproducibility.

## Initial Perspectives

Perspectives are named so that callers cannot accidentally mix them.

- PREVIEW
  An interactive what-if read. Must not show executed state and must
  honor the knowledge cutoff aggressively.

- PRE_TRADE_INTENT
  A read taken before an order is sent. The world reflects intent, not
  execution.

- LIVE
  A real-time operational read during the trading day. Freshness matters,
  and stale or missing sources must be visible.

- EXECUTED
  A read whose answer must reflect actual fills and cancels, not intent.

- CANONICAL
  The system-of-record read. Provisional values are not acceptable; if
  the canonical source is not published yet, the call must fail closed.

- REPLAY
  A reconstruction of a past TemporalContext, typically driven from an
  AsOfSnapshot. Must not leak data that did not exist at the replayed
  instant.

- HISTORICAL
  An analytical read of a past period. Honors the knowledge cutoff for
  that period and labels its sources accordingly.

These names matter because the same raw data, viewed under two different
perspectives, must produce two different answers, and the difference must
be auditable.

## Initial Market Phases

- PRE_OPEN
- MARKET_OPEN
- POST_CLOSE
- WEEKEND
- HOLIDAY
- CLOSED

CLOSED is the fail-safe default whenever a more specific phase cannot be
resolved. Code that treats an unknown phase as MARKET_OPEN is wrong.

## Concrete Examples

These are the kinds of bugs asof123 exists to prevent.

1. Pre-open PM dashboard using prior close.
   At 07:30 America/New_York, a portfolio manager opens a dashboard. The
   equities feed will not start updating until the opening auction.
   Without asof123, the dashboard quietly displays yesterday's last
   trades as if they were live. With asof123, the resolver returns
   `market_phase = PRE_OPEN`, `price_basis = PRIOR_CLOSE`, and
   `sources.equities_quotes.freshness = PRIOR_CLOSE`. The dashboard
   labels every price accordingly and the PM is not misled.

2. Replay job accidentally seeing future data.
   A replay of a strategy as of business date 2026-02-10 reads from a
   warehouse table that has since been backfilled with corrections dated
   2026-02-11. Without asof123, the replay silently uses corrected data
   that did not exist on the replayed date. With asof123, the replay
   runs under `perspective = REPLAY` with `knowledge_cutoff_utc` pinned
   to the end of 2026-02-10 in the market timezone. Any source whose
   last update is after that cutoff is reported as
   `freshness = NOT_PUBLISHED` for this context, and the replay refuses
   to consume it.

3. Canonical publication not yet available.
   A nightly report runs at 16:05 America/New_York and expects the
   official closing print. The print is late. Without asof123, the
   report ships using the last intraday print as if it were canonical.
   With asof123, the report runs under `perspective = CANONICAL`, the
   official-close SourceProvider reports `freshness = NOT_PUBLISHED`,
   and the resolver fails closed with an explicit reason. The report
   does not ship until the print arrives or a human overrides the
   perspective.

4. Fills partially available intraday.
   A risk view is rebuilt at 11:00 America/New_York. Some fills are in
   the OMS, some are still working, some have been canceled. Without
   asof123, the view inconsistently mixes intent and execution. With
   asof123, the call specifies `perspective = EXECUTED`, the OMS
   SourceProvider reports `freshness = PARTIAL` with metadata about
   which order book slices are complete, and the view labels the
   incomplete slices instead of pretending they are final.

5. ETL finished but prices stale.
   An overnight ETL completes successfully at 02:00 America/New_York,
   but the upstream vendor feed stopped publishing at 21:00 the prior
   day. Without asof123, downstream consumers see "ETL OK" and assume
   the data is current. With asof123, the SourceProvider for that feed
   reports `freshness = STALE` with `last_update_utc` pinned to 21:00,
   and consumers can decide whether to proceed.

## Resolved TemporalContext (JSON)

A realistic resolved TemporalContext looks like this:

    {
      "resolved_at_utc": "2026-05-12T13:45:00Z",
      "perspective": "LIVE",
      "market": "XNYS",
      "market_timezone": "America/New_York",
      "business_date": "2026-05-12",
      "market_phase": "MARKET_OPEN",
      "knowledge_cutoff_utc": "2026-05-12T13:45:00Z",
      "price_basis": "LAST_TRADE",
      "publication_state": "PUBLISHED",
      "canonical_state": "PROVISIONAL",
      "sources": {
        "equities_quotes": {
          "provider": "vendor_a_equities",
          "freshness": "FRESH",
          "last_update_utc": "2026-05-12T13:44:58Z"
        },
        "corporate_actions": {
          "provider": "internal_ca_warehouse",
          "freshness": "PRIOR_CLOSE",
          "last_update_utc": "2026-05-11T21:05:00Z"
        },
        "official_close": {
          "provider": "exchange_official_close",
          "freshness": "NOT_PUBLISHED",
          "expected_publication_utc": "2026-05-12T20:15:00Z"
        }
      }
    }

Every datetime is UTC. The market is identified by its MIC (XNYS) and
paired with an explicit IANA timezone. There are no naive datetimes.

## Python Example

asof123 is intended to be called in-process from any service that needs
temporal semantics. A typical pre-trade call:

    from asof123 import resolve_asof

    ctx = resolve_asof(
        perspective="PRE_TRADE_INTENT",
        market="XNYS",
    )

    if ctx.market_phase != "MARKET_OPEN":
        raise RuntimeError(
            f"Cannot send order: market_phase={ctx.market_phase}"
        )

    if ctx.execution_state == "NOT_EXECUTED":
        # We are still in the intent phase. Read positions from the
        # intent view, not the executed view.
        positions = intent_positions(as_of=ctx)
    else:
        positions = executed_positions(as_of=ctx)

    if ctx.sources["equities_quotes"].freshness != "FRESH":
        raise RuntimeError(
            "Quotes are not fresh; refusing to size a new order"
        )

The point of the example is not the function signature. The point is
that the semantic decisions ("are we open?", "is this intent or
execution?", "are quotes fresh?") are centralized in a single resolver
and a single ontology, instead of being reinvented in every caller.

## Open-Source Boundary

The open-source core of asof123 ships with:

- Timezone handling built on standard IANA tz data.
- Basic market calendar support.
- NYSE-style and Nasdaq-style example calendars and phase definitions.
- Static SourceProvider implementations for tests and demos.
- File-based SourceProvider implementations.
- Simple Postgres freshness providers (read last-update timestamps from
  a named table or query).
- A FastAPI reference application.
- A CLI reference command.

The following adapters are intentionally outside the open-source core.
They may exist as private or commercial integrations downstream, but
they are not required by, and will not be merged into, this repository:

- Bloomberg adapters or Bloomberg-derived data.
- OMS and PMS integrations.
- Broker fill adapters.
- Internal or proprietary data warehouse adapters.
- Internal fund accounting and fund administration systems.

This boundary keeps the open-source core free of commercial license
dependencies and free of proprietary schemas.

## Quickstart

See `docs/quickstart.md` for installation, the `asof123` CLI
(`resolve`, `snapshot`, `serve`), and the runnable example scripts
under `examples/` (`examples/resolve_demo.py`,
`examples/snapshot_demo.py`, plus the
`examples/source_status_quotes.json` fixture they read).

## Status

This repository ships a Python library, a CLI, a FastAPI reference
app, and runnable example scripts. There is still no persistence, no
auth, no scheduler, and no background worker. The chronological build
reports under `docs/` describe how each layer was added.
