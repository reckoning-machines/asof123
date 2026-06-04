# asof123 Recipes

These recipes show practical integration patterns for Wall Street data
scientists, quant researchers, ETL engineers, and execution engineers.

The goal is simple: replace local time-state checks with `asof123` primitives.

`asof123` does not fetch proprietary data, schedule jobs, run workflows, store
your warehouse, operate an OMS/EMS/PMS, route orders, or talk to brokers. It
resolves temporal meaning from facts your systems already report.

## Recipes

- [Business Date](business_date.md): stop guessing whether "today" is the
  calendar date or market business date.
- [Market Phase](market_phase.md): resolve pre-open, market open, post-close,
  weekend, holiday, or closed using the calendar boundary.
- [Stale Quotes](stale_quotes.md): make quote freshness checks explicit with
  `SourcePolicy`.
- [Replay Safety](replay_safety.md): prevent replay and historical reads from
  seeing future source updates.
- [Canonical Close](canonical_close.md): fail closed unless supplied official
  close publication facts prove a canonical read.
- [Pre-Trade Checks](pre_trade_checks.md): use existing source policy primitives
  for quote, locate, and basket-file readiness.
- [Snapshot Audit](snapshot_audit.md): create deterministic audit identity for a
  resolved AsOf.

## Public APIs Used

The recipes use existing public APIs only:

- `AsOfRequest`
- `AsOf`
- `AsOfSnapshot`
- `resolve`
- `SourcePolicy`
- `apply_source_policy`
- `StaticProvider`
- `FileProvider`
- `make_snapshot`
- CLI `resolve` and `snapshot`
- API `/asof/resolve` wrapper with optional `policy`
