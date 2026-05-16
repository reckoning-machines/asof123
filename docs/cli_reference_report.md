# CLI Reference Report

## Files Created or Updated

Created:
- /Users/jedgore/dev/asof123/src/asof123/cli.py
- /Users/jedgore/dev/asof123/tests/test_cli.py
- /Users/jedgore/dev/asof123/docs/cli_reference_report.md

Updated:
- /Users/jedgore/dev/asof123/pyproject.toml
  - Added the console entry point `asof123 = "asof123.cli:main"` under
    `[project.scripts]`.
  - Added a new `serve` optional extra (`fastapi`, `httpx`, `uvicorn`).
  - Added `uvicorn>=0.27` to the `dev` extra so `pytest` can drive the
    `serve` subcommand in-process via monkeypatching.
  - Did not add FastAPI or uvicorn to the core dependency list. The
    core install is still Pydantic only.

Not updated:
- /Users/jedgore/dev/asof123/src/asof123/__init__.py
  - The CLI is exposed via the `asof123` console script, not via the
    package's import surface. `from asof123 import main` was not
    requested by the brief and would add a CLI import path that
    competes with `asof123.cli:main`.

No persistence, auth, scheduler, background jobs, mutable source
registry, external integrations, database integrations, or config
system was introduced. The CLI is a thin in-process wrapper around the
existing library and FastAPI app.

## Subcommands

`asof123 resolve` builds a `ResolveRequest`, resolves it in-process
against an `XNYSCalendar`, and prints the resulting `TemporalContext`
as JSON. Options:

- `--perspective`: defaults to `LIVE`; one of the seven pinned
  `Perspective` values.
- `--market`: defaults to `XNYS`.
- `--market-timezone`: defaults to `America/New_York`.
- `--as-of-utc`: optional ISO 8601 UTC datetime.
- `--knowledge-cutoff-utc`: optional ISO 8601 UTC datetime.
- `--source-file name=path`: appendable. Each occurrence creates a
  `FileProvider(name, path)` that reads its `SourceStatus` from a
  local JSON file.

`asof123 snapshot` resolves the same way and then calls `make_snapshot`
on the result. Required argument `--snapshot-id`. All other arguments
are shared with `resolve` via a single `_add_resolve_args` helper, so
the two subcommands cannot drift apart accidentally.

`asof123 serve` imports `uvicorn` lazily (inside the subcommand
handler, not at module import time), builds the FastAPI app via
`create_app()`, and calls `uvicorn.run(app, host=..., port=...)`.

- `--host`: defaults to `127.0.0.1`.
- `--port`: defaults to `8000`.

If `import uvicorn` fails, the CLI prints a hint pointing at the
`asof123[serve]` extra and returns exit code 2.

## Dependency Decision

The CLI is built on `argparse` only. No `typer`, no `click`, no `rich`.
`argparse` is in the standard library; adding a CLI framework to the
core would force every consumer to pull it in even when they only
want the library.

`uvicorn` is added to a new `serve` optional extra and bundled into
the `dev` extra. It is not part of the `api` extra because the
FastAPI app itself is useful in-process (via `TestClient`) without an
ASGI runner. `pip install asof123[api]` gets the test client and the
app; `pip install asof123[serve]` adds uvicorn for production-style
serving.

The console script entry is wired through
`[project.scripts] asof123 = "asof123.cli:main"`. Installing the
package puts an `asof123` binary on `PATH`; without installation,
tests still invoke `main(argv=[...])` directly.

## Datetime Parsing Decision

`--as-of-utc` and `--knowledge-cutoff-utc` are parsed by a single
`_parse_utc` argparse `type=` function. The rules:

1. The input must be a non-empty string. Empty strings are rejected
   with `argparse.ArgumentTypeError`.
2. A trailing `Z` is normalized to `+00:00` so `datetime.fromisoformat`
   accepts it. (Pre-3.11 `fromisoformat` would not accept `Z`; the
   normalization keeps the same behavior across Python 3.11+ minor
   versions.)
3. `datetime.fromisoformat` parses the string. Any parse error
   surfaces as `argparse.ArgumentTypeError` with the original message.
4. If `tzinfo` is `None` or `utcoffset()` is `None`, the datetime is
   naive; rejected with a message that says "timezone-aware ... not
   allowed".
5. If `utcoffset()` is non-zero, the datetime is tz-aware but not UTC;
   rejected with a message that says "must be UTC (offset +00:00)".

This puts the strict UTC enforcement at the CLI boundary. Inputs that
reach `ResolveRequest` are already UTC-aware. The same enforcement is
duplicated inside `ResolveRequest`'s validators, but defense in depth
is intentional: if a future caller bypasses argparse and calls
`_build_request` directly, the model still rejects bad input.

## Source-File Behavior

`--source-file name=path` is parsed by another argparse `type=`
function. The rules:

- The value must contain an `=`. If not, argparse error.
- The `name` portion before the `=` must be non-empty. If not, argparse
  error.
- The `path` portion after the `=` must be non-empty. If not, argparse
  error.

Each parsed pair becomes a `FileProvider(name, path)` in the CLI's
providers list. FileProvider construction does not touch the
filesystem; it stores the path and validates that `name` is non-empty.
Actual reads happen when the resolver calls `provider.report(now_utc)`.

If the underlying file is missing, unreadable, empty, malformed JSON,
or contains a payload that does not validate as `SourceStatus`, the
provider raises `ProviderReportError` from `report`. The resolver
catches that and stores a `SourceStatus` with
`freshness=FAILED`, `reason_code=PROVIDER_REPORT_FAILED`, and the
exception message in `explanation`. The CLI prints the resulting
`TemporalContext` with the failing source listed alongside any healthy
ones and returns exit code 0.

This was the chosen behavior between the two options the brief
allowed: "FAILED SourceStatus in the resolved context" vs "nonzero
exit code from the CLI". A non-existent or unreadable provider file
is a fact about the world that the contract already has a vocabulary
for (`SourceFreshness.FAILED`). Turning it into a hard CLI failure
would discard that information and force the caller to decide
themselves; surfacing it as a FAILED status preserves it and lets the
caller decide whether to act on it. Constructor-time provider errors
(like an empty name from a malformed `--source-file`) still fail
nonzero because they indicate a bug in the invocation rather than a
fact about the world.

## Error Handling

Three layers:

- argparse errors (invalid datetime, missing `--snapshot-id`,
  malformed `--source-file`, unknown subcommand) call `sys.exit(2)`
  through argparse itself. They print to stderr and raise
  `SystemExit(2)`. Tests use `pytest.raises(SystemExit)` with
  `exc_info.value.code == 2`.
- Library-level errors (`pydantic.ValidationError` from
  `ResolveRequest` or `AsOfSnapshot`, `asof123.ResolverError` from
  the resolver) are caught inside each subcommand handler. The
  handler writes structured JSON with `error`, `reason_code`, and
  `explanation` to stderr and returns 2.
  `main(...)` returns 2 in this case (no exception leaks out).
- Provider-level failures (a `FileProvider` whose file cannot be
  read) are not caught at the CLI layer. The resolver translates
  them into `SourceFreshness.FAILED` entries in
  `TemporalContext.sources` and the CLI prints the resulting context
  with exit code 0. Test
  `test_source_file_missing_file_yields_failed_source_status`
  proves this.

`asof123 serve` reports a missing `uvicorn` via structured stderr JSON
plus exit code 2, not via a Python traceback. Other startup failures
(port already in use, etc.) are left to uvicorn and propagate as uvicorn
does.

## Tests Added

`tests/test_cli.py` (15 tests):

- `resolve` with no arguments produces JSON for `LIVE` / `XNYS` /
  `America/New_York` and a UTC `resolved_at_utc`. Time-of-day
  agnostic.
- `resolve` with `--perspective PRE_TRADE_INTENT` and pinned UTC
  fields produces `market_phase=PRE_OPEN` and
  `price_basis=PRIOR_CLOSE`.
- `resolve` with `--source-file name=path` includes the source's
  `SourceStatus` in the output, with `freshness=FRESH`.
- `resolve` with `--as-of-utc not-a-datetime` raises `SystemExit(2)`
  and writes an "ISO 8601" or "invalid" message to stderr.
- `resolve` with a naive datetime (`2026-05-12T12:00:00`) raises
  `SystemExit(2)` and stderr mentions `timezone-aware` or `naive`.
- `resolve` with a non-UTC offset (`+02:00`) raises `SystemExit(2)`
  and stderr mentions `UTC`.
- `resolve --perspective LIVE --as-of-utc ...` returns exit code 2
  (LIVE forbids `as_of_utc` per `ResolveRequest`'s validator) and
  writes structured JSON with `reason_code=INVALID_REQUEST` to stderr.
- `snapshot --snapshot-id demo-1 ...` returns exit code 0 with a 64-
  character hex `content_hash` and a non-empty `snapshot_id`.
- `snapshot` without `--snapshot-id` raises `SystemExit(2)` via
  argparse.
- `--source-file noequalsign` (malformed) raises `SystemExit(2)` and
  stderr mentions `name=path`.
- `--source-file pointing at a non-existent file` returns exit code 0
  with the source listed as `freshness=FAILED`,
  `reason_code=PROVIDER_REPORT_FAILED`.
- `serve` with `sys.modules["uvicorn"]` monkeypatched to `None`
  returns exit code 2 with structured stderr JSON mentioning `uvicorn`.
- `serve --host 0.0.0.0 --port 9000` with `sys.modules["uvicorn"]`
  monkeypatched to a `SimpleNamespace(run=...)` stub returns exit
  code 0 and the stub records the host and port that were passed.
- `resolve` JSON output round-trips through `json.loads` (sanity).
- `main([])` (no subcommand) raises `SystemExit(2)` via argparse.

All tests use `capsys` and / or `monkeypatch`. No subprocess, no real
network, no real disk other than `tmp_path`.

Total project test count: 142 passed (127 prior + 15 new).

## Validation Commands Run

1. `python -m py_compile src/asof123/cli.py tests/test_cli.py`
   Result: clean.

2. `python -m pytest -q`
   Result: 142 passed in 0.22s.

3. `LC_ALL=C grep -rnP '[^\x00-\x7F]' src/asof123/cli.py
   tests/test_cli.py pyproject.toml`
   Result: no matches (exit 1).

4. `git diff --check`
   Result: clean (exit 0).

## Assumptions Made

- `--perspective` defaults to `LIVE`. The brief allowed picking
  required-vs-defaulted; LIVE is the most common interactive use
  case and matches the default in `GET /asof/current`, so callers
  do not have to remember a flag for the common path.
- `--source-file` value parsing accepts `name=path` only. Paths
  containing `=` are not supported. A future extension can introduce
  `--source-file-json` or `--source-file file:///` if that
  restriction becomes a problem; until then `=` is enough for tests
  and demos.
- A missing or unreadable `--source-file` becomes a `FAILED`
  `SourceStatus` in the output, not a CLI error. See the
  source-file section above for the reasoning. Constructor-time
  provider errors (empty name, etc.) still fail nonzero because
  they indicate a bug in the invocation.
- Library validation errors (`pydantic.ValidationError`,
  `ResolverError`) print structured JSON to stderr. Argparse
  pre-dispatch errors remain conventional argparse stderr plus
  `SystemExit(2)`.
- `serve` imports uvicorn lazily inside the subcommand handler, not
  at module import time. This keeps `asof123.cli` importable in
  environments where uvicorn is not installed (for example a CI
  job that only needs `resolve`).
- `main(argv=None)` is the single entry point. The harness goes
  through argparse, so all flag validation lives in one place.
  `__main__` calls `main()` and exits with its return code, so the
  module can also be invoked as `python -m asof123.cli`.

## Recommended Next Step

The CLI uses the library and the FastAPI app as black boxes; it does
not yet exercise the open-source provider extension points. The next
pass should give one downstream system an end-to-end smoke test:

1. `examples/` directory at the repo root, containing:
   - `examples/static_fixtures/equities_quotes.json`: a hand-written
     SourceStatus fixture suitable for `--source-file`.
   - `examples/static_fixtures/official_close.json`: a `NOT_PUBLISHED`
     fixture with `expected_publication_utc` set.
   - `examples/demos/pre_open.sh`: a short shell script that runs
     `asof123 resolve --perspective PRE_TRADE_INTENT --as-of-utc ...
     --source-file equities_quotes=...` and pipes through `jq` so a
     human can see the canonical context output.
   - `examples/demos/canonical_unpublished.sh`: a demo that shows the
     CANONICAL perspective failing closed when the official-close
     SourceProvider is `NOT_PUBLISHED`.
2. `docs/quickstart.md`: a short walkthrough that pairs each demo
   script with the relevant section of `PRODUCT_CONTRACT.md`.
3. A smoke test under `tests/` that runs the demo scripts (or their
   Python equivalent) and asserts the JSON output matches a small
   snapshot fixture. No subprocess if avoidable; prefer calling
   `cli.main` directly with the same arguments.

Still out of scope for the next pass: persistence (writing snapshots
to disk or a database), scheduling, retries, auth, multi-tenant
configuration, async, additional `SourceProvider` implementations
(Postgres freshness reader, etc.), and any non-static / non-file
provider.
