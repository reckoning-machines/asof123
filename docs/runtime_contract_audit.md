# Runtime Contract Audit

Date: 2026-05-15

Scope: standalone asof123 runtime behavior only. This was not a fin123
integration audit and did not add persistence, schedulers, background jobs,
external integrations, proprietary adapters, or new product scope.

`docs/unified_diff.md` does not exist and was not created.

## Runtime Behavior Inventory

Implemented runtime surfaces audited:

- `ResolveRequest` request validation in `src/asof123/requests.py`.
- Pydantic ontology models in `src/asof123/models.py`.
- Pinned enums in `src/asof123/enums.py`.
- Minimal resolver in `src/asof123/resolver.py`.
- XNYS reference calendar in `src/asof123/calendars/xnys.py`.
- Source provider protocol, static provider, and file provider in
  `src/asof123/providers/`.
- Snapshot helper in `src/asof123/snapshot.py`.
- FastAPI reference app in `src/asof123/api.py`.
- CLI in `src/asof123/cli.py`.
- Examples under `examples/`.
- Runtime tests under `tests/`.

## Resolver Audit Findings

The resolver remains small and in-process: it accepts a validated
`ResolveRequest`, a caller-supplied calendar mapping, and caller-supplied
providers. It performs no IO, persistence, scheduling, orchestration,
background work, source-of-truth storage, or external integration.

One runtime contract violation was found and fixed:

- Before this audit, a `CANONICAL` request returned
  `canonical_state=CANONICAL` even though the minimal resolver has no
  modeled canonical authority or system-of-record provider. That violated
  the contract rule that CANONICAL is reserved for answers asserted by the
  system of record.
- The resolver now fails closed for `perspective=CANONICAL` with
  `ResolverError("CANONICAL_UNSUPPORTED: ...")`.
- Resolver, API, and CLI tests now pin that behavior.

Resolver fail-closed errors now include stable reason-code prefixes:

- `UNKNOWN_MARKET`
- `CALENDAR_MARKET_MISMATCH`
- `CALENDAR_TIMEZONE_MISMATCH`
- `DUPLICATE_PROVIDER_NAME`
- `CANONICAL_UNSUPPORTED`

Provider failures remain data-bearing rather than process-fatal:
`ProviderReportError` becomes a `SourceStatus` with `freshness=FAILED`,
`reason_code=PROVIDER_REPORT_FAILED`, and a human explanation.

## API Audit Findings

The FastAPI reference app exposes the documented reference surface. It keeps
calendars and providers in `app.state`, loads no environment config, opens no
database, schedules no work, and has no mutable source registry.

API behavior conforms after the resolver fix:

- Malformed request bodies fail with FastAPI/Pydantic 422 responses.
- Unknown market and other resolver failures fail with HTTP 400 and
  `{"error": "RESOLVER_ERROR", "message": "..."}`.
- The resolver message now includes the specific reason code, such as
  `UNKNOWN_MARKET` or `CANONICAL_UNSUPPORTED`.
- `POST /sources/report` remains read-only and returns HTTP 501 with
  `NOT_IMPLEMENTED`; it does not create a registry or persistence layer.
- `GET /sources/status` translates provider report failures into explicit
  `FAILED` source statuses.

`GET /asof/current` still has documented convenience defaults for interactive
use. These defaults stay at the reference-app surface and pass through
`ResolveRequest`; they do not become core resolver defaults.

## CLI Audit Findings

The CLI remains a thin wrapper over `ResolveRequest`, `resolve`, and
`make_snapshot`.

CLI behavior conforms after the resolver fix:

- Naive and non-UTC datetime arguments are rejected at argparse time.
- LIVE with `--as-of-utc` is rejected by `ResolveRequest`.
- REPLAY/HISTORICAL without required UTC fields are rejected by
  `ResolveRequest`.
- Unknown market exits nonzero and stderr includes `UNKNOWN_MARKET`.
- CANONICAL exits nonzero and stderr includes `CANONICAL_UNSUPPORTED`.
- Missing source files do not produce fake freshness; the file provider
  fails closed and the resolver returns a `FAILED` source status.

The CLI still uses documented convenience defaults for interactive use:
`LIVE`, `XNYS`, and `America/New_York`. These defaults are reference-surface
defaults and not core resolver semantics.

## Snapshot Audit Findings

`canonicalize_context(context)` is deterministic for the same
`TemporalContext`: it dumps Pydantic JSON-mode data with sorted keys and
tight separators. `canonicalize_snapshot_payload(context)` is the
versioned hash preimage for snapshots.

`make_snapshot(context, snapshot_id)` computes `content_hash` from the
canonicalized snapshot payload, including snapshot schema version, semantic
contract version, and context. The hash is reproducible for byte-equal
contexts under the same versions and changes when the embedded context or
hash-affecting versions change.

`captured_at_utc` intentionally uses `datetime.now(timezone.utc)`, so the
snapshot record itself is not byte-identical across calls. This does not
affect the deterministic `content_hash`. There is no replay engine in this
repo, so snapshot replay cannot currently reach out to wall-clock state
unless a future replay surface is added.

## UTC / Timezone Enforcement Findings

UTC and timezone validation is strong at public boundaries:

- `TemporalContext`, `SourceStatus`, `AsOfSnapshot`, and `ResolveRequest`
  reject naive datetime values.
- `*_utc` fields reject non-UTC offsets.
- `market_timezone` is validated via `zoneinfo.ZoneInfo` and rejects
  abbreviations such as `EST`.
- `market` must be uppercase and non-empty.
- Public market-relative response models include `market` and
  `market_timezone`.
- XNYS calendar methods reject naive and non-UTC inputs before converting
  through `ZoneInfo("America/New_York")`.

Searches found no `utcnow`, `replace(tzinfo=...)`, or localtime use.

## Perspective Enforcement Findings

Perspective validation is mostly enforced before resolver logic:

- LIVE rejects `as_of_utc` and `knowledge_cutoff_utc`.
- REPLAY and HISTORICAL require both `as_of_utc` and
  `knowledge_cutoff_utc`.
- `knowledge_cutoff_utc > as_of_utc` is rejected.
- CANONICAL rejects `as_of_utc`.
- EXECUTED may carry explicit UTC fields; without an execution authority,
  the resolver returns `execution_state=UNKNOWN` with
  `EXECUTION_FACTS_UNAVAILABLE`.
- CANONICAL now fails closed because the minimal resolver has no canonical
  authority provider.

This prevents replay/historical calls from silently using wall-clock now and
prevents the resolver from quietly becoming a system of record.

## Fail-Closed Findings

Fail-closed behavior is now coherent across runtime surfaces:

- Unknown market raises typed `ResolverError` with `UNKNOWN_MARKET`.
- Calendar identity/timezone mismatches raise typed `ResolverError` with
  explicit reason codes.
- Duplicate providers raise typed `ResolverError`.
- Provider read/report failures become `FAILED` source statuses, not
  `FRESH`.
- Malformed API requests fail with 422.
- Malformed CLI arguments fail with exit code 2.
- CANONICAL fails closed until a real canonical authority boundary exists.
- UNKNOWN enum states that are allowed in `TemporalContext` require
  `reason_code` and `explanation`.

## Contract Mismatch Findings

Fixed during this audit:

- Resolver no longer asserts canonical state without canonical authority.
- Resolver errors now include stable reason-code prefixes.
- Tests now cover canonical fail-closed behavior through resolver, API, and
  CLI.
- `docs/minimal_resolver_report.md` no longer claims the minimal resolver
  returns `canonical_state=CANONICAL`.

No remaining HOLD-level runtime mismatch was found.

## HOLD / WARNING / NOTE Table

| Level | Finding | Status |
| --- | --- | --- |
| NOTE | `CANONICAL` currently fails closed because no canonical authority protocol/provider exists. | Safe behavior; future work may add a typed authority boundary. |
| NOTE | XNYS calendar is deliberately minimal and does not model full early-close sessions or full exchange calendars. | Known unsupported early-close dates now fail closed as `CLOSED`; no silent fallback to another market/calendar. |
| NOTE | Snapshot `captured_at_utc` changes per call. | Expected audit timestamp; `content_hash` remains deterministic for the versioned snapshot payload. |
| NOTE | API resolver failures now expose explicit `reason_code`. | This removes the prior need to parse `message` for resolver failure identity. |
| NOTE | CLI/API convenience defaults remain. | Documented as reference-surface conveniences, not resolver semantics. |

## Recommended Next Hardening Step

The next hardening step should be a typed canonical authority boundary, not a
provider expansion or external integration. Until such a boundary exists,
CANONICAL should continue to fail closed.

The API-hardening pass has split resolver errors into `error` plus
`reason_code` fields, preserving the current fail-closed control flow while
making error parsing cleaner.

## Validation Results

Commands run:

- `python -m pytest tests/test_resolver.py tests/test_api.py tests/test_cli.py -q`
- `python -m pytest -q`
- `rg -n "datetime\\.now|utcnow|replace\\(tzinfo|localtime|timezone\\.utc|ResolverError|UNKNOWN|CLOSED|default|fallback|fall back" src tests examples README.md PRODUCT_CONTRACT.md docs`
- `git diff --check`
- `LC_ALL=C rg -n "[^\\x00-\\x7F]" --glob '*.md'`

Results:

- Targeted resolver/API/CLI tests passed: 41 passed.
- Full test suite passed: 149 passed.
- Targeted grep found expected uses of `datetime.now(timezone.utc)` only in
  current-context and snapshot paths, no `utcnow`, no `replace(tzinfo=...)`,
  and no localtime usage.
- Targeted grep found expected enum values, documented defaults, and
  `ResolverError` paths with reason-code tests.
- `git diff --check` passed.
- Markdown ASCII check passed with no matches.

## Final Verdict

PASS.

Runtime behavior now conforms to the reconciled contract under the audited
edge cases. The only semantic violation found during the audit was corrected
with a narrow fail-closed resolver change and tests.
