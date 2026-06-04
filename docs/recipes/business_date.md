# Business Date

## Problem

ETL jobs, notebooks, and daily reports often need the market business date, not
the machine calendar date. Around midnight, weekends, holidays, and pre-open
processing, local code tends to drift.

## Code People Usually Write

```python
today = datetime.now().date()

if today.weekday() >= 5:
    business_date = previous_friday(today)
else:
    business_date = today
```

That code usually grows ad hoc holiday handling, timezone conversion, and
special cases for pre-market jobs.

## asof123 Replacement

```python
from datetime import datetime, timezone

from asof123 import ResolveRequest, XNYSCalendar, resolve

request = ResolveRequest(
    perspective="PRE_TRADE_INTENT",
    market="XNYS",
    market_timezone="America/New_York",
    as_of_utc=datetime(2026, 5, 12, 13, 0, 0, tzinfo=timezone.utc),
)

ctx = resolve(request, calendars={"XNYS": XNYSCalendar()})

print(ctx.business_date)
print(ctx.market_phase)
```

CLI:

```bash
asof123 resolve \
  --perspective PRE_TRADE_INTENT \
  --market XNYS \
  --market-timezone America/New_York \
  --as-of-utc 2026-05-12T13:00:00Z
```

## What The Result Means

`ctx.business_date` is the business date resolved by the supplied market
calendar for the requested UTC instant. `ctx.market_phase` tells the caller
whether the market is pre-open, open, post-close, weekend, holiday, or closed.

The caller gets a validated `TemporalContext` instead of local date booleans.

## What asof123 Does Not Do

asof123 does not run the ETL job, persist the result, schedule the report, or
act as a production exchange-calendar authority. The open-source package ships
a minimal `XNYSCalendar` reference calendar; production-grade holiday coverage
is still a caller responsibility.

