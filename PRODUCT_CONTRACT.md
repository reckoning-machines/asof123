# asof123 Product Contract

Tagline: Every bug in finance software is secretly an "as of" bug.

This document is the canonical contract for the asof123 open-source project.
It defines what asof123 is, what it is not, the ontology it must expose, and
the rules its implementation must follow. Any code, API surface, or
documentation that contradicts this contract is wrong and must be changed to
conform to it.

asof123 is an open-source temporal semantics layer for financial and
institutional systems. It is not a clock service. It is not a scheduler. It
is not a workflow engine. It resolves what "as of" means for a business
context by combining market and session calendars, source freshness, source
authority, publication state, execution state, and named temporal
perspectives.

Core principle:

    External systems report facts.
    asof123 resolves temporal meaning.

---

## 1. What asof123 Is

asof123 is:

- A semantic "as of" resolver.
- A central authority for temporal context in a financial or institutional
  system.
- A library and an API that answers questions of the form:
  - What business date are we in?
  - What market phase are we in (pre-open, open, post-close, weekend,
    holiday, closed)?
  - What source states are fresh, stale, missing, failed, partial, or
    not yet published?
  - Is the caller operating in a preview, pre-trade intent, live,
    executed, canonical, replay, or historical perspective?
  - What knowledge cutoff applies to the answer being produced?
  - What price basis applies (for example last trade, prior close,
    indicative, official close, settlement)?
  - What publication state applies to a given dataset or report?

asof123 answers these questions in a single, consistent, auditable way so
that downstream systems do not each invent their own incompatible notion of
"now" or "as of".

## 2. What asof123 Is Not

asof123 is not, and must not become:

- A time clock or a wall-clock service.
- A distributed clock synchronization system. It does not replace NTP, PTP,
  Spanner TrueTime, or any vector clock or hybrid logical clock scheme.
- A scheduler. It does not run jobs, fire cron triggers, or wake workers.
- An orchestrator. It does not coordinate DAGs, retries, or task graphs.
- A data warehouse. It does not store historical fact tables for analytics.
- A temporal database. It does not provide bitemporal storage or
  system-time versioning of arbitrary rows.
- An order management system (OMS) or portfolio management system (PMS).
- A replacement for pandas, numpy, market calendar libraries (such as
  pandas-market-calendars or exchange_calendars), Airflow, Dagster, Prefect,
  dbt, or data lineage tools.

asof123 sits next to these systems and tells them, and each other, what
"as of" means in a given call. It does not absorb their responsibilities.

## 3. Required Ontology

The following nouns are the initial public ontology of asof123. Every
implementation, API response, and documentation example must use these
names exactly.

- TemporalContext
  The top-level resolved answer. Bundles a business date, market phase,
  perspective, source statuses, knowledge cutoff, price basis, publication
  state, and the UTC instant of resolution.

- Perspective
  A named temporal viewpoint the caller is operating under. See section 4
  for the initial set.

- MarketPhase
  The current phase of a given market or session. See section 5 for the
  initial set.

- SourceStatus
  The resolved state of a named source provider at the resolution instant.
  Carries a SourceFreshness value and optional publication metadata.

- SourceFreshness
  The freshness classification of a source. See section 6 for the initial
  set.

- KnowledgeCutoff
  The latest instant for which information is considered admissible in the
  current TemporalContext. Used to prevent leakage of future-dated facts
  into preview, replay, and historical perspectives.

- PriceBasis
  The pricing convention that applies for the current TemporalContext. See
  section 8 for the initial set.

- ExecutionState
  The execution lifecycle state relevant to the caller. See section 7 for
  the initial set.

- PublicationState
  The publication state of a given dataset, report, or document in the
  current TemporalContext. See section 9 for the initial set.

- CanonicalState
  Whether the answer is considered canonical (the system of record) or
  provisional, and which authority asserts that status. See section 10
  for the initial set.

- BusinessDate
  The business date associated with the current TemporalContext. This is
  not necessarily the calendar date in UTC and is not necessarily the
  calendar date in the caller's local time.

- MarketCalendar
  A named calendar that defines sessions, holidays, half-days, and
  early-close rules for one market or venue.

- SourceProvider
  A named external system that reports facts to asof123 (for example a
  price feed, an OMS connector, an internal warehouse).

- AsOfSnapshot
  An immutable, serializable record of a resolved TemporalContext, intended
  for replay, audit, and reproducibility.

## 4. Required Initial Perspectives

The initial Perspective values are:

- PREVIEW
- PRE_TRADE_INTENT
- LIVE
- EXECUTED
- CANONICAL
- REPLAY
- HISTORICAL

These names are normative. Implementations may add perspectives later, but
must not rename, merge, or drop any of these without a contract change.

## 5. Required Initial Market Phases

The initial MarketPhase values are:

- PRE_OPEN
- MARKET_OPEN
- POST_CLOSE
- WEEKEND
- HOLIDAY
- CLOSED

CLOSED is the fail-safe default when no more specific phase can be
resolved.

## 6. Required Initial Source States

The initial SourceFreshness values are:

- FRESH
- STALE
- MISSING
- FAILED
- PRIOR_CLOSE
- PARTIAL
- PUBLISHED
- NOT_PUBLISHED

A SourceStatus carries one SourceFreshness value plus optional metadata
such as the last observed update instant, the expected publication time,
and the SourceProvider identity.

## 7. Required Initial Execution States

The initial ExecutionState values are:

- NOT_EXECUTED
- INTENDED
- WORKING
- PARTIALLY_FILLED
- FILLED
- CANCELED
- REJECTED
- UNKNOWN

NOT_EXECUTED is the fail-safe default when execution context is not
applicable or cannot be resolved (for example, a PREVIEW or
PRE_TRADE_INTENT call against an instrument with no open orders).
UNKNOWN is reserved for cases where execution status cannot be retrieved
and the call must fail closed rather than guess. INTENDED and WORKING
must never be reported under perspective EXECUTED or CANONICAL.

## 8. Required Initial Price Basis Values

The initial PriceBasis values are:

- PRIOR_CLOSE
- LAST_TRADE
- INDICATIVE
- OFFICIAL_CLOSE
- SETTLEMENT
- MODEL
- UNKNOWN

UNKNOWN is the fail-safe default when no PriceBasis can be resolved for
the current TemporalContext. MODEL covers any model-derived price
(theoretical, mark-to-model, interpolated curve) and must never be
reported as OFFICIAL_CLOSE or SETTLEMENT. OFFICIAL_CLOSE and SETTLEMENT
are reserved for venue-published canonical prices and must not be used
for intraday last-trade values.

## 9. Required Initial Publication States

The initial PublicationState values are:

- NOT_PUBLISHED
- PRE_PUBLISHED
- PUBLISHED
- EMBARGOED
- WITHDRAWN
- FAILED
- UNKNOWN

NOT_PUBLISHED is the fail-safe default when a dataset, report, or
document is expected but has not been released. PRE_PUBLISHED covers
content that has been prepared but is not yet visible to consumers
(for example, a build-and-stage step that has not been promoted).
EMBARGOED covers content held under a release embargo and must not be
treated as PUBLISHED before the embargo lifts. WITHDRAWN covers content
that was previously PUBLISHED and has been retracted; downstream readers
must treat WITHDRAWN as not available, not as historical. FAILED is
reserved for publication attempts that errored. UNKNOWN is reserved for
cases where publication state cannot be determined and the call must
fail closed.

## 10. Required Initial Canonical States

The initial CanonicalState values are:

- PROVISIONAL
- CANONICAL
- SUPERSEDED
- NOT_CANONICAL
- NOT_AVAILABLE
- UNKNOWN

PROVISIONAL is the fail-safe default when an answer can be produced but
no canonical authority has asserted it. CANONICAL is reserved for
answers asserted by the system of record. SUPERSEDED covers values that
were previously CANONICAL and have been replaced by a later canonical
assertion; readers must not treat SUPERSEDED as current. NOT_CANONICAL
covers answers that are valid for other perspectives but explicitly are
not eligible to be canonical (for example, a PREVIEW result).
NOT_AVAILABLE covers cases where a canonical answer exists but cannot be
retrieved at the resolution instant. UNKNOWN is reserved for cases
where canonical state cannot be determined and the call must fail
closed. A call under perspective CANONICAL must resolve to CANONICAL or
fail closed; it must never silently return PROVISIONAL.

## 11. Market Identity Convention

- Public requests and responses must identify markets using a MIC-style
  market code where available. For example, NYSE is XNYS and Nasdaq is
  XNAS.
- Every market code in a public request or response must be paired with
  an explicit IANA timezone in a separate field (for example
  market_timezone).
- A MarketCalendar may also expose an internal calendar_id for use by
  resolver internals, but calendar_id must not replace market plus
  market_timezone in public API models.
- For US equities examples, the contract uses market = XNYS and
  market_timezone = America/New_York.
- No API response may expose a market_phase, business_date, or any
  market-relative field without also exposing the market and
  market_timezone that were used to resolve it.
- If the requested market code has no recognized MarketCalendar, the
  resolver must fail closed per section 13. It must not fall back to a
  default market.

## 12. UTC and Timezone Rule

- All machine instants in asof123 must be represented in UTC.
- All market-facing interpretation (business date, market phase, session
  boundaries) must include an explicit IANA timezone identifier.
- For US equities examples, the IANA timezone is America/New_York.
- No naive datetime values are allowed in public models, API requests, or
  API responses. Every datetime field must carry timezone information, and
  every stored instant must be UTC.
- Conversions between UTC and a market timezone must go through a named
  MarketCalendar. Ad hoc offset arithmetic is not acceptable.

## 13. Fail-Closed Rule

If asof123 cannot resolve temporal semantics safely, it must return an
explicit unresolved or failed status. It must not silently guess, must not
fall back to wall-clock now, and must not assume a default perspective or
market phase.

Concretely:

- If a required SourceProvider has not reported and no fallback is
  configured, the resolved SourceStatus must be MISSING or FAILED, not
  FRESH.
- If a MarketCalendar is unknown, the resolved MarketPhase must be CLOSED
  with an explicit reason, not MARKET_OPEN.
- If a Perspective cannot be determined from the request, the response
  must be an explicit error, not a guessed PREVIEW or LIVE.
- Every fail-closed response must carry a machine-readable reason code and
  a human-readable explanation.

## 14. API Direction

The following endpoints describe the intended shape of the future HTTP
API. They are not yet implemented; they are listed here so the contract
constrains future work.

- GET /asof/current
  Resolve the current TemporalContext for a given perspective, market, and
  caller identity.

- POST /asof/resolve
  Resolve a TemporalContext for an explicit request body. Supports
  overrides for perspective, market, business date, and knowledge cutoff.
  Used by preview, replay, and historical callers.

- POST /sources/report
  A SourceProvider reports its current state (last update instant,
  publication state, partial or complete, failure reason).

- GET /sources/status
  Read the current resolved state of one or more SourceProviders.

- POST /asof/snapshot
  Materialize the current or specified TemporalContext as an immutable
  AsOfSnapshot suitable for replay and audit.

All request and response bodies must obey the UTC and timezone rule in
section 12 and the fail-closed rule in section 13.

## 15. Open-Source Boundary

The open-source core of asof123 may ship with:

- Timezone handling built on standard IANA tz data.
- Basic market calendar support.
- NYSE-style and Nasdaq-style example calendars and phase definitions.
- Static SourceProvider implementations (constant fixtures for tests and
  demos).
- File-based SourceProvider implementations (read freshness from a local
  file or directory).
- Simple Postgres freshness providers (read last-update timestamps from a
  named table or query).
- A FastAPI reference application exposing the endpoints in section 14.
- A CLI reference command for resolving a TemporalContext from a shell.

The following are explicitly out of scope for the open-source core. They
may exist as private adapters, commercial integrations, or downstream
projects, but they must not be required by, or merged into, the
open-source core:

- Bloomberg adapters or Bloomberg-derived data.
- OMS or PMS integrations.
- Broker fill adapters.
- Proprietary data warehouse adapters.
- Internal fund accounting or fund administration systems.

This boundary protects the open-source core from depending on commercial
licenses and from leaking proprietary schemas.

## 16. README Seed Language

The following text is a seed for README.md. It may be copied and lightly
edited when README.md is created.

---

asof123

Every bug in finance software is secretly an "as of" bug.

In finance and institutional software, almost every hard bug eventually
turns out to be a disagreement about "as of". One service uses wall-clock
now. Another uses the prior business close. A preview screen quietly
mixes in live prices. A replay job sees data that did not exist on the
date being replayed. Each team writes its own ad hoc rules for business
date, market phase, freshness, and publication. The rules drift, and the
bugs are blamed on data quality.

asof123 is a temporal semantics layer. It does not tell you what time it
is. It tells you what "as of" means in a given call: which business date,
which market phase, which perspective (preview, live, executed,
canonical, replay, historical), which sources are fresh or stale or not
yet published, and which knowledge cutoff and price basis apply. External
systems report facts. asof123 resolves temporal meaning.

Example of a resolved TemporalContext:

    {
      "resolved_at_utc": "2026-05-12T18:30:00Z",
      "perspective": "LIVE",
      "market": "XNYS",
      "market_timezone": "America/New_York",
      "business_date": "2026-05-12",
      "market_phase": "MARKET_OPEN",
      "knowledge_cutoff_utc": "2026-05-12T18:30:00Z",
      "price_basis": "LAST_TRADE",
      "publication_state": "PUBLISHED",
      "canonical_state": "PROVISIONAL",
      "sources": {
        "equities_quotes": {
          "freshness": "FRESH",
          "last_update_utc": "2026-05-12T18:29:58Z"
        },
        "corporate_actions": {
          "freshness": "PRIOR_CLOSE",
          "last_update_utc": "2026-05-11T21:05:00Z"
        }
      }
    }

---

## 17. Coding Discipline

- No code is written in this pass.
- No application scaffolding is created in this pass.
- The only artifact produced in this pass is this PRODUCT_CONTRACT.md and
  an accompanying short report under docs/.
- All documents use plain ASCII punctuation only. No smart quotes, em
  dashes, ellipses, or other non-ASCII typography.
- The contract must remain direct, concrete, and implementation-guiding.
  It is a working specification, not marketing copy.
- Future changes to this contract must be made by editing this file, not
  by adding parallel documents that quietly disagree with it.
