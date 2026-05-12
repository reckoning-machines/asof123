# API Reference Surface Report

## Files Created or Updated

Created:
- /Users/jedgore/dev/asof123/src/asof123/api.py
- /Users/jedgore/dev/asof123/tests/test_api.py
- /Users/jedgore/dev/asof123/docs/api_reference_surface_report.md

Updated:
- /Users/jedgore/dev/asof123/pyproject.toml
  - Added `api = ["fastapi>=0.110", "httpx>=0.27"]` optional extra.
  - Added `fastapi>=0.110` and `httpx>=0.27` to the `dev` extra so
    `pytest` can drive the API in-process via
    `fastapi.testclient.TestClient`.
  - Did not add FastAPI to the core dependency list. The package
    remains importable and useful without FastAPI installed.
- /Users/jedgore/dev/asof123/src/asof123/__init__.py
  - Added `create_app` to `__all__`.
  - Exposed `create_app` lazily via `__getattr__` so a plain
    `import asof123` does not pull in FastAPI. The first attribute
    access (`asof123.create_app`) imports `asof123.api`; without the
    `api` extra installed, that access raises `ImportError` rather than
    failing at module-import time.
  - Updated the module docstring to describe the new HTTP surface.
  - Preserved every prior export.

No persistence, auth, multi-tenant config, scheduler, orchestration,
async behavior, background job, external network call, database
integration, or CLI was added. The reference app is read-only and
fully in-process.

## Endpoint Behavior

`create_app(calendars=None, providers=None)` builds a FastAPI app:

- `calendars` defaults to `{"XNYS": XNYSCalendar()}`. Stored on
  `app.state.calendars` as a plain dict.
- `providers` defaults to `[]`. Stored on `app.state.providers` as a
  plain list.
- No environment loading, no disk loading, no auth, no persistence,
  no scheduling, no background tasks.

Routes:

- `GET /asof/current` — Query parameters: `perspective` (defaults to
  `LIVE`), `market` (defaults to `XNYS`), `market_timezone` (defaults to
  `America/New_York`). Builds a `ResolveRequest` with no `as_of_utc`
  and no `knowledge_cutoff_utc`, calls `resolve`, returns the
  `TemporalContext`.
- `POST /asof/resolve` — Body: `ResolveRequest`. Calls `resolve`,
  returns the `TemporalContext`.
- `GET /sources/status` — Iterates `app.state.providers`, calls
  `provider.report(datetime.now(timezone.utc))` on each. Translates
  `ProviderReportError` into a `SourceStatus` with
  `freshness=FAILED`, `reason_code="PROVIDER_REPORT_FAILED"`, and the
  exception message in `explanation`. Returns a JSON object keyed by
  provider name. Duplicate provider names short-circuit before any
  provider is called and return HTTP 409 Conflict with body
  `{"error": "DUPLICATE_PROVIDER_NAME", "message": "..."}`.
- `POST /sources/report` — Body: `SourceReportRequest`
  (`{"name": ..., "status": SourceStatus}`). Always returns HTTP 501
  Not Implemented with body
  `{"error": "NOT_IMPLEMENTED", "message": "The reference app is
  read-only. Source reporting requires a registry or persistence layer
  outside this pass."}`. The route still accepts and validates the
  request body so the OpenAPI shape matches PRODUCT_CONTRACT.md section
  14; only the runtime implementation is deferred.
- `POST /asof/snapshot` — Body: `SnapshotRequest`
  (`{"snapshot_id": str, "context": TemporalContext}`). Calls
  `make_snapshot(context, snapshot_id)` and returns the
  `AsOfSnapshot`. The `snapshot_id` is validated to be non-empty at
  request parse time, so an empty value returns HTTP 422 before
  `make_snapshot` is invoked.

## Dependency Decision

FastAPI and httpx are optional extras, not core dependencies. The core
package is the contract-aligned ontology plus the in-process resolver;
it should remain importable from a Python environment that has only
Pydantic installed. The HTTP surface is a convenience, not the system
of record.

`pyproject.toml` now has two extras:

- `api`: `fastapi>=0.110` and `httpx>=0.27`. `httpx` is included
  because `fastapi.testclient.TestClient` depends on it; shipping the
  extra without httpx would leave the test harness broken.
- `dev`: `pytest>=8.0` plus `fastapi>=0.110` and `httpx>=0.27`. Test
  development requires FastAPI to be installed, so it is bundled into
  the dev extra rather than left to a separate command.

Implementation choice: `asof123.create_app` is exposed lazily via
`__getattr__` on the package. A consumer who never installs the `api`
extra can still do `import asof123` and use everything else. The
moment they reference `asof123.create_app`, the api module is imported
and FastAPI is needed. If FastAPI is missing the import error surfaces
at that point, not at the time of `import asof123`. This keeps the
core dependency footprint honest.

## State Injection Decision

Calendars and providers are passed to `create_app` at construction
time and stored on `app.state` (a plain attribute container provided
by Starlette). They are:

- Stored as plain dict / list rather than as a mapping protocol object,
  so tests and downstream code can introspect `app.state.calendars`
  and `app.state.providers` directly.
- Snapshotted at construction time: passing an iterable for
  `providers` materializes it into a list once. There is no live
  refresh, no rotation, no addition or removal at runtime. Adding a
  provider later requires constructing a new app.
- Never persisted, never loaded from disk, never loaded from
  environment variables. The reference app is a thin HTTP front for an
  in-process call; it does not assume an environment beyond the
  arguments to `create_app`.

This matches the contract's read-only stance for this pass and keeps
the surface area minimal. A future pass that introduces a mutable
registry can replace `app.state.providers` with a registry object
without changing the URL surface.

## Error Handling

- `ResolverError` (raised by `resolve`) is caught by an exception
  handler registered on the app. The response is HTTP 400 Bad Request
  with body `{"error": "RESOLVER_ERROR", "message": "..."}`, where
  `message` is `str(exc)`. This is the only path that converts a
  Python exception into a non-standard error body; everything else
  follows FastAPI's defaults.
- Pydantic validation errors on request bodies (invalid
  `ResolveRequest`, invalid `SnapshotRequest`, etc.) surface as HTTP
  422 with FastAPI's default error envelope (`{"detail": [...]}`).
  This is the framework default and is sufficient for the reference
  app.
- Provider failures in `GET /sources/status` are never converted to
  HTTP 500. A `ProviderReportError` becomes a `SourceStatus` with
  `freshness=FAILED`; the HTTP response itself is still 200 and the
  failing provider appears alongside the healthy ones. This matches
  the resolver's fail-closed contract: providers report facts, even
  the fact of their own failure.
- Duplicate provider names in `GET /sources/status` return HTTP 409
  Conflict with body
  `{"error": "DUPLICATE_PROVIDER_NAME", "message": "..."}`. 409 was
  chosen over 500 because the duplication is a registration mistake
  caught at request time, not an internal server fault. The message
  names the offending provider so a caller can fix it.
- Unexpected exceptions (none expected in this pass, but possible if
  a provider raises something other than `ProviderReportError`) fall
  through to FastAPI's default 500 handler. The reference app does
  not catch arbitrary exceptions, because doing so would mask bugs in
  third-party providers that this pass is not in a position to debug.

## Tests Added

`tests/test_api.py` (12 tests):

- `create_app()` with no arguments registers `XNYSCalendar` under
  `"XNYS"` and an empty providers list.
- `GET /asof/current` defaults to perspective LIVE, market XNYS,
  market_timezone America/New_York. Time-of-day agnostic.
- `GET /asof/current?perspective=PRE_TRADE_INTENT` returns 200 with a
  valid `TemporalContext`. Market phase is asserted to be one of the
  six pinned values rather than a specific value.
- `POST /asof/resolve` with a REPLAY body pinned to
  `2026-02-10T21:00:00Z` (both `as_of_utc` and `knowledge_cutoff_utc`)
  returns 200 and the returned `resolved_at_utc` and
  `knowledge_cutoff_utc` start with the pinned instant.
- `POST /asof/resolve` with `perspective=LIVE` and `as_of_utc` set
  returns 422 (caught by `ResolveRequest`'s own model validator
  before any handler logic runs).
- Missing calendar: `create_app(calendars={})` plus an XNYS request
  returns 400 with `{"error": "RESOLVER_ERROR", "message": "..."}`
  containing `"XNYS"` in the message.
- `GET /sources/status` with one `StaticProvider` returns a JSON
  object keyed by provider name, with the stored freshness and
  provider fields preserved.
- `GET /sources/status` with a provider that raises
  `ProviderReportError` returns 200 with the provider listed as
  `freshness=FAILED`, `reason_code=PROVIDER_REPORT_FAILED`, and the
  exception message inside `explanation`.
- `GET /sources/status` with two providers of the same name returns
  409 with `{"error": "DUPLICATE_PROVIDER_NAME", ...}`.
- `POST /sources/report` with a valid body returns 501 with
  `{"error": "NOT_IMPLEMENTED", ...}` and the word `"read-only"` in
  the message.
- `POST /asof/snapshot` with a valid context returns 200 with a 64-
  character hex `content_hash` and a UTC `captured_at_utc`.
- `POST /asof/snapshot` with `snapshot_id=""` returns 422 at request
  parse time (the validator rejects empty before `make_snapshot` is
  called).

All tests use `fastapi.testclient.TestClient` for in-process ASGI
calls. No real network, no external services, no disk.

Total project test count: 127 passed (115 prior + 12 new).

## Validation Commands Run

1. `python -m py_compile src/asof123/__init__.py src/asof123/api.py
   tests/test_api.py`
   Result: clean.

2. `python -m pytest -q`
   Result: 127 passed in 0.20s.

3. `LC_ALL=C grep -rnP '[^\x00-\x7F]' src/asof123/__init__.py
   src/asof123/api.py tests/test_api.py pyproject.toml`
   Result: no matches (exit 1).

4. `git diff --check`
   Result: clean (exit 0).

## Assumptions Made

- `POST /sources/report` returns HTTP 501 deliberately. The brief
  allowed picking a status; 501 was chosen over 405 because the
  endpoint is named in the contract (PRODUCT_CONTRACT.md section 14)
  but is intentionally not implemented in this pass. 405 would
  suggest "wrong method"; 501 says "this method on this path is
  defined but not yet implemented", which matches reality.
- `GET /sources/status` duplicate-name response is HTTP 409 Conflict
  rather than 500. The brief permitted either; 409 reflects that the
  state (`app.state.providers`) was constructed with conflicting
  inputs, not that the server hit an internal fault. This is the
  same 409 a registry would return for a unique-key violation.
- `app.state.providers` is materialized into a list at construction
  time. The brief said `providers: Iterable[SourceProvider] | None =
  None`; iterables can be one-shot generators, so materializing once
  is the only way to make a long-lived FastAPI app correct.
- `create_app` is exposed via lazy `__getattr__` on the package. This
  keeps `import asof123` cheap and avoids forcing FastAPI into the
  core dependency set. The lazy lookup matches PEP 562 module-level
  `__getattr__` semantics.
- `GET /sources/status` does not have an explicit `response_model`.
  The success path returns `dict[str, SourceStatus]` (which FastAPI
  serializes naturally), and the duplicate-name path returns a
  `JSONResponse` with a 409 envelope. Setting `response_model` would
  add OpenAPI documentation for the success path but would conflict
  with the JSONResponse-from-the-same-handler pattern that this
  endpoint needs. A future pass can split the duplicate check into
  an exception handler if the OpenAPI fidelity becomes important.
- `POST /sources/report` validates the body shape via
  `SourceReportRequest` even though the endpoint always returns 501.
  This keeps the OpenAPI documentation accurate for the contract's
  named endpoint and means a future implementation can drop the
  `JSONResponse(501)` line without rewriting the route.

## Recommended Next Step

The next pass should add a small CLI on top of `create_app`, `resolve`,
and `make_snapshot`. The CLI should be a thin wrapper, not a parallel
implementation. In order:

1. `src/asof123/cli.py`: a `main(argv=None)` entrypoint built on
   `argparse` (no Typer / Click dependency yet). Subcommands:
   - `asof123 resolve --perspective LIVE --market XNYS
     --market-timezone America/New_York [--as-of-utc ...]
     [--knowledge-cutoff-utc ...]`: build a `ResolveRequest`, call
     `resolve` against a default `XNYSCalendar` and empty providers,
     print the `TemporalContext` as canonical JSON.
   - `asof123 snapshot --snapshot-id ... < context.json`: read a
     `TemporalContext` from stdin (canonical JSON), call
     `make_snapshot`, print the `AsOfSnapshot` as canonical JSON.
   - `asof123 serve --host 127.0.0.1 --port 8000`: import
     `uvicorn` lazily and run `create_app()`. The `uvicorn` import
     should be inside the `serve` subcommand only; do not add
     `uvicorn` to the core dependency set.
2. `tests/test_cli.py`: drive `main(argv=[...])` directly and capture
   stdout, so the CLI is testable without subprocess.
3. A `pyproject.toml` entry point: `[project.scripts] asof123 =
   "asof123.cli:main"`. This makes the CLI installable as a binary.
4. Add `uvicorn` to the `api` extra (or a new `serve` extra) so
   `pip install asof123[api]` covers the full HTTP runtime.

Still out of scope for the next pass: persistence (writing snapshots
to disk or to a database), scheduler / background work, auth, multi-
tenant configuration, retries, async, and any non-static / non-file
SourceProvider implementations.
