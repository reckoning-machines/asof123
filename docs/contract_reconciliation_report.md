# Contract Reconciliation Report

Date: 2026-05-15

`docs/unified_diff.md` does not exist and was not created.

## Changed Files

- `PRODUCT_CONTRACT.md`
- `README.md`
- `docs/api_reference_surface_report.md`
- `src/asof123/__init__.py`
- `docs/contract_reconciliation_report.md`

## What Contract Drift Was Repaired

- Removed current normative pass-language from the canonical contract:
  `No code is written in this pass`, `No application scaffolding is created
  in this pass`, and the claim that the API endpoints are not implemented.
- Replaced the README seed section with a README relationship section that
  keeps README subordinate to `PRODUCT_CONTRACT.md`.
- Added `Implemented Reference Surfaces` to acknowledge the existing
  standalone repository surfaces: Python package, enums, models, request
  models, minimal resolver, SourceProvider protocol, static provider, file
  provider, snapshot helper, XNYS reference calendar, FastAPI reference app,
  CLI, examples, and tests.
- Preserved the negative scope: asof123 is not a scheduler, orchestrator,
  warehouse, temporal database, OMS/PMS, broker adapter, proprietary
  warehouse integration, or internal fund system.
- Updated README's Python example to use the current public package surface
  and to pass `market_timezone` explicitly.
- Changed README open-source boundary wording from "ships with" to "may
  include" so unimplemented future surfaces such as a simple Postgres
  freshness provider are not claimed as current.
- Removed non-ASCII em dashes from `docs/api_reference_surface_report.md`.
- Updated the package docstring in `src/asof123/__init__.py` so it no longer
  says the package ships no FastAPI app or CLI.

## What Behavior Was Intentionally Left Unchanged

- No resolver, provider, API, CLI, calendar, snapshot, model, enum, example,
  or test behavior was changed.
- CLI convenience defaults remain unchanged.
- `GET /asof/current` convenience defaults remain unchanged.
- Unknown market still raises `ResolverError` in the core Python resolver.
- API handling of `ResolverError` remains unchanged.
- `POST /sources/report` remains a read-only reference-app endpoint that
  returns HTTP 501.

## Default Behavior Decision

The smallest coherent choice was documentation-only reconciliation:

- Core public models and resolver request models must require
  `market`, `market_timezone`, and `perspective`.
- The core resolver must not silently assume a default market, timezone, or
  perspective for an underspecified request.
- CLI and reference HTTP app defaults are explicitly classified as
  documented reference-surface conveniences, not core resolver semantics.
- Those defaults still pass through the same request validation as explicit
  caller input.

## Current-Time Behavior Decision

The contract now distinguishes explicit current-context resolution from a
forbidden silent wall-clock fallback:

- `GET /asof/current` and current-oriented requests such as LIVE with no
  `as_of_utc` may use `datetime.now(timezone.utc)`.
- REPLAY and HISTORICAL requests must provide `as_of_utc` and
  `knowledge_cutoff_utc`.
- CANONICAL requests must resolve against canonical publication semantics,
  not an arbitrary wall-clock fallback.

## Unknown-Market Fail-Closed Decision

The contract now accepts the current core behavior:

- Unknown market may fail closed by raising a typed `ResolverError`.
- API and CLI surfaces must translate that error into an explicit failed
  response or process error with a machine-readable reason and
  human-readable explanation.
- This preserves fail-closed behavior without changing runtime code.

## Validation Results

Commands run:

- `rg --files`
- `git diff --check`
- `LC_ALL=C rg -n "[^\\x00-\\x7F]" --glob '*.md'`
- `python -m pytest -q`
- `rg -n "not yet implemented|No code is written|No application scaffolding|default market|wall-clock|fallback|fall back|ResolverError|UNKNOWN|CLOSED" PRODUCT_CONTRACT.md README.md docs src tests examples`

Results:

- `rg --files` completed and showed the expected standalone repository
  files.
- `git diff --check` passed.
- Markdown non-ASCII search passed with no matches.
- `python -m pytest -q` passed: 146 passed in 0.22s.
- Targeted grep found no remaining current normative pass-language in
  `PRODUCT_CONTRACT.md`.
- Targeted grep still finds historical mentions in
  `docs/standalone_repo_contract_audit.md`, expected enum values such as
  `UNKNOWN` and `CLOSED`, expected `ResolverError` code/tests/docs, and the
  clarified contract language for default market, wall-clock, and fallback.

## Remaining HOLD / WARNING / NOTE Table

| Level | Finding | Status |
| --- | --- | --- |
| NOTE | Historical audit report still contains the old HOLD text it recorded. | Expected; audit reports are historical artifacts, not current contract. |
| NOTE | CLI and `GET /asof/current` keep convenience defaults. | Contract now classifies these as reference-surface conveniences, not core resolver semantics. |
| NOTE | Unknown market raises `ResolverError` in the core resolver. | Contract now documents this as an accepted fail-closed mechanism. |
| NOTE | `POST /sources/report` returns HTTP 501. | Behavior intentionally left unchanged because the reference app remains read-only. |

## Final Verdict

PASS.

The canonical contract now matches the current standalone repository shape
without broadening product scope or changing runtime behavior.
