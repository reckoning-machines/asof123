# Examples and Quickstart Report

## Files Created or Updated

Created:
- /Users/jedgore/dev/asof123/examples/source_status_quotes.json
- /Users/jedgore/dev/asof123/examples/resolve_demo.py
- /Users/jedgore/dev/asof123/examples/snapshot_demo.py
- /Users/jedgore/dev/asof123/docs/quickstart.md
- /Users/jedgore/dev/asof123/tests/test_examples.py
- /Users/jedgore/dev/asof123/docs/examples_quickstart_report.md

Updated:
- /Users/jedgore/dev/asof123/README.md
  - Added a `## Quickstart` section pointing at `docs/quickstart.md`
    and naming the three example artifacts
    (`examples/resolve_demo.py`, `examples/snapshot_demo.py`,
    `examples/source_status_quotes.json`).
  - Replaced the stale `## Status` paragraph with a one-paragraph
    accurate description (library, CLI, FastAPI app, examples
    shipping; no persistence, auth, scheduler, or background
    worker). The original Status text claimed "no package, no API
    server, no CLI, and no tests yet", which directly contradicted
    the current repo. The brief allowed mentioning examples briefly,
    so the corrected Status mentions them in one phrase and points
    at `docs/` for the build history.

No persistence, auth, scheduler, background job, mutable registry,
external integration, database integration, or config system was
introduced.

## Example Behavior

`examples/source_status_quotes.json` is a valid `SourceStatus` payload
for a US-equities quote feed:

- `provider`: `quotes_feed`
- `freshness`: `FRESH`
- `last_update_utc`: `2026-05-12T13:44:58Z`
- `metadata`: `{"row_count": 9421, "symbol_count": 3500, "feed_label":
  "us_equities_consolidated"}`

`metadata` is intentionally small but non-empty so the fixture
demonstrates the `dict[str, Any]` field's role without implying any
schema.

`examples/resolve_demo.py` is the 30-line minimum needed to use the
library end-to-end: it imports `ResolveRequest`, `XNYSCalendar`,
`FileProvider`, and `resolve`, points the FileProvider at the fixture
JSON, builds a LIVE request for `XNYS` / `America/New_York`, calls
`resolve`, and prints the resulting `TemporalContext` as pretty
JSON sorted by key. No argparse, no network, no environment loading.

`examples/snapshot_demo.py` is the same flow with a single extra step:
`snapshot = make_snapshot(context, snapshot_id="demo_snapshot")`, then
prints the snapshot. The snapshot's `content_hash` is a deterministic
SHA256 over the canonical JSON of the context.

Both scripts resolve their fixture path via
`Path(__file__).resolve().parent / "source_status_quotes.json"` so
they work regardless of the current working directory, including when
invoked via `runpy` from inside pytest.

## Quickstart Coverage

`docs/quickstart.md` walks through:

- The mental model: "External systems report facts. asof123 resolves
  temporal meaning." Plus a short note that the only IO in the repo
  is the `FileProvider` reading a local JSON file.
- Install: `pip install -e ".[dev]"` (full dev stack),
  `pip install -e .` (library only), `pip install -e ".[serve]"`
  (HTTP without test stack).
- Tests: `python -m pytest -q`.
- CLI: `asof123 resolve`, `asof123 resolve ... --source-file ...`,
  `asof123 snapshot ...`, with a note on strict UTC datetime parsing.
- Example scripts: `python examples/resolve_demo.py` and
  `python examples/snapshot_demo.py`, with a one-line description of
  each.
- Optional HTTP: `pip install -e ".[serve]"`, `asof123 serve`, and a
  bullet list of the five endpoints (including the deliberate 501
  on `POST /sources/report`).
- Where to go next: `PRODUCT_CONTRACT.md`, `README.md`, `docs/`,
  `examples/`.

The brief required that the quickstart contain `asof123 resolve`,
`asof123 snapshot`, `asof123 serve`, `examples/resolve_demo.py`,
`examples/snapshot_demo.py`. All five strings are present and tested
by `test_quickstart_md_contains_key_commands_and_example_paths`.

## Tests Added

`tests/test_examples.py` (4 tests):

- `test_source_status_quotes_json_validates_via_file_provider`:
  Constructs a `FileProvider("quotes_feed",
  examples/source_status_quotes.json)` and calls `report(now)`.
  Asserts the parsed `SourceStatus` has the expected `provider`,
  `freshness`, a UTC `last_update_utc`, and `metadata` containing
  `row_count` and `symbol_count`.
- `test_resolve_demo_runs_and_emits_valid_temporal_context_json`:
  Runs `examples/resolve_demo.py` via `runpy.run_path(...,
  run_name="__main__")`, captures stdout with `capsys`, parses the
  JSON, and asserts `market=XNYS`, `market_timezone=America/New_York`,
  `perspective=LIVE`, and the `quotes_feed` source appearing in
  `sources` with `freshness=FRESH`.
- `test_snapshot_demo_runs_and_emits_snapshot_json`: Runs
  `examples/snapshot_demo.py` the same way, asserts
  `snapshot_id="demo_snapshot"`, a 64-character hex `content_hash`, a
  UTC `captured_at_utc`, and an embedded `context.market=XNYS`.
- `test_quickstart_md_contains_key_commands_and_example_paths`:
  Reads `docs/quickstart.md` and asserts the five required strings
  plus `pip install -e` are present.

`runpy.run_path(..., run_name="__main__")` was preferred over
`subprocess` because it avoids spawning a new interpreter, keeps the
test in-process, and lets `capsys` capture stdout directly. The
demos' `if __name__ == "__main__":` blocks execute as expected under
this entry mode.

Total project test count: 146 passed (142 prior + 4 new).

## Validation Commands Run

1. `python -m py_compile examples/resolve_demo.py
   examples/snapshot_demo.py tests/test_examples.py`
   Result: clean.

2. `python -m pytest -q`
   Result: 146 passed in 0.22s.

3. `LC_ALL=C grep -rnP '[^\x00-\x7F]' examples/ docs/quickstart.md
   tests/test_examples.py README.md`
   Result: no matches (exit 1).

4. `git diff --check`
   Result: clean (exit 0).

## Assumptions Made

- The example fixture's `last_update_utc` is fixed at
  `2026-05-12T13:44:58Z`. Using a fixed past instant rather than a
  template token (`{{ now }}`) keeps the JSON file directly loadable
  by `FileProvider` without templating, and makes the fixture
  deterministic across test runs. The fixture's "FRESH" label is a
  fact the fixture asserts; whether that "FRESH" is appropriate for
  a real wall-clock now is a downstream decision for callers, not
  this demo's concern.
- The demo scripts use `LIVE` perspective with no pinned UTC, so the
  resolver fills `now_utc` from `datetime.now(timezone.utc)`. The
  tests assert structural fields (`market`, `perspective`,
  `sources["quotes_feed"]`) rather than time-dependent fields
  (`market_phase`, `price_basis`), so they pass at any time of day.
- The README's `Status` paragraph was rewritten rather than appended
  to. The brief allowed mentioning examples briefly and linking to
  the quickstart; leaving the stale "no package, no API server, no
  CLI" paragraph in place would have created a self-contradicting
  README. The rewritten paragraph is one short sentence longer than
  the original and contains nothing the brief did not authorize.
- The quickstart uses `\` for shell line continuations in the
  multi-line CLI examples. ASCII only, no unicode line-continuation
  characters.
- `runpy.run_path` was chosen over `subprocess.run([sys.executable,
  path])` because the test runner already has `src/` on
  `pythonpath` via `[tool.pytest.ini_options]`. A subprocess would
  need either an editable install or an explicit `PYTHONPATH`
  environment variable; `runpy` inherits the parent process's
  `sys.path`, which is what we want.

## Recommended Next Step

The repository now has a contract, a library, a CLI, an HTTP surface,
and runnable demos. The natural next pass is to put a second concrete
provider behind the file-based one, so the open-source core can
demonstrate a non-file source without yet introducing real network
IO. In order:

1. `src/asof123/providers/postgres.py`: a `PostgresFreshnessProvider`
   that takes a SQL query and a DSN, runs the query with `psycopg`
   (or `psycopg2`), and converts a single-row `(last_update_utc,
   row_count)` result into a `SourceStatus`. Strict UTC validation
   on the returned timestamp. Fail-closed translation of any
   driver-level exception into `ProviderReportError`.
2. Add `postgres = ["psycopg[binary]>=3.1"]` to
   `[project.optional-dependencies]`, never to the core. The HTTP
   and CLI surfaces should keep working without psycopg installed.
3. `tests/test_postgres_provider.py`: drive the provider against a
   stub connection object (no real Postgres). The test fakes a
   cursor that returns the canned tuple and asserts the resulting
   `SourceStatus`.
4. `examples/postgres_demo.py`: a short script with a clear DSN
   placeholder and a comment explaining that a real DSN is required
   to run it. The example must not run by default in tests.
5. Add a one-paragraph section to `docs/quickstart.md` explaining
   the optional `postgres` extra and pointing at the example.

Still out of scope for the next pass: scheduling, retries, async
drivers, connection pooling beyond the provider's own session, auth,
multi-tenant configuration, and any persistence of snapshots or
contexts.
