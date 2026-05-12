# README Initial Report

## Files Created

- /Users/jedgore/dev/asof123/README.md

This pass created the initial README only. No code, no package layout,
no FastAPI app, no CLI, no tests. The contract in `PRODUCT_CONTRACT.md`
remains the source of truth; the README defers to it explicitly.

## Key README Decisions

- Opened with the tagline and an immediate one-paragraph definition, so a
  reader who skims the top of the file already knows asof123 is a
  temporal semantics layer and not a clock, scheduler, or warehouse.
- Stated explicitly that `PRODUCT_CONTRACT.md` is canonical and that the
  README loses any conflict with it. This prevents the README from
  silently drifting into a parallel spec.
- Repeated the core principle in three places (intro, "What asof123 Is",
  and the problem section): "External systems report facts. asof123
  resolves temporal meaning." The repetition is intentional. It is the
  mental model that resolves most future scope arguments.
- Framed the problem in concrete, finance-native language (business date,
  market phase, freshness, publication state, preview vs executed,
  replay vs live, historical admissibility, knowledge cutoff, timezone
  interpretation) before introducing any of the library's own nouns.
- Kept the "What asof123 Is Not" section explicit and itemized, mirroring
  contract section 2. This is load-bearing: most of the value of the
  README is in what it refuses to be.
- Introduced the ontology as a brief readable section (TemporalContext,
  Perspective, MarketPhase, SourceProvider, SourceStatus,
  KnowledgeCutoff, AsOfSnapshot) and pointed at the contract for the
  full list (PriceBasis, ExecutionState, PublicationState, CanonicalState,
  BusinessDate, MarketCalendar). This keeps the README readable without
  duplicating the contract.
- Documented all 7 perspectives and all 6 market phases with one
  sentence each, and explicitly noted that CLOSED is the fail-safe
  default. This codifies the fail-closed rule in human-readable form.
- Added 5 concrete finance examples (pre-open dashboard using prior
  close, replay seeing future data, canonical publication not yet
  available, partial fills intraday, ETL OK but feed stale). Each
  example pairs the bug with the specific TemporalContext shape that
  prevents it. This is the section most likely to be read by skeptics.
- Used a single realistic JSON TemporalContext example pinned to XNYS /
  America/New_York at 2026-05-12T13:45:00Z, including a `NOT_PUBLISHED`
  source with an `expected_publication_utc`. Chosen to demonstrate UTC
  instants, IANA timezone, MIC for market identity, and the fail-closed
  story for an unpublished source in the same payload.
- Used a Python example whose call signature is illustrative
  (`resolve_asof(perspective=..., market=...)`) and whose body
  demonstrates centralizing semantic decisions in the resolver. The
  README explicitly says the signature is not the point; the
  centralization is.
- Restated the open-source boundary verbatim from the contract (in
  scope: timezones, basic calendars, NYSE/Nasdaq examples, static and
  file-based and simple Postgres providers, FastAPI reference, CLI; out
  of scope: Bloomberg, OMS/PMS, broker fills, internal warehouse,
  internal fund systems). Repeating this in the README, not just the
  contract, makes the boundary visible to first-time visitors and
  prospective contributors.
- Tone is technical, direct, and finance-native. No "revolutionary", no
  "AI-powered", no startup framing. The only first-person pronouns are
  in the examples, not in the marketing voice.
- Plain ASCII punctuation throughout, per contract section 12. No smart
  quotes, no em dashes, no ellipses.

## Assumptions Made

- The Python entrypoint will be named `resolve_asof` and live at the
  top level of the `asof123` package. This is illustrative, not yet
  binding; the package layout pass can change it, but if it does, the
  README example must change with it.
- `TemporalContext.execution_state` is exposed as a string-valued field
  carrying an `ExecutionState` value (for example `"NOT_EXECUTED"`).
  This is consistent with the contract's ontology but the specific
  string enumeration for ExecutionState is not yet locked in the
  contract; section 3 lists ExecutionState as a noun but does not pin
  its values. The README uses `"NOT_EXECUTED"` as a plausible member;
  the contract should be updated to lock the ExecutionState
  enumeration before code is written.
- `TemporalContext.sources` is exposed as a mapping from source name to
  a `SourceStatus`-shaped object with at least `provider`, `freshness`,
  and `last_update_utc` fields, plus optional metadata such as
  `expected_publication_utc`. This is consistent with the contract but
  is the README's first concrete shape for SourceStatus and should be
  ratified when the Pydantic models are written.
- Markets are identified by MIC (for example `XNYS`) paired with an
  explicit IANA timezone (for example `America/New_York`). The contract
  requires the IANA timezone; the MIC is the README's choice for market
  identity and should be locked in the contract or the models pass.
- `price_basis` values shown (`LAST_TRADE`, `PRIOR_CLOSE`) are
  illustrative. The contract names PriceBasis but does not yet pin its
  enumeration. These specific values should be locked before code is
  written.

## Suggested Next Implementation Step

Lock the remaining enumerations in `PRODUCT_CONTRACT.md` before any
code is written. Specifically:

1. Pin the `ExecutionState` values (the contract currently lists the
   noun and a parenthetical sketch; convert that sketch into a
   normative list, the same way Perspective, MarketPhase, and
   SourceFreshness are pinned).
2. Pin the `PriceBasis` values (`LAST_TRADE`, `PRIOR_CLOSE`,
   `INDICATIVE`, `OFFICIAL_CLOSE`, `SETTLEMENT`, etc.) as a normative
   list.
3. Pin the `PublicationState` values (`NOT_PUBLISHED`, `PRE_PUBLISHED`,
   `PUBLISHED`, `EMBARGOED`, `WITHDRAWN`) as a normative list.
4. Pin the `CanonicalState` values (for example `PROVISIONAL`,
   `CANONICAL`, `SUPERSEDED`) as a normative list.
5. Decide and document how a market is identified in API requests
   (MIC, internal calendar name, or both).

After those enumerations are locked, the next pass is the Python package
skeleton: empty modules whose names mirror the ontology, plus Pydantic
models for TemporalContext, SourceStatus, and AsOfSnapshot with strict
UTC and IANA-timezone validation. That is the smallest unit of code that
turns the contract into something the rest of the project can import.

No FastAPI app, no CLI, no providers, and no resolver logic should be
written before the enumerations are locked and the models compile.
