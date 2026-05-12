# Product Contract Report

## File Created

- /Users/jedgore/dev/asof123/PRODUCT_CONTRACT.md

This is the root-level canonical contract for the asof123 open-source
project. No code or scaffolding was added in this pass, per the contract's
own coding discipline rule (section 12).

## Key Decisions

- Framed asof123 as a "temporal semantics layer", not a clock, scheduler,
  orchestrator, warehouse, or temporal database. The negative scope in
  section 2 is as load-bearing as the positive scope in section 1.
- Adopted the core principle verbatim: external systems report facts,
  asof123 resolves temporal meaning. This is the line that should be used
  to settle future scope arguments.
- Locked the initial ontology (section 3) to a fixed set of nouns:
  TemporalContext, Perspective, MarketPhase, SourceStatus, SourceFreshness,
  KnowledgeCutoff, PriceBasis, ExecutionState, PublicationState,
  CanonicalState, BusinessDate, MarketCalendar, SourceProvider,
  AsOfSnapshot. These names are normative and must be used exactly in
  code, API, and docs.
- Locked the initial enumerations for Perspective (7 values), MarketPhase
  (6 values), and SourceFreshness (8 values). New values may be added
  later but existing names are not to be renamed, merged, or dropped
  without a contract change.
- Codified the UTC and timezone rule in section 7: UTC for all machine
  instants, explicit IANA timezone for all market-facing interpretation,
  no naive datetimes in public models or API responses. Conversions must
  go through a named MarketCalendar.
- Codified the fail-closed rule in section 8: unresolved temporal
  semantics must return an explicit failed or unresolved status with a
  reason code, never a silent guess and never a wall-clock fallback.
- Sketched the future HTTP surface (section 9): GET /asof/current,
  POST /asof/resolve, POST /sources/report, GET /sources/status, and
  POST /asof/snapshot. Endpoints are described but not implemented.
- Drew the open-source boundary (section 10): timezones, basic market
  calendars, NYSE/Nasdaq examples, static, file-based, and simple
  Postgres SourceProvider implementations, a FastAPI reference app, and
  a CLI are in scope. Bloomberg, OMS/PMS, broker fills, proprietary
  warehouses, and internal fund systems are explicitly out of scope for
  the open-source core.
- Included README seed language (section 11) with the tagline, a
  pain-paragraph, a what-it-does paragraph, and a small JSON example of
  a resolved TemporalContext keyed to America/New_York for US equities.
- Enforced plain ASCII punctuation throughout, per section 12.

## What Should Come Next

In rough priority order, the next passes should be:

1. Repository scaffolding: LICENSE (choose Apache-2.0 or MIT and commit to
   it before any code lands), README.md seeded from section 11,
   CONTRIBUTING.md that points back at PRODUCT_CONTRACT.md as the source
   of truth, and a .gitignore.
2. Python package skeleton: an `asof123/` package with empty modules that
   mirror the ontology in section 3 (for example `context.py`,
   `perspective.py`, `market_phase.py`, `source_status.py`,
   `calendar.py`, `snapshot.py`). No logic yet, just the type surface.
3. Pydantic (or dataclass) models for TemporalContext, SourceStatus, and
   AsOfSnapshot, with strict UTC and IANA-timezone validation as required
   by section 7. These are the first place the contract becomes
   executable.
4. A reference MarketCalendar for XNYS (NYSE) sufficient to compute
   BusinessDate and MarketPhase deterministically for a given UTC instant,
   with explicit handling of weekends, holidays, and early closes.
5. A minimal in-memory resolver that, given a request, returns a
   TemporalContext or a fail-closed error. This is the smallest end-to-end
   slice that proves the contract.
6. A FastAPI reference app exposing GET /asof/current and POST
   /asof/resolve against the in-memory resolver, plus a CLI command that
   prints a resolved TemporalContext to stdout.
7. SourceProvider implementations in this order: static fixture, file-
   based, simple Postgres freshness reader. Each must demonstrate the
   fail-closed rule when its backing source is missing or stale.
8. POST /sources/report, GET /sources/status, and POST /asof/snapshot,
   plus an AsOfSnapshot replay path that re-resolves a TemporalContext
   from a stored snapshot for audit and reproducibility.
9. A test suite that pins the enumerations and the fail-closed behavior,
   so future refactors cannot quietly weaken the contract.
10. Only after the open-source core is usable end-to-end, consider how
    private adapters (Bloomberg, OMS/PMS, internal warehouses) plug in
    from outside the core, per the boundary in section 10.
