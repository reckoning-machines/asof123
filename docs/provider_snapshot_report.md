# Provider and Snapshot Report

## Files Created or Updated

Created:
- /Users/jedgore/dev/asof123/src/asof123/providers/__init__.py
- /Users/jedgore/dev/asof123/src/asof123/providers/_protocol.py
- /Users/jedgore/dev/asof123/src/asof123/providers/static.py
- /Users/jedgore/dev/asof123/src/asof123/providers/file.py
- /Users/jedgore/dev/asof123/src/asof123/snapshot.py
- /Users/jedgore/dev/asof123/tests/test_static_provider.py
- /Users/jedgore/dev/asof123/tests/test_file_provider.py
- /Users/jedgore/dev/asof123/tests/test_snapshot.py
- /Users/jedgore/dev/asof123/docs/provider_snapshot_report.md

Removed:
- /Users/jedgore/dev/asof123/src/asof123/providers.py
  (replaced by the `providers/` package; contents moved into
  `providers/_protocol.py`, no behavior change.)

Updated:
- /Users/jedgore/dev/asof123/src/asof123/__init__.py
  - Added `StaticProvider`, `FileProvider`, `make_snapshot`, and
    `canonicalize_context` to imports and `__all__`. Later snapshot
    schema hardening also exported `canonicalize_snapshot_payload`.
  - Updated the module docstring to reflect the new public surface.
  - Preserved all prior exports. `from asof123.providers import
    ProviderReportError, SourceProvider` continues to work unchanged
    via `providers/__init__.py`.

No FastAPI app, CLI, persistence layer, scheduler, orchestration code,
async behavior, network IO, external API, background job, or database
IO was introduced. The only IO in this pass is local file reads
performed by `FileProvider`.

## Provider Implementation Decisions

`providers.py` became `providers/` so the protocol and the concrete
implementations can live side by side without crowding one module.
`SourceProvider` and `ProviderReportError` moved verbatim into
`providers/_protocol.py`; `providers/__init__.py` re-exports them along
with `StaticProvider` and `FileProvider`. The internal `_protocol`
module keeps `static.py` and `file.py` from importing through the
package's `__init__.py`, which avoids a partially-initialized-module
trap if anyone later moves imports around in `__init__.py`. Callers
that imported `from asof123.providers import SourceProvider` or
`from asof123.providers import ProviderReportError` see no change.

`StaticProvider`:

- Constructor: `StaticProvider(name: str, status: SourceStatus)`.
- `name` is required and must be non-empty; raises `ValueError`
  otherwise. This is a constructor-time guard, not a runtime guard,
  because a static fixture with no name is always a bug.
- If `status.provider` is `None`, the constructor fills it in with
  `name` via `status.model_copy(update=...)`. The original SourceStatus
  the caller passed in is not mutated; only the stored copy carries the
  filled-in provider.
- If `status.provider` is set and does not match `name`, the constructor
  raises `ValueError` with both values in the message. This catches
  fixture / registration mismatches early.
- `report(now_utc)` returns the stored `SourceStatus` directly, by
  identity. The input clock is intentionally ignored: that is what
  "static" means. No copy is made per call, no clock is read, no side
  effects.
- The `SourceProvider` protocol is structural and runtime-checkable,
  so `StaticProvider` does not need to inherit from anything to satisfy
  it. `isinstance(StaticProvider(...), SourceProvider)` is True.

`FileProvider`:

- Constructor: `FileProvider(name: str, path: str | Path)`.
- `name` is required and non-empty; raises `ValueError` otherwise.
- The path is stored as `pathlib.Path` so the rest of the implementation
  can treat string and `Path` inputs identically.
- `report(now_utc)` reads the file on every call. There is no caching,
  no memoization, no watchdog, no background refresh. Each call is an
  independent transaction; the test
  `test_file_is_re_read_on_each_report` proves that semantic by
  mutating the file between calls and observing a different
  `SourceStatus`.
- The JSON shape maps directly to `SourceStatus` fields. If `provider`
  is absent (or explicitly `null`), the FileProvider's own `name` is
  used. If `provider` is present and disagrees with `name`, the call
  fails closed.
- All validation flows through `SourceStatus(**payload)`. The
  `extra="forbid"`, UTC validators, and IANA timezone checks on
  `SourceStatus` are reused as the schema for the file. The FileProvider
  does not duplicate or relax those rules.

## Fail-Closed Behavior

`FileProvider` raises `ProviderReportError` rather than `ValueError` or
`FileNotFoundError` for every failure mode below. This keeps the
resolver's existing fail-closed translation (which catches
`ProviderReportError` and produces a `SourceStatus` with
`SourceFreshness.FAILED`) sufficient; the resolver does not need to
learn any new exception types.

Failure modes:

- File not found: `FileNotFoundError` -> `ProviderReportError("file not
  found at ...")`.
- Other OS read failure: `OSError` -> `ProviderReportError("cannot
  read ...: <reason>")`.
- Empty file (length 0 or whitespace only) -> `ProviderReportError`.
  Whitespace-only is treated as empty because a file containing only
  newlines is functionally the same and would otherwise produce a
  noisy JSON parse error.
- Invalid JSON: `json.JSONDecodeError` -> `ProviderReportError("invalid
  JSON at ...: <msg>")`.
- JSON that parses but is not an object (array, scalar, null) ->
  `ProviderReportError("must be an object")`. SourceStatus is an
  object-shaped model; arrays and scalars are never valid payloads.
- Provider mismatch: payload's `provider` set and not equal to
  `self.name` -> `ProviderReportError("does not match")`.
- Invalid `SourceStatus` payload (bad enum value, naive datetime,
  non-UTC datetime, unknown field, etc.):
  `pydantic.ValidationError` -> `ProviderReportError("invalid
  SourceStatus payload at ...: <errors>")`.

`StaticProvider` does not raise `ProviderReportError`; its failure
modes are constructor-time only (`ValueError`).

## Snapshot Hashing Decisions

`snapshot.py` exposes three snapshot helpers:

- `canonicalize_context(context: TemporalContext) -> str`
- `canonicalize_snapshot_payload(context: TemporalContext) -> str`
- `make_snapshot(context: TemporalContext, snapshot_id: str) ->
  AsOfSnapshot`

Hash chosen: SHA256. It is in the standard library
(`hashlib.sha256`), fixed-width (64 hex characters), and collision-safe
for this purpose. The hex digest is stored on the snapshot as
`content_hash`. `AsOfSnapshot.content_hash` is already validated as a
non-empty string by the model, so a malformed digest cannot leak
through.

`captured_at_utc` is `datetime.now(timezone.utc)`. The snapshot is the
only artifact in the repo that legitimately reads wall-clock time at
construction; that is what "captured at" means. The resolver and the
calendar still get their `now_utc` from the request or from
`datetime.now(timezone.utc)` propagated downward, and providers still
do not read clocks.

The snapshot embeds a validated copy of the full `TemporalContext`.
This prevents later caller mutation of the original context from
changing the snapshot's semantic payload after `content_hash` has been
computed. The snapshot is fully validated by `AsOfSnapshot`'s own model
validator before it is returned; an empty `snapshot_id` raises
`pydantic.ValidationError`, not `ValueError`, and never produces a
half-built snapshot.

## Deterministic Serialization Decisions

`canonicalize_context` follows these rules:

1. `context.model_dump(mode="json")` produces a Python dict whose enum
   values are their string members and whose datetimes are ISO 8601 UTC
   strings. This is the canonical wire form of the model.
2. `json.dumps(payload, sort_keys=True, separators=(",", ":"),
   ensure_ascii=False)` sorts keys at every nesting level, removes
   whitespace via tight separators, and emits UTF-8 directly. Sort
   ordering at every level (not just the top) is what guarantees that
   two byte-equal contexts produce two byte-equal canonical strings.

`canonicalize_snapshot_payload` wraps the context with the hash-affecting
snapshot versions before serialization:

- `snapshot_schema_version`
- `semantic_contract_version`
- `context`

SHA256 is computed over `canonicalize_snapshot_payload(context).encode("utf-8")`.
UTF-8 is explicit so callers cannot assume a different encoding by accident.

Properties enforced by tests:

- `canonicalize_context(ctx)` equals
  `json.dumps(ctx.model_dump(mode="json"), sort_keys=True,
  separators=(",", ":"), ensure_ascii=False)` exactly, so a future
  refactor cannot silently change the canonical form.
- Tight separators: no `", "` and no `": "` appear in the canonical
  string. This is asserted directly.
- Two snapshots from the same context have the same `content_hash`.
- `content_hash` equals SHA256 over
  `canonicalize_snapshot_payload(context).encode("utf-8")`.
- Changing any field (perspective, price_basis, a source's freshness)
  changes the hash.
- Building a snapshot does not mutate the input `TemporalContext`
  (`model_dump` before and after are byte-equal).

## Tests Added

`tests/test_static_provider.py` (7 tests):
- Happy path: stored status returned with provider, freshness, and
  `last_update_utc` carried through.
- Constructor auto-fills `status.provider` when absent.
- Mismatched provider names raise `ValueError`.
- Empty name raises `ValueError`.
- `report` returns a `SourceStatus` instance.
- `StaticProvider` satisfies the `SourceProvider` protocol via
  `isinstance` against the runtime-checkable protocol.
- `report` is independent of `now_utc` (identity stable across calls).

`tests/test_file_provider.py` (14 tests):
- Happy path: valid JSON file parses into a `SourceStatus`.
- `provider` auto-filled from FileProvider name when absent in file.
- Missing file -> `ProviderReportError("not found")`.
- Empty file -> `ProviderReportError("empty")`.
- Whitespace-only file -> `ProviderReportError("empty")`.
- Invalid JSON -> `ProviderReportError("invalid JSON")`.
- Non-object JSON (array) -> `ProviderReportError("must be an object")`.
- Invalid freshness enum -> `ProviderReportError("invalid SourceStatus")`.
- Naive datetime in payload -> `ProviderReportError("invalid SourceStatus")`.
- Mismatched provider name -> `ProviderReportError("does not match")`.
- `report` returns a `SourceStatus` instance.
- `FileProvider` satisfies the `SourceProvider` protocol.
- Empty name raises `ValueError`.
- File contents are re-read on every call (no caching).

All filesystem access is via `tmp_path`. No real-world paths, no
network, no external services.

`tests/test_snapshot.py` (9 tests):
- `make_snapshot` returns a validated `AsOfSnapshot` with a 64-char
  hex `content_hash`, UTC-aware `captured_at_utc`, and a validated copy
  of the input context attached.
- The snapshot carries `snapshot_schema_version`,
  `semantic_contract_version`, and `hash_algorithm`.
- Two snapshots from the same context have the same `content_hash`.
- `canonicalize_context` is deterministic across calls.
- Changing the context changes the hash.
- Empty `snapshot_id` raises `pydantic.ValidationError`.
- `captured_at_utc` is timezone-aware UTC with zero offset.
- Canonical JSON matches `json.dumps(model_dump(mode="json"),
  sort_keys=True, separators=(",", ":"), ensure_ascii=False)` and has
  no `", "` or `": "` whitespace.
- `make_snapshot` does not mutate the input context.
- Changing a `SourceStatus.freshness` inside `sources` changes the
  hash (so the canonical form is recursive, not just shallow).

Total project test count: 115 passed (85 prior + 30 new).

## Validation Commands Run

1. `python -m py_compile src/asof123/__init__.py
   src/asof123/providers/__init__.py
   src/asof123/providers/_protocol.py
   src/asof123/providers/static.py
   src/asof123/providers/file.py
   src/asof123/snapshot.py
   tests/test_static_provider.py
   tests/test_file_provider.py
   tests/test_snapshot.py`
   Result: clean.

2. `python -m pytest -q`
   Result: 115 passed in 0.12s.

3. `LC_ALL=C grep -rnP '[^\x00-\x7F]' src/asof123/__init__.py
   src/asof123/providers/ src/asof123/snapshot.py
   tests/test_static_provider.py tests/test_file_provider.py
   tests/test_snapshot.py`
   Result: no matches (exit 1).

4. `git diff --check`
   Result: clean (exit 0).

## Assumptions Made

- `providers/` became a package with an internal `_protocol.py` module
  so that `static.py` and `file.py` import the protocol from a stable
  internal location rather than through `providers/__init__.py`. The
  brief did not call for `_protocol.py` explicitly, but creating it
  avoids a partially-initialized-module trap if anyone later rearranges
  imports in `__init__.py`. The public surface
  (`from asof123.providers import SourceProvider, ProviderReportError`)
  is unchanged.
- `StaticProvider.report` returns the stored `SourceStatus` by identity,
  not by copy. `SourceStatus` is now frozen after validation, so callers
  cannot mutate the returned model in place and change subsequent static
  reports.
- `FileProvider` re-reads the file on every call rather than caching.
  Caching introduces a refresh-policy question that belongs to a higher
  layer; the minimal provider has no opinion on it. Callers that need
  caching can wrap the provider, but the open-source minimum does not.
- `canonicalize_snapshot_payload` uses `ensure_ascii=False` and an explicit
  UTF-8 encoding before hashing, matching the brief's UTF-8 requirement.
  All current contract content is ASCII, but the canonical snapshot payload
  is deterministic for any UTF-8 input that `model_dump(mode="json")`
  produces.
- `make_snapshot` reads `datetime.now(timezone.utc)` for
  `captured_at_utc`. This is the one place in the package where wall-
  clock time is read directly. The resolver still propagates `now_utc`
  from the request or computes it once and hands it to providers;
  providers themselves still do not read clocks.

## Recommended Next Step

The package now has enough surface area for a useful local demo, but
all surfaces are still in-process. The next pass should add a small
HTTP entry point so external services can call `resolve` and
`make_snapshot` over a single port, without introducing scheduling,
persistence, or auth. In order:

1. `src/asof123/api.py`: a FastAPI app exposing exactly the four
   endpoints from PRODUCT_CONTRACT.md section 14:
   `GET /asof/current`, `POST /asof/resolve`, `POST /sources/report`,
   `GET /sources/status`, and `POST /asof/snapshot`. The app must
   accept a `Mapping[str, MarketCalendar]` and a list of
   `SourceProvider`s at construction time; it must not load any state
   from disk or environment by default.
2. The FastAPI request models reuse `ResolveRequest`. The response
   models reuse `TemporalContext` and `AsOfSnapshot`. No new models
   are introduced unless the HTTP surface genuinely needs them.
3. `tests/test_api.py` using `fastapi.testclient.TestClient`, with a
   `StaticProvider` and an `XNYSCalendar` wired up at fixture scope.
   No live network; the test client speaks ASGI in-process.
4. A small CLI entry point (`python -m asof123 resolve ...`) only
   after the HTTP surface is in place. The CLI should be a wrapper
   over `resolve` and `make_snapshot`, not a parallel implementation.

Still out of scope for the next pass: persistence (writing snapshots
to disk or to a database), scheduling, retry orchestration, async,
authentication, multi-tenant configuration, and any non-static /
non-file SourceProvider.
