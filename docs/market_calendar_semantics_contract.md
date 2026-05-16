# Market Calendar Semantics Contract

Date: 2026-05-15

This document is contract-derived from `PRODUCT_CONTRACT.md`. If it ever
disagrees with `PRODUCT_CONTRACT.md`, the product contract wins and this
document must be corrected.

`docs/unified_diff.md` exists and was updated.

## Current XNYS Guarantees

The current `XNYSCalendar` is a minimal deterministic reference calendar. It
guarantees:

- `market = "XNYS"`;
- `market_timezone = "America/New_York"`;
- all calendar method inputs must be timezone-aware UTC;
- conversion from UTC to market time uses `ZoneInfo("America/New_York")`;
- `business_date_for()` returns the local calendar date in the market
  timezone, with no roll-forward or roll-back on weekends or holidays;
- weekends are recognized from the local market date;
- a fixed 2025-2026 holiday set is recognized;
- regular-session weekday phase boundaries are deterministic;
- DST behavior is deterministic for the same UTC instant and runtime timezone
  database.

Regular-session phase boundaries:

- before 09:30 ET: `PRE_OPEN`;
- 09:30 ET inclusive until before 16:00 ET: `MARKET_OPEN`;
- 16:00 ET and later: `POST_CLOSE`.

The current calendar is intentionally not a full exchange calendar and is not
production NYSE trading calendar authority.

## Unsupported-Condition Policy

Unsupported conditions include:

- early closes;
- half days;
- emergency exchange closures;
- ad hoc market halts;
- unscheduled holidays;
- holidays outside the hard-coded supported years;
- pre-market trading sessions;
- after-hours trading sessions;
- timezone database drift.

Current XNYS unsupported-condition behavior:

- known unsupported early-close dates return `CLOSED`;
- dates outside the supported 2025-2026 holiday years return `CLOSED`;
- unknown markets fail closed through the resolver with typed
  `ResolverError`;
- calendar market or timezone mismatch fails closed through the resolver with
  typed `ResolverError`;
- naive or non-UTC datetimes are rejected.

`CLOSED` is the current fail-safe market phase for a known XNYS condition
that the minimal reference calendar cannot safely interpret. The current
`MarketPhase` enum has no `UNKNOWN` value; future richer calendars may use
typed resolver errors or explicit model metadata when a phase cannot be
represented safely.

## Market Phase Semantics

`PRE_OPEN`, `MARKET_OPEN`, and `POST_CLOSE` are regular-session states only.
They do not include pre-market, after-hours, auction, halt, half-day, or
early-close semantics.

Transitions are timezone-safe because UTC inputs are validated before
conversion through `ZoneInfo`. They remain replay-safe only for in-memory
current use; long-lived persisted replay requires calendar and timezone rule
version pins.

`CLOSED` is the fail-safe default when the calendar knows regular-session
rules are unsafe to apply. Weekend and holiday remain more specific closed
states when known.

## Calendar Governance Requirements

Future production-grade calendars must define and pin:

- `calendar_id`;
- `calendar_version`;
- `market`;
- `market_timezone`;
- holiday set version;
- exchange rule version;
- timezone rule version or `tzdata_version`;
- market session version;
- early-close version when early closes are modeled;
- ad hoc closure version when ad hoc closures are modeled.

Any calendar metadata that can alter `business_date`, `market_phase`, session
boundary, or admissibility must be hash-affecting before persisted replay is
allowed.

## Replay-Safe Calendar Policy

Historical replay must preserve original calendar interpretation. It must not
silently change `business_date`, `market_phase`, or session boundary when:

- holiday definitions change;
- tzdata changes;
- exchange sessions evolve;
- early-close tables are added or updated;
- market definitions are renamed or aliased.

Reproduction mode uses the recorded calendar, market, timezone, and rule
versions.

Reinterpretation mode may apply newer calendar or timezone rules only when
the caller explicitly requests reinterpretation and the result is clearly
distinguished from original reproduction.

## Multi-Market Future Safety Rules

Future markets must obey:

- every market must carry an explicit IANA timezone;
- market-relative fields must include market plus market_timezone;
- markets may share calendar implementations only when each market identity
  remains explicit;
- aliases may exist only as explicit mappings with versioned governance;
- no fallback market is allowed;
- no fallback timezone is allowed;
- missing typed calendars fail closed;
- provider data must not infer market phase.

## Future Integration Prohibitions

Future integrations must not:

- silently update holidays in a way that rewrites historical meaning;
- treat the current XNYS reference calendar as full exchange authority;
- fall back from XNAS or any unknown market to XNYS;
- silently reinterpret timezone aliases;
- apply current calendar rules to historical replay without explicit
  reinterpretation;
- infer market phase from provider freshness or price timestamps;
- use mutable runtime calendars in Replay, Run Diff, Audit, or read paths;
- download live calendars inside resolver or replay read paths.

## HOLD / WARNING / NOTE Table

| Level | Finding | Status |
| --- | --- | --- |
| WARNING | XNYS is still a minimal reference calendar, not production exchange authority. | Explicitly documented; future production use needs versioned calendar governance. |
| WARNING | Calendar version and timezone rule metadata are not runtime snapshot fields. | Required before persisted replay, intentionally deferred. |
| WARNING | Known unsupported early-close dates fail closed as `CLOSED`; shortened-session modeling is not implemented. | Safe minimal behavior; future richer calendar must model versions explicitly. |
| NOTE | Dates outside the supported 2025-2026 XNYS holiday range fail closed as `CLOSED`. | Prevents silent future holiday approximation. |
| NOTE | Unknown markets fail closed in the resolver, not in `XNYSCalendar`. | No default-market fallback is allowed. |

## Final Verdict

PASS WITH WARNINGS.

The current calendar is safe as a deterministic minimal reference calendar
with explicit limitations. It is not a production exchange calendar authority,
and future persisted replay remains blocked on calendar and timezone freeze
metadata.
