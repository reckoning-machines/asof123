# Snapshot Replay Determinism Audit

Date: 2026-05-15

Scope: standalone asof123 snapshot and replay determinism only. This was not
a fin123 integration audit and did not add persistence, schedulers,
background jobs, databases, external integrations, or proprietary adapters.

`docs/unified_diff.md` does not exist and was not created.

## Snapshot Determinism Findings

Current snapshot hashing is deterministic over semantic content:

- `canonicalize_context()` uses `context.model_dump(mode="json")` followed
  by `json.dumps(..., sort_keys=True, separators=(",", ":"))`.
- `canonicalize_snapshot_payload()` wraps that context in explicit
  `snapshot_schema_version` and `semantic_contract_version` fields before
  hashing.
- Enum members serialize to their pinned string values.
- UTC datetimes serialize through Pydantic JSON mode.
- Source ordering and nested metadata key ordering do not affect the
  `content_hash`.
- Optional and null fields are included in the dumped model, so
  `reason_code`, `explanation`, and UNKNOWN-related fields are part of the
  canonical payload.
- Semantically different source freshness values produce different hashes.

Two determinism hazards were found and fixed:

- `make_snapshot()` previously embedded the caller's original
  `TemporalContext` object. A later mutation of that object could change the
  snapshot payload after `content_hash` had been computed. `make_snapshot()`
  now embeds a validated copy.
- `SourceStatus.metadata` previously accepted arbitrary `Any` values. Sets,
  NaN, Infinity, or arbitrary Python objects could make canonical JSON
  ambiguous or non-deterministic. Metadata now accepts only deterministic
  JSON-compatible values, rejects non-finite floats and arbitrary objects,
  freezes mappings, and converts lists to tuples after validation.

The models involved in snapshots are now frozen after validation:
`SourceStatus`, `TemporalContext`, and `AsOfSnapshot`.

## Replay Safety Findings

REPLAY and HISTORICAL request semantics are constrained before resolver
execution:

- Both require `as_of_utc`.
- Both require `knowledge_cutoff_utc`.
- Both reject non-UTC and naive datetimes.
- Both reject `knowledge_cutoff_utc > as_of_utc`.

The resolver uses `datetime.now(timezone.utc)` only when the request allows
current-context behavior. REPLAY and HISTORICAL cannot reach that path
because their request validation requires pinned UTC instants.

There is no replay engine yet, so no code currently rehydrates an
`AsOfSnapshot` and re-resolves external provider state. That is safe for the
current repository. Future replay code must not call live providers or
current calendars without explicit version/freeze metadata.

## Calendar Determinism Findings

XNYS calendar behavior is deterministic for the same UTC instant:

- Inputs must be UTC-aware and offset zero.
- Conversion goes through `ZoneInfo("America/New_York")`.
- Weekends are pinned by weekday.
- The hard-coded 2025-2026 holiday set is deterministic.
- Regular pre-open/open/post-close session boundaries are fixed at 09:30 and
  16:00 market local time.
- DST spring-forward and fall-back adjacent trading days are now covered by
  tests.

Warnings:

- Full exchange calendars, early closes, half-days, ad hoc closures, and
  post-2026 holidays are intentionally not modeled. This is documented, but
  future replay safety requires calendar identity/version metadata before
  richer calendars are used to reinterpret historical snapshots.
- Timezone database behavior is external to the repo. For historical replay,
  future persisted snapshots should record enough timezone/calendar version
  metadata to prevent silent reinterpretation after tzdata changes.

## Provider Determinism Findings

Provider behavior is currently bounded:

- Duplicate provider names fail closed before source statuses are assembled.
- `ProviderReportError` becomes a stable `FAILED` `SourceStatus` with
  `reason_code=PROVIDER_REPORT_FAILED`.
- Source status dictionaries are sorted during canonical serialization, so
  provider iteration order does not change snapshot hashes.
- `StaticProvider` returns an immutable `SourceStatus`.
- `FileProvider` re-reads its file on each call; that is acceptable for
  current/live resolution, but future replay must not read mutable files as
  historical truth unless the file content/version is pinned in the replay
  input.

Provider metadata is now validated and frozen to prevent non-deterministic
payloads from entering snapshot hashes.

## Semantic Drift Findings

Current enum behavior is pinned by tests and string values. Invalid
enum-like strings are rejected by Pydantic.

Remaining drift risks are future-facing:

- Adding enum values can change downstream interpretation even if old values
  remain valid.
- Adding a canonical authority can change CANONICAL behavior from fail-closed
  to resolved; that boundary must be typed and explicitly asserted.
- Adding richer calendars can alter historical market phases unless calendar
  identity and version are captured.
- Adding snapshot schema fields can change hashes unless schema evolution is
  explicit.

No current runtime path silently reinterprets REPLAY/HISTORICAL requests
using wall-clock state.

## Future Replay Risk Analysis

Future architectural danger zones:

- Canonical authority introduction: must include an explicit authority id,
  assertion instant, publication state, and failure semantics. The resolver
  must not infer canonical state from generic source metadata.
- Persistence layer introduction: must store the full snapshot payload,
  content hash, schema version, semantic version, and calendar/provider
  version metadata. It must not recompute historical meaning from live state
  without an explicit replay mode.
- Provider expansion: providers must continue to report facts only. They
  must not infer perspectives, market phases, execution states, or canonical
  state unless a future typed protocol explicitly owns that fact.
- Mutable calendars: calendar implementations must be versioned or frozen for
  replay. A changed holiday table must not silently alter old snapshots.
- Snapshot schema evolution: every hash-affecting field addition/removal must
  be schema-versioned. Old snapshots need deterministic interpretation under
  the schema that produced them.
- Enum evolution: enum additions require contract changes and tests. Enum
  renames, merges, or semantic reuse must be prohibited for replayed data.
- Timezone database drift: historical conversions can change if tzdata rules
  change. Long-lived replay artifacts need timezone/calendar version pins or
  a canonical calendar publication artifact.

## Required Future Invariants

Future replay-safe implementations must preserve these invariants:

- Snapshot payloads are immutable after creation.
- Snapshot hashes are computed from deterministic, JSON-compatible semantic
  content only.
- Snapshot schema version is explicit before persistent snapshots are
  introduced. This is now defined as `asof123.snapshot.v1`.
- Calendar identity and calendar version are explicit before replay depends
  on richer calendar rules.
- Provider identity and provider data version are explicit before replay
  depends on provider-reported facts.
- Timezone/calendar interpretation used for a replay must be the same
  interpretation used when the snapshot was captured, unless the caller
  explicitly requests reinterpretation.
- REPLAY and HISTORICAL must never substitute wall-clock now for missing
  `as_of_utc` or `knowledge_cutoff_utc`.
- CANONICAL must remain fail-closed until a typed canonical authority can
  assert canonical state.

## HOLD / WARNING / NOTE Table

| Level | Finding | Status |
| --- | --- | --- |
| NOTE | Snapshot schema and semantic contract versions are explicit in the v1 hash payload. | Current hardening is complete; migration support is still future work. |
| WARNING | Richer market calendars will need calendar identity/version metadata to avoid historical reinterpretation. | Future risk; current XNYS calendar is deterministic and limited. |
| WARNING | Provider expansion will need provider/version pins for replay. | Future risk; current providers are static/file only and bounded. |
| WARNING | Timezone database drift can alter historical market interpretation over long horizons. | Future risk; current examples/tests are pinned but no tzdata version is recorded. |
| NOTE | `captured_at_utc` changes on each snapshot. | Expected audit field; `content_hash` excludes it and remains deterministic over the versioned snapshot payload. |
| NOTE | CANONICAL currently fails closed. | Safe until canonical authority is introduced. |

## Recommended Next Hardening Step

The next hardening step should be calendar/provider/tzdata freeze metadata.
The snapshot schema/version contract now exists, but persisted replay still
must not be added until calendar and provider version pins are defined.

## Validation Results

Commands run:

- `python -m pytest tests/test_models.py tests/test_snapshot.py tests/test_calendar.py -q`
- `python -m pytest -q`
- `rg -n "datetime\\.now|utcnow|random|uuid|hash\\(|sort_keys|timezone|ZoneInfo|fallback|default" src tests examples README.md PRODUCT_CONTRACT.md docs`
- `git diff --check`
- `LC_ALL=C rg -n "[^\\x00-\\x7F]" --glob '*.md'`

Results:

- Targeted snapshot/replay/calendar/model tests passed: 56 passed.
- Full test suite passed: 158 passed.
- Targeted grep found expected `datetime.now(timezone.utc)` use only in
  current-context and snapshot capture paths; no `utcnow`, `random`, `uuid`,
  or Python `hash()` use in runtime snapshot logic.
- `sort_keys=True` is used for canonical JSON and CLI/example output.
- `ZoneInfo` usage is explicit and limited to timezone validation and XNYS
  market conversion.
- `git diff --check` passed.
- Markdown ASCII check passed with no matches.

## Final Verdict

PASS WITH WARNINGS.

Current snapshot and replay-adjacent behavior is deterministic after the
narrow fixes in this audit. The warnings are future replay invariants that
must be addressed before persistence, richer calendars, provider expansion,
or replay execution are added.
