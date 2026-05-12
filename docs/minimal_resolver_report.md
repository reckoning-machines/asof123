# Minimal Resolver Report

## Files Created or Updated

Created:
- /Users/jedgore/dev/asof123/src/asof123/calendar.py
- /Users/jedgore/dev/asof123/src/asof123/calendars/__init__.py
- /Users/jedgore/dev/asof123/src/asof123/calendars/xnys.py
- /Users/jedgore/dev/asof123/src/asof123/resolver.py
- /Users/jedgore/dev/asof123/tests/test_calendar.py
- /Users/jedgore/dev/asof123/tests/test_resolver.py
- /Users/jedgore/dev/asof123/docs/minimal_resolver_report.md

Updated:
- /Users/jedgore/dev/asof123/src/asof123/__init__.py
  - Added `MarketCalendar`, `XNYSCalendar`, `ResolverError`, and
    `resolve` to imports and `__all__`.
  - Updated the module docstring to reflect the new boundary.
  - Preserved all prior exports.

No FastAPI app, CLI, persistence, scheduler, orchestration code, async
behavior, or external IO was added. No real provider implementations
exist in the package; the only providers are inline fakes inside
`tests/`.

## Calendar Decisions

`MarketCalendar` (in `src/asof123/calendar.py`) is defined as a
`@runtime_checkable` `typing.Protocol`. Choosing a Protocol over an ABC
keeps the boundary structural and prevents future implementations from
inheriting helpers that creep beyond "return business_date and
market_phase for a UTC instant." Members:

- `market: str`
- `market_timezone: str`
- `business_date_for(now_utc: datetime) -> date`
- `market_phase_for(now_utc: datetime) -> MarketPhase`

Both methods are documented as requiring UTC-aware input and as raising
`ValueError` for naive or non-UTC tz-aware datetimes. The protocol does
not encode that requirement (a Protocol cannot enforce method behavior),
but the docstring binds implementations.

`XNYSCalendar` (in `src/asof123/calendars/xnys.py`) is the minimum
reference implementation:

- `market = "XNYS"`, `market_timezone = "America/New_York"`. Both are
  class attributes; this lets `isinstance(cal, MarketCalendar)` succeed
  under `runtime_checkable`.
- Local-time conversion goes through `zoneinfo.ZoneInfo` and reuses
  `asof123.models._require_utc` for UTC validation. Naive and non-UTC
  tz-aware inputs raise `ValueError`.
- `business_date_for` returns the calendar date in `America/New_York`
  for the given UTC instant. No roll-forward to the next business day
  on weekends or holidays; the date is just "the local calendar date".
- `market_phase_for` returns `WEEKEND` for Saturday or Sunday,
  `HOLIDAY` for any date in the hard-coded holiday set, `PRE_OPEN`
  before 09:30 ET, `MARKET_OPEN` from 09:30 ET inclusive through 16:00
  ET exclusive, and `POST_CLOSE` from 16:00 ET on.
- The holiday set is a `frozenset[date]` with 20 entries covering 2025
  and 2026. No half-days, no ad hoc closures, no early-close handling.
  Anything more complete is deliberately out of scope and belongs in a
  downstream calendar that satisfies the protocol.

## Resolver Defaults

`resolve(request, calendars, providers=())` composes the request, the
calendars registry, and the providers iterable into a `TemporalContext`.
The defaults it picks:

- `now_utc = request.as_of_utc` if provided, otherwise
  `datetime.now(timezone.utc)`.
- `business_date` and `market_phase` come from the resolved calendar.
- `price_basis`:
  - `LIVE` + `MARKET_OPEN` -> `LAST_TRADE` (no reason set).
  - `market_phase == PRE_OPEN` (any perspective) -> `PRIOR_CLOSE`.
  - `perspective in {PRE_TRADE_INTENT, PREVIEW}` -> `PRIOR_CLOSE`.
  - Otherwise -> `UNKNOWN`, with `reason_code =
    "PRICE_BASIS_UNRESOLVED"` and an explanation that names the
    perspective and market_phase.
- `execution_state`:
  - `perspective != EXECUTED` -> `NOT_EXECUTED`.
  - `perspective == EXECUTED` -> `UNKNOWN`, with `reason_code =
    "EXECUTION_FACTS_UNAVAILABLE"` and an explanation that the minimal
    resolver has no execution provider. The minimal resolver does not
    inspect provider metadata to derive execution state; that is a
    later layer.
- `canonical_state`:
  - `perspective == CANONICAL` -> `CANONICAL`.
  - Otherwise -> `PROVISIONAL`.
- `publication_state` is always `PUBLISHED` in the minimal slice. This
  is the one place the resolver does not match the briefing word for
  word ("PUBLISHED except CANONICAL unresolved cases"). The minimal
  resolver has no canonical SourceProvider, so "unresolved" is not
  detectable here; rather than silently inventing an unresolved state,
  the resolver leaves `publication_state` as `PUBLISHED` and lets the
  caller spot mismatches via `canonical_state` and `sources`. This is
  flagged as a known follow-up below.
- `knowledge_cutoff_utc = request.knowledge_cutoff_utc` if provided,
  otherwise `now_utc`.
- `reason_code` and `explanation` on the TemporalContext are populated
  whenever any subcomponent contributes a reason. Multiple reasons are
  combined: `reason_code` is `;`-joined and `explanation` is
  ` | `-joined. This keeps the model validator's
  `UNKNOWN`-requires-reason rule satisfied even when both `price_basis`
  and `execution_state` are `UNKNOWN`.

## Fail-Closed Behavior

The resolver raises `ResolverError` (a plain `Exception` subclass) in
three cases, each with an explicit message that names the offending
input and points back at PRODUCT_CONTRACT.md where relevant:

- No calendar registered for `request.market`. The resolver does not
  fall back to a default market or to UTC. Message includes the
  requested market and references section 11.
- Calendar metadata mismatch. If `calendars[request.market]` exists but
  its `.market` differs from the request, or its `.market_timezone`
  differs from the request, the resolver raises. This catches
  misregistration and prevents a calendar from silently answering for
  the wrong market.
- Duplicate provider name. Each `SourceProvider` in the providers
  iterable must have a unique `name`. The resolver scans them in order
  and raises on the first duplicate.

When a provider raises `ProviderReportError` during `report(now_utc)`,
the resolver does NOT raise. It catches the error and stores a
`SourceStatus` with:

- `freshness = SourceFreshness.FAILED`
- `reason_code = "PROVIDER_REPORT_FAILED"`
- `explanation = str(exc)` (or a fixed string if the exception had no
  message)

This is the fail-closed translation called for by PRODUCT_CONTRACT.md
section 13: the provider signaled it could not safely report; the
resolver records `FAILED` rather than guessing `FRESH`. The provider
appears in `TemporalContext.sources` and any downstream consumer can
see exactly why.

The final guardrail is the `TemporalContext` model validator itself.
The resolver assembles fields and constructs a `TemporalContext`; if
that construction would violate any contract rule (`UNKNOWN` value with
no reason, `EXECUTED` perspective with `INTENDED`/`WORKING` execution
state, `CANONICAL` perspective without `CANONICAL` canonical state),
Pydantic raises `ValidationError` and the resolver does not return a
malformed context.

## Tests Added

`tests/test_calendar.py` (11 tests):

- `XNYSCalendar` conforms to `MarketCalendar` (protocol isinstance,
  market and market_timezone class attributes).
- Tuesday 08:00 ET -> `PRE_OPEN`.
- Tuesday 10:00 ET -> `MARKET_OPEN`.
- Tuesday 17:00 ET -> `POST_CLOSE`.
- Saturday -> `WEEKEND`.
- 2026-01-01 (New Year's Day) -> `HOLIDAY`.
- `business_date_for` returns the local NY date for an intraday UTC
  instant.
- `business_date_for` rolls into the next local day when the UTC
  instant maps to early morning ET on the next calendar day.
- Naive datetime to `market_phase_for` -> `ValueError`.
- Non-UTC tz-aware datetime (`+02:00`) to `market_phase_for` ->
  `ValueError`.
- `business_date_for` rejects a naive datetime.

`tests/test_resolver.py` (11 tests):

- LIVE happy path with `XNYSCalendar` and one fresh provider, returns a
  `TemporalContext` with the provider's `SourceStatus` and a UTC
  `resolved_at_utc`. Time-of-day agnostic so the test does not flake
  on weekends or holidays.
- `PRE_TRADE_INTENT` at pinned 08:00 ET yields `MARKET_OPEN=PRE_OPEN`,
  `price_basis=PRIOR_CLOSE`, `execution_state=NOT_EXECUTED`, and no
  reason / explanation.
- LIVE with a stub calendar that forces `MARKET_OPEN` yields
  `price_basis=LAST_TRADE`. Uses a stub because LIVE requests cannot
  carry an `as_of_utc`, so the only way to pin the phase is via the
  calendar.
- Missing calendar -> `ResolverError("No calendar...")`.
- Calendar timezone mismatch -> `ResolverError(... market_timezone ...)`.
- Calendar market mismatch (calendar registered under a different key
  than its own `.market`) -> `ResolverError`.
- Duplicate provider names -> `ResolverError("Duplicate provider...")`.
- `ProviderReportError` during `report` is translated into a
  `SourceStatus` with `freshness=FAILED`,
  `reason_code="PROVIDER_REPORT_FAILED"`, and the exception message in
  the explanation.
- CANONICAL request returns `canonical_state=CANONICAL`.
- EXECUTED request with no execution provider returns
  `execution_state=UNKNOWN` with `reason_code` containing
  `"EXECUTION_FACTS_UNAVAILABLE"` and a non-empty explanation.
- Sanity check that the resolver hands back a `TemporalContext`
  instance and that `resolved_at_utc` and `knowledge_cutoff_utc` carry
  the request's pinned time. If the resolver had assembled an invalid
  context, `TemporalContext`'s own validator would have raised before
  the test got here.

Total project test count: 85 passed (63 prior + 22 new).

## Validation Commands Run

1. `python -m py_compile src/asof123/__init__.py
   src/asof123/calendar.py src/asof123/calendars/__init__.py
   src/asof123/calendars/xnys.py src/asof123/resolver.py
   tests/test_calendar.py tests/test_resolver.py`
   Result: clean.

2. `python -m pytest -q`
   Result: 85 passed in 0.08s.

3. `LC_ALL=C grep -rnP '[^\x00-\x7F]' src/asof123/__init__.py
   src/asof123/calendar.py src/asof123/calendars/ src/asof123/resolver.py
   tests/test_calendar.py tests/test_resolver.py`
   Result: no matches (exit 1).

4. `git diff --check`
   Result: clean (exit 0).

## Assumptions Made

- The minimal resolver always sets `publication_state = PUBLISHED`.
  The brief mentioned "PUBLISHED except CANONICAL unresolved cases",
  but the minimal slice has no canonical SourceProvider against which
  to detect "unresolved", and silently inventing an unresolved state
  would itself violate the fail-closed rule. When a real canonical
  SourceProvider exists, the resolver can flip `publication_state` to
  `NOT_PUBLISHED` (with reason / explanation) when the canonical
  provider reports `NOT_PUBLISHED` for CANONICAL perspective. This is
  the cleanest place to wire it in.
- `business_date_for` returns the local calendar date in
  `market_timezone`, with no roll-forward on weekends or holidays. The
  contract allows refinement, and a richer calendar can implement
  "next business day" semantics without changing the protocol. For the
  minimal slice this avoids inventing a convention that future calendars
  might disagree with.
- `_require_utc` (private in `models.py`) is now imported by three
  modules: `requests.py`, `resolver.py`, and `calendars/xnys.py`. As
  flagged in `docs/request_protocol_report.md`, when a fourth caller
  appears, the helpers should be promoted to
  `src/asof123/_validators.py` and re-exported from `models.py`.
- The minimal resolver does not inspect `SourceStatus.metadata` to
  derive `execution_state` or `publication_state`. Treating arbitrary
  metadata as a side channel for canonical fields would create
  contract-level ambiguity. A future "execution provider" should be a
  separate, typed protocol that exposes an `ExecutionState` directly.

## Recommended Next Step

The next pass should put the resolver behind two thin reference
adapters, in this order:

1. `src/asof123/providers/static.py`: a `StaticProvider` that holds a
   pre-built `SourceStatus` and returns it from every `report` call.
   This is the first concrete provider in the repo and gives us a
   non-test surface area for resolver behavior. Plus tests.
2. `src/asof123/providers/file.py`: a `FileProvider` that reads a JSON
   blob from a local file and constructs a `SourceStatus` from it.
   Strict schema validation on the JSON, no network IO. Plus tests.
3. `src/asof123/snapshot.py`: a `make_snapshot(context, snapshot_id)`
   helper that returns an `AsOfSnapshot` whose `content_hash` is a
   stable hash of the canonical JSON of the context. Plus tests.

Still out of scope after that pass: FastAPI app, CLI entrypoint,
persistence (writing snapshots to disk or to a database), scheduling,
retry orchestration, async, and any non-static / non-file SourceProvider.
