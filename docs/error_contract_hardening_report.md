# Error Contract Hardening Report

Date: 2026-05-15

`docs/unified_diff.md` does not exist and was not created.

## Changed Files

- `PRODUCT_CONTRACT.md`
- `src/asof123/errors.py`
- `src/asof123/resolver.py`
- `src/asof123/api.py`
- `src/asof123/cli.py`
- `src/asof123/__init__.py`
- `tests/test_resolver.py`
- `tests/test_api.py`
- `tests/test_cli.py`
- `docs/api_reference_surface_report.md`
- `docs/cli_reference_report.md`
- `docs/runtime_contract_audit.md`
- `docs/error_contract_hardening_audit.md`
- `docs/error_contract_hardening_report.md`

## Runtime Hardening Changes

Added `ErrorReasonCode`, a pinned machine-readable reason-code enum for
public failure identity.

Added `ErrorResponse`, a stable JSON error payload model with:

- `error`
- `reason_code`
- `explanation`
- optional `message`
- optional `details`

Updated `ResolverError` to carry:

- `reason_code`
- `explanation`

while preserving string form as `REASON_CODE: explanation`.

Updated API error surfaces:

- resolver failures now include explicit `reason_code` and `explanation`;
- request validation failures now use structured
  `error=VALIDATION_ERROR`, `reason_code=VALIDATION_ERROR`;
- duplicate provider names expose `reason_code=DUPLICATE_PROVIDER_NAME`;
- read-only source reporting exposes `reason_code=NOT_IMPLEMENTED`.

Updated CLI runtime failures to write structured JSON to stderr for request
validation, provider construction, resolver failures, snapshot validation,
and missing serve dependency.

## Behavior Intentionally Left Unchanged

No persistence was added.
No replay engine was added.
No database or storage layer was added.
No scheduler or background job was added.
No external integration was added.
No canonical authority was added.
No broad exception hierarchy was added.

Provider failures still become data-bearing `SourceStatus` values with
`freshness=FAILED`; they are not process-fatal after reaching the resolver.

CLI exit code semantics remain unchanged: `0` for success and `2` for
validation, resolver, local runtime, or invocation failure.

## Tests Added Or Tightened

Targeted tests now assert:

- `ResolverError.reason_code` and `ResolverError.explanation`;
- API validation errors expose `reason_code=VALIDATION_ERROR`;
- API resolver failures expose specific reason codes;
- API duplicate provider and not-implemented responses expose reason codes;
- CLI resolver and validation failures write parseable JSON stderr with
  stable reason codes.

## Validation Results

Commands run:

- `python -m pytest tests/test_resolver.py tests/test_api.py tests/test_cli.py -q`
- `python -m pytest -q`
- `rg -n "ResolverError|reason_code|explanation|FAILED|UNKNOWN|HTTPException|stderr|exit" PRODUCT_CONTRACT.md README.md docs src tests`
- `git diff --check`
- `LC_ALL=C rg -n "[^\\x00-\\x7F]" --glob '*.md'`

Results:

- Targeted resolver/API/CLI tests passed: 42 passed.
- Full test suite passed: 165 passed.
- Targeted grep found expected resolver error, reason code, explanation,
  FAILED/UNKNOWN, stderr, and exit references.
- `git diff --check` passed.
- Markdown ASCII check passed with no matches.

## HOLD / WARNING / NOTE Table

| Level | Finding | Status |
| --- | --- | --- |
| WARNING | Argparse syntax errors still use conventional argparse stderr before command dispatch. | Acceptable for current reference CLI; future hardening if every invalid CLI invocation must be JSON. |
| WARNING | Validation `details` is advisory and follows framework structure. | Stable control flow must use `reason_code`. |
| NOTE | API and CLI no longer require parsing English prose for resolver failures. | `reason_code` is explicit. |

## Final Verdict

PASS WITH WARNINGS.

The error contract is now explicit, typed, and pinned for current resolver,
API, CLI, provider, and snapshot surfaces. Remaining warnings are future
interface-hardening items, not current fail-closed semantic risks.
