# Model Skeleton Report

## Files Created

- /Users/jedgore/dev/asof123/pyproject.toml
- /Users/jedgore/dev/asof123/src/asof123/__init__.py
- /Users/jedgore/dev/asof123/src/asof123/enums.py
- /Users/jedgore/dev/asof123/src/asof123/models.py
- /Users/jedgore/dev/asof123/tests/test_enums.py
- /Users/jedgore/dev/asof123/tests/test_models.py
- /Users/jedgore/dev/asof123/docs/model_skeleton_report.md

No resolver, provider, API, CLI, persistence, scheduler, or orchestration
code was created. This pass is types only.

## Enum Decisions

- One module, `asof123.enums`, holds every pinned enumeration. The set
  of values per enum is byte-for-byte the contract list (PRODUCT_CONTRACT.md
  sections 4 through 10). No values were added or omitted, and no aliases
  were introduced.
- Each enum is declared as `class X(str, Enum)`. This gives a string-valued
  enum whose members compare equal to their string names, which is what
  the JSON examples in `README.md` and the contract assume, and which is
  what Pydantic v2 accepts directly as field values.
- Each member's `.value` equals its `.name` (`"PREVIEW" == "PREVIEW"`),
  which is asserted by `test_enum_values_are_strings`. This blocks future
  drift where someone could change an enum's value to lowercase.
- Default constants live at module scope as `DEFAULT_*` bindings rather
  than as `Enum` class attributes. The contract requires defaults; binding
  them on the class would corrupt the enum (extra members would appear in
  iteration). The bindings are:
  - `DEFAULT_MARKET_PHASE = MarketPhase.CLOSED`
  - `DEFAULT_EXECUTION_STATE = ExecutionState.NOT_EXECUTED`
  - `DEFAULT_PRICE_BASIS = PriceBasis.UNKNOWN`
  - `DEFAULT_PUBLICATION_STATE = PublicationState.NOT_PUBLISHED`
  - `DEFAULT_CANONICAL_STATE = CanonicalState.PROVISIONAL`
- The two enums that overlap on `PRIOR_CLOSE` (`SourceFreshness` and
  `PriceBasis`) are intentionally kept separate. `SourceFreshness` is a
  property of a SourceProvider; `PriceBasis` is a property of the
  TemporalContext. The string happens to be identical but the type tags
  the meaning.

## Model Decisions

- `MarketIdentity`, `SourceStatus`, `TemporalContext`, and `AsOfSnapshot`
  are Pydantic v2 models. All use `ConfigDict(extra="forbid")` so the
  schemas are closed; extra fields cause validation errors, which protects
  the contract from silent shape drift.
- `MarketIdentity` is also `frozen=True`. Once a market identity has been
  resolved it should not be mutated on a TemporalContext in flight; this
  catches that class of bug at runtime.
- `SourceStatus` carries optional `provider`, datetime fields, `reason_code`,
  `explanation`, and a freeform `metadata: dict[str, Any]`. `metadata` is
  intentionally typed loose because SourceProviders are pluggable; the
  closed shape lives in the named fields.
- `TemporalContext` reproduces the JSON example in the contract:
  `resolved_at_utc`, `perspective`, `market`, `market_timezone`,
  `business_date`, `market_phase`, `knowledge_cutoff_utc`, `price_basis`,
  `execution_state` (default `NOT_EXECUTED`), `publication_state`,
  `canonical_state`, `sources`, and the optional `reason_code` /
  `explanation` pair used by fail-closed responses.
- `AsOfSnapshot` wraps a `TemporalContext` with `snapshot_id`,
  `captured_at_utc`, and optional `content_hash`. The snapshot intentionally
  embeds the full TemporalContext rather than referencing it by id, because
  the contract requires that snapshots be immutable and replay-safe.

## Validation Rules Implemented

UTC enforcement (`_require_utc`):
- `resolved_at_utc`, `knowledge_cutoff_utc`, `last_update_utc`,
  `expected_publication_utc`, and `captured_at_utc` are rejected if
  `tzinfo` is `None`, if `utcoffset()` is `None`, or if `utcoffset() !=
  timedelta(0)`. Naive datetimes and non-UTC tz-aware datetimes both
  fail.

IANA timezone enforcement (`_require_iana_region_city`):
- `market_timezone` must contain `/` (Region/City form) or equal `"UTC"`.
  Abbreviations like `EST`, `PST`, `MST`, `EST5EDT` are rejected.
- The value must resolve via `zoneinfo.ZoneInfo(name)`. Unknown names
  raise a `ValidationError`.

Market code enforcement (`_require_uppercase_market`):
- `market` must be a non-empty string equal to its `.upper()`. Empty,
  lowercase, or mixed-case values are rejected. The convention follows
  PRODUCT_CONTRACT.md section 11 (MIC-style codes such as `XNYS`).

Source dict enforcement (`_check_sources`):
- Every key in `TemporalContext.sources` must be a non-empty string.
  An empty source name is rejected.

Optional-string non-empty enforcement:
- `SourceStatus.provider`, `AsOfSnapshot.content_hash`: if present, must
  be non-empty.
- `AsOfSnapshot.snapshot_id`: always required and must be non-empty.

Fail-closed bindings (model_validator on TemporalContext):
- `perspective == CANONICAL` requires `canonical_state == CANONICAL`.
- `perspective == EXECUTED` forbids `execution_state` in
  `{INTENDED, WORKING}`.
- `price_basis == UNKNOWN` requires both `reason_code` and `explanation`.
- `publication_state == UNKNOWN` requires both `reason_code` and
  `explanation`.
- `canonical_state == UNKNOWN` requires both `reason_code` and
  `explanation`.

Every error message names the offending value and points at the relevant
section of PRODUCT_CONTRACT.md so future maintainers can trace back to
the contract.

## Tests Added

`tests/test_enums.py` (8 tests):
- one test per enum asserting the exact contract value set
- one test asserting all five default constants
- one test asserting that every enum member is a `str` and that
  `.value == .name`

`tests/test_models.py` (28 tests):
- happy path: valid TemporalContext for XNYS / America/New_York
- happy path: MarketIdentity for XNYS / America/New_York, and for
  XCRYPTO / UTC
- naive datetime rejected on TemporalContext.resolved_at_utc
- non-UTC tz-aware datetime rejected on TemporalContext.knowledge_cutoff_utc
- naive datetime rejected on SourceStatus.last_update_utc
- non-UTC tz-aware datetime rejected on SourceStatus.expected_publication_utc
- empty provider rejected on SourceStatus
- `EST` rejected as market_timezone
- unknown timezone (`America/Not_A_Place`) rejected
- lowercase market (`xnys`) rejected
- empty market rejected
- empty source key rejected in TemporalContext.sources
- CANONICAL perspective with PROVISIONAL canonical_state rejected
- CANONICAL perspective with CANONICAL canonical_state accepted
- EXECUTED perspective with INTENDED execution_state rejected
- EXECUTED perspective with WORKING execution_state rejected
- EXECUTED perspective with FILLED execution_state accepted
- UNKNOWN price_basis without reason and explanation rejected
- UNKNOWN price_basis with reason and explanation accepted
- UNKNOWN publication_state without reason and explanation rejected
- UNKNOWN canonical_state without reason and explanation rejected
- AsOfSnapshot happy path
- AsOfSnapshot rejects empty snapshot_id
- AsOfSnapshot rejects naive captured_at_utc
- AsOfSnapshot rejects non-UTC captured_at_utc
- AsOfSnapshot rejects empty content_hash

Total: 36 tests, all passing.

## Validation Commands Run

1. `python -m py_compile src/asof123/__init__.py src/asof123/enums.py
   src/asof123/models.py tests/test_enums.py tests/test_models.py`
   Result: clean.

2. `python -m pytest -q`
   Result: 36 passed in 0.06s.

3. `LC_ALL=C grep -rnP '[^\x00-\x7F]' pyproject.toml src/ tests/`
   Result: no matches (exit 1, meaning grep found nothing).

4. `git diff --check`
   Result: clean (exit 0).

## Assumptions Made

- The package is consumed via the src/ layout. `pyproject.toml` declares
  `pythonpath = ["src"]` under `[tool.pytest.ini_options]` so tests can
  run without an editable install. When the package is published it will
  be installed normally and the pythonpath shim becomes unnecessary.
- License is intentionally not declared in `pyproject.toml`. The
  previously written `docs/readme_initial_report.md` flagged the LICENSE
  decision as pending. This pass does not pick one; that is a separate
  decision to make before any public release.
- `zoneinfo.ZoneInfo` is the source of truth for "is this an IANA
  timezone". On Windows, the optional `tzdata` package is pulled in via a
  marker dependency. On macOS and Linux the system tz database is used.
- `UTC` is accepted as a market_timezone value. The contract requires
  IANA identifiers; `UTC` is an IANA identifier and is the right answer
  for venues that are genuinely UTC-based (for example crypto-style
  exchanges). Real equities markets must use Region/City form.

## Recommended Next Step

The contract now has executable types. The next pass should be the
resolver-input layer, not the resolver itself: define the request shape
that callers will use to ask for a TemporalContext, plus a thin
SourceProvider protocol that other modules can implement against. In
order:

1. Add `src/asof123/requests.py` with a Pydantic model
   `ResolveRequest`:
   - `perspective: Perspective`
   - `market: str`
   - `market_timezone: str`
   - `as_of_utc: datetime | None` (defaults to "now" only when the
     caller asks for it; LIVE callers may omit, REPLAY / HISTORICAL
     callers must supply)
   - `knowledge_cutoff_utc: datetime | None`
   - same UTC / IANA / uppercase-market validators as TemporalContext
   - cross-field rule: REPLAY and HISTORICAL must supply `as_of_utc` and
     `knowledge_cutoff_utc`; LIVE must not supply them
2. Add `src/asof123/providers.py` with an abstract `SourceProvider`
   protocol: `name`, `report(now_utc) -> SourceStatus`. No
   implementations yet, just the type.
3. Add tests for `ResolveRequest` covering each cross-field rule.
4. Only after that, write a minimal in-memory resolver and a `XNYS`
   reference MarketCalendar.

No FastAPI app, no CLI, no persistence, no scheduler should be added in
the next pass. The next pass is still types and small protocols.
