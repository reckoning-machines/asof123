# asof123 Quickstart

Get from `git clone` to a resolved `TemporalContext` in under a minute.

## The mental model

External systems report facts.
asof123 resolves temporal meaning.

Every example below uses a `FileProvider` as the simplest hook for an
external fact. There is no persistence, no auth, no scheduler, and no
background worker in this repo; the only IO is the JSON file the
`FileProvider` reads.

## Install

Editable install with dev extras:

    pip install -e ".[dev]"

This pulls in Pydantic plus the test and API extras (`fastapi`,
`httpx`, `pytest`, `uvicorn`). For library-only use, `pip install -e .`
is enough; for HTTP serving without the test stack, use
`pip install -e ".[serve]"`.

## Run the tests

    python -m pytest -q

You should see every test pass.

## Use the CLI

Resolve a LIVE `TemporalContext` for US equities:

    asof123 resolve --perspective LIVE

Resolve and include a source feed via a local JSON file:

    asof123 resolve \
        --perspective LIVE \
        --source-file quotes_feed=examples/source_status_quotes.json

Create a replay-safe snapshot of the resolved context:

    asof123 snapshot \
        --snapshot-id demo \
        --perspective LIVE \
        --source-file quotes_feed=examples/source_status_quotes.json

Datetime arguments are strict: `--as-of-utc` and
`--knowledge-cutoff-utc` must be ISO 8601 with a UTC offset (`Z` or
`+00:00`). Naive datetimes and non-UTC offsets are rejected at
argparse time.

## Run the example scripts

The examples take no arguments and print JSON to stdout:

    python examples/resolve_demo.py
    python examples/snapshot_demo.py

`examples/resolve_demo.py` resolves a LIVE `TemporalContext` with a
single `FileProvider` pointed at `examples/source_status_quotes.json`.
`examples/snapshot_demo.py` does the same and wraps the result in an
`AsOfSnapshot` with `snapshot_id="demo_snapshot"`. Both scripts are
intentionally short; they are the smallest possible end-to-end use of
the library.

## Optional: serve the FastAPI reference app

The HTTP surface is an optional extra. To run it:

    pip install -e ".[serve]"
    asof123 serve --host 127.0.0.1 --port 8000

That exposes the endpoints from `PRODUCT_CONTRACT.md` section 14:

- `GET  /asof/current`
- `POST /asof/resolve`
- `GET  /sources/status`
- `POST /sources/report` (returns 501; the reference app is read-only)
- `POST /asof/snapshot`

The serve mode loads no environment variables, opens no databases, and
holds no mutable state beyond the calendars and providers handed to
`create_app(...)` at construction time.

## Where to go next

- `PRODUCT_CONTRACT.md` is the canonical contract. The locked
  enumerations and the fail-closed rules live there.
- `README.md` explains the problem space and lists the concrete bugs
  this layer exists to prevent.
- `docs/` contains a chronological set of design reports, one per
  build pass. Read them in order if you want to see how the codebase
  was put together.
- `examples/` contains the small fixtures and scripts referenced
  above.
