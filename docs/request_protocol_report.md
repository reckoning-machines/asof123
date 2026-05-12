# Request and Protocol Layer Report

## Files Created or Updated

Created:
- /Users/jedgore/dev/asof123/src/asof123/requests.py
- /Users/jedgore/dev/asof123/src/asof123/providers.py
- /Users/jedgore/dev/asof123/tests/test_requests.py
- /Users/jedgore/dev/asof123/tests/test_providers.py
- /Users/jedgore/dev/asof123/docs/request_protocol_report.md

Updated:
- /Users/jedgore/dev/asof123/src/asof123/__init__.py
  (added `ResolveRequest`, `SourceProvider`, `ProviderReportError` to
  the import block and to `__all__`; updated the module docstring to
  describe the new boundary; preserved all prior exports.)

No resolver, calendar, provider implementation, FastAPI app, CLI,
persistence, scheduler, async, or orchestration code was added. This is
still a types / protocols pass.

## ResolveRequest Semantics Implemented

`ResolveRequest` is a Pydantic v2 model with `extra="forbid"`. It carries
five fields:

- `perspective: Perspective` (required)
- `market: str` (required, uppercase, non-empty)
- `market_timezone: str` (required, IANA Region/City or `UTC`)
- `as_of_utc: datetime | None`
- `knowledge_cutoff_utc: datetime | None`

The shared field validators reuse the helpers defined in `models.py`
(`_require_utc`, `_require_iana_region_city`,
`_require_uppercase_market`) so the request layer and the response
layer cannot disagree about what a valid market or UTC instant is.
Reuse is by direct import; the validators are not duplicated.

Per-Perspective cross-field rules, enforced in `mode="after"` model
validation:

- `REPLAY` and `HISTORICAL` require both `as_of_utc` and
  `knowledge_cutoff_utc`. Either one missing raises a validation error
  that names the perspective.
- `LIVE` forbids both `as_of_utc` and `knowledge_cutoff_utc`. LIVE
  resolves to the current instant by definition; a caller that wants a
  past instant should use REPLAY or HISTORICAL.
- `PREVIEW` and `PRE_TRADE_INTENT` may omit `as_of_utc` and may supply
  `knowledge_cutoff_utc`. Neither is required.
- `CANONICAL` may supply `knowledge_cutoff_utc` but must not supply
  `as_of_utc`. CANONICAL resolves against the system of record's
  publication, not an arbitrary past instant.
- `EXECUTED` permits both `as_of_utc` and `knowledge_cutoff_utc` to be
  supplied or omitted.

Cross-field invariant independent of perspective:

- If both `as_of_utc` and `knowledge_cutoff_utc` are supplied,
  `knowledge_cutoff_utc <= as_of_utc`. A request that knows about
  data from after the instant it is supposed to be reporting on is a
  knowledge leak and is rejected per PRODUCT_CONTRACT.md section 13.

Every cross-field error message names the offending perspective and/or
field and points back at the relevant section of PRODUCT_CONTRACT.md
(section 4 for perspective semantics, section 13 for the fail-closed
rule).

## Protocol Decisions

`providers.py` defines two symbols and nothing else:

- `ProviderReportError`, a plain `Exception` subclass. Providers raise
  it when they prefer to fail closed rather than guess. The docstring
  describes how a future resolver layer will translate it into a
  `SourceStatus` carrying `SourceFreshness.FAILED` with `reason_code`
  and `explanation`.
- `SourceProvider`, a `typing.Protocol` marked `@runtime_checkable`,
  with two members:
  - `name: str`
  - `report(now_utc: datetime) -> SourceStatus`

Decisions:

- Used `Protocol`, not `ABC` or a base class. The contract says
  providers report facts and nothing else. A `Protocol` expresses that
  structurally without inheriting state, helpers, or default methods
  that providers could lean on to grow scope.
- Marked `@runtime_checkable` so tests can assert
  `isinstance(provider, SourceProvider)`. The runtime check is
  attribute-based (`hasattr` for `name`, `hasattr` plus callability for
  `report`), which is the cheapest way to reject obvious non-providers
  (a dict, an object with only `name`, etc.) without enforcing nominal
  inheritance.
- The `report` signature takes a UTC-aware `datetime` named `now_utc`.
  The contract requires UTC for all machine instants
  (PRODUCT_CONTRACT.md section 12); the parameter name documents that
  expectation at the call site. The protocol does not type-validate the
  datetime; that is the resolver's responsibility before it hands the
  datetime to a provider.
- No implementations, no base classes, no ABCs, no network code, no
  database code ship in this module. The open-source provider
  implementations promised in PRODUCT_CONTRACT.md section 15 (static
  fixture, file-based, simple Postgres freshness) live in separate
  future modules.

## Validation Rules Implemented

Shared field validators (imported from `models.py`):

- `as_of_utc`, `knowledge_cutoff_utc`: must be timezone-aware and have a
  UTC offset of exactly `+00:00`. Naive datetimes and non-UTC tz-aware
  datetimes both raise validation errors.
- `market_timezone`: must contain `/` or equal `"UTC"`, and must resolve
  via `zoneinfo.ZoneInfo`. Abbreviations like `EST`, `PST`, and
  `EST5EDT` are rejected.
- `market`: must be a non-empty string equal to its `.upper()`.

Request-only rules (model validator, `mode="after"`):

- REPLAY, HISTORICAL: both UTC fields required.
- LIVE: both UTC fields forbidden.
- CANONICAL: `as_of_utc` forbidden, `knowledge_cutoff_utc` allowed.
- PREVIEW, PRE_TRADE_INTENT, EXECUTED: no extra cross-field rejection.
- `knowledge_cutoff_utc <= as_of_utc` when both present.

Schema-shape rule:

- `model_config = ConfigDict(extra="forbid")`. Unknown fields raise a
  validation error so the request schema cannot drift silently.

## Tests Added

`tests/test_requests.py` (20 tests):

Happy paths:
- LIVE with no UTC fields
- REPLAY with both UTC fields
- HISTORICAL with both UTC fields
- PREVIEW with only `knowledge_cutoff_utc`
- PRE_TRADE_INTENT with only `knowledge_cutoff_utc`
- EXECUTED with both UTC fields
- CANONICAL with only `knowledge_cutoff_utc`

Failures:
- LIVE with `as_of_utc`
- LIVE with `knowledge_cutoff_utc`
- REPLAY without `as_of_utc`
- REPLAY without `knowledge_cutoff_utc`
- HISTORICAL with neither UTC field
- CANONICAL with `as_of_utc`
- naive datetime in `as_of_utc`
- non-UTC tz-aware datetime in `as_of_utc`
- `EST` as `market_timezone`
- lowercase `market`
- `knowledge_cutoff_utc > as_of_utc`
- extra unknown field

Boundary case:
- `knowledge_cutoff_utc == as_of_utc` is accepted (the rule is `<=`,
  not `<`).

`tests/test_providers.py` (7 tests):
- `isinstance(fake_provider, SourceProvider)` is true via
  `runtime_checkable`.
- `fake_provider.report(UTC_NOW)` returns a `SourceStatus` with the
  expected provider name, freshness, and last_update_utc.
- `ProviderReportError` is an `Exception` subclass.
- `ProviderReportError` is raisable and catchable with a message match.
- The fake provider's own constructor rejects an empty `name`. This is
  an example of provider-side discipline, not a protocol-level rule.
- A `dict` is not a `SourceProvider` (sanity check on
  `runtime_checkable`).
- An object with only `name` (no `report`) is not a `SourceProvider`.

The fake provider is defined inline in the test module on purpose. The
package itself ships zero provider implementations per
PRODUCT_CONTRACT.md sections 12 and 15.

Total project test count: 63 passed (36 prior plus 27 new).

## Validation Commands Run

1. `python -m py_compile src/asof123/__init__.py
   src/asof123/requests.py src/asof123/providers.py
   tests/test_requests.py tests/test_providers.py`
   Result: clean.

2. `python -m pytest -q`
   Result: 63 passed in 0.06s.

3. `LC_ALL=C grep -rnP '[^\x00-\x7F]' src/asof123/__init__.py
   src/asof123/requests.py src/asof123/providers.py
   tests/test_requests.py tests/test_providers.py`
   Result: no matches (exit 1).

4. `git diff --check`
   Result: clean (exit 0).

## Assumptions Made

- `ResolveRequest` reuses the private helpers
  `_require_utc`, `_require_iana_region_city`,
  `_require_uppercase_market` from `models.py` by direct import.
  Cross-module use of underscored helpers is conventionally discouraged,
  but the alternatives were worse: duplicating the helpers risks drift
  between the request and response layers, and promoting them to a
  separate internal module is a larger refactor for no behavioral gain.
  If a third caller needs these helpers, a future pass should extract
  them into `src/asof123/_validators.py` and re-export from `models.py`.
- `LIVE` is interpreted strictly: it forbids both `as_of_utc` and
  `knowledge_cutoff_utc`. The contract says LIVE is a real-time
  operational read; allowing either field would let callers smuggle in
  replay semantics under a LIVE label. If a future use case argues for
  LIVE with a `knowledge_cutoff_utc`, that is a contract change, not a
  resolver change.
- `CANONICAL` is interpreted as: caller asks the system of record what
  its latest canonical answer is. Allowing `knowledge_cutoff_utc` (but
  not `as_of_utc`) makes the request semantically equivalent to "the
  canonical view as of the most recent canonical publication, ignoring
  any later data". If a use case appears for "canonical as of a past
  business date", it is a separate perspective, not a CANONICAL
  variant.
- The `SourceProvider` protocol does not yet declare `__hash__` or
  equality semantics. Providers are identified by `name`. If providers
  need to be deduplicated by identity in a future resolver, that will
  be a registry-layer decision, not a protocol change.

## Recommended Next Step

The boundary is now: enums, models, request, and provider protocol.
The next pass should implement the smallest possible end-to-end slice
of the resolver, without introducing scheduling, persistence, or
external IO. In order:

1. Create `src/asof123/calendar.py` with a `MarketCalendar` Protocol
   exposing:
   - `market: str`, `market_timezone: str`
   - `business_date_for(now_utc) -> date`
   - `market_phase_for(now_utc) -> MarketPhase`
   No implementations yet; this is another protocol pass.
2. Create `src/asof123/calendars/xnys.py` with a single concrete
   reference calendar for XNYS / America/New_York. Hard-coded session
   boundaries are acceptable for the first pass; holidays and early
   closes can be a list constant. This is the first concrete
   implementation in the repo and should be kept deliberately small.
3. Create `src/asof123/resolver.py` exposing
   `resolve(request: ResolveRequest, calendars, providers) ->
   TemporalContext`. The resolver:
   - rejects requests whose `market` has no matching calendar
     (fail-closed per PRODUCT_CONTRACT.md section 13)
   - calls each provider's `report(now_utc)` and assembles the
     `sources` dict
   - translates `ProviderReportError` into a `SourceStatus` with
     `SourceFreshness.FAILED`, `reason_code`, and `explanation`
   - applies the fail-closed bindings already enforced by
     `TemporalContext`'s model validator
4. Add tests covering: missing calendar, provider raising
   `ProviderReportError`, a happy-path LIVE resolve, and a happy-path
   REPLAY resolve.

Still out of scope for the next pass: FastAPI, CLI, snapshot
persistence, scheduling, async, retries, and any non-static / non-file
provider implementations.
