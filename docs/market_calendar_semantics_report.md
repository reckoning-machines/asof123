# Market Calendar Semantics Report

Date: 2026-05-15

`docs/unified_diff.md` exists and was updated.

## Changed Files

- `PRODUCT_CONTRACT.md`
- `src/asof123/calendars/xnys.py`
- `tests/test_calendar.py`
- `docs/market_calendar_semantics_contract.md`
- `docs/market_calendar_semantics_report.md`
- `docs/minimal_resolver_report.md`
- `docs/runtime_contract_audit.md`
- `docs/calendar_provider_timezone_freeze_contract.md`
- `docs/product_contract_report.md`
- `docs/unified_diff.md`

## Runtime Hardening Changes

`XNYSCalendar` now fails closed as `CLOSED` for:

- dates outside the supported 2025-2026 holiday years;
- known unsupported XNYS early-close dates inside the supported range.

This prevents the minimal reference calendar from silently applying regular
09:30-16:00 session semantics to dates it explicitly does not model safely.

No new markets were added.
No exchange integration was added.
No live calendar download was added.
No persistence or replay engine was added.
No scheduler or background job was added.
No fin123 integration was added.

## Tests Added

Calendar tests now assert:

- a known unsupported early-close date returns `CLOSED`;
- a date outside the supported holiday years returns `CLOSED`.

## Behavior Intentionally Left Unsupported

The current XNYS reference calendar still does not model:

- shortened early-close sessions;
- half days;
- emergency closures;
- ad hoc halts;
- unscheduled holidays;
- full NYSE holiday coverage outside the hard-coded range;
- pre-market or after-hours sessions;
- production exchange calendar authority.

## Validation Results

Commands run:

- `python -m pytest tests/test_calendar.py -q`
- `python -m pytest -q`
- `rg -n "XNYS|ZoneInfo|MARKET_OPEN|PRE_OPEN|CLOSED|holiday|timezone|business_date|calendar_version" PRODUCT_CONTRACT.md README.md docs src tests`
- `git diff --check`
- `LC_ALL=C rg -n "[^\\x00-\\x7F]" --glob '*.md'`

Results:

- Targeted calendar tests passed: 15 passed.
- Full test suite passed: 167 passed.
- Targeted grep found expected XNYS, ZoneInfo, phase, holiday, timezone,
  business_date, and calendar_version references.
- `git diff --check` passed.
- Markdown ASCII check passed with no matches.

## HOLD / WARNING / NOTE Table

| Level | Finding | Status |
| --- | --- | --- |
| WARNING | XNYS remains minimal and non-production. | Explicitly documented; no exchange authority is claimed. |
| WARNING | Calendar version and tzdata metadata are deferred. | Required before persisted replay. |
| WARNING | Early closes fail closed instead of being modeled as shortened sessions. | Safe minimal behavior; future production calendar must version early-close rules. |
| NOTE | Unsupported future years now return `CLOSED`. | Prevents silent holiday approximation outside the supported range. |

## Final Verdict

PASS WITH WARNINGS.

The market calendar semantics are now explicit, and the minimal XNYS calendar
fails closed for unsupported future years and known unsupported early-close
dates. Remaining warnings are intentional limitations, not current semantic
corruption risks.
