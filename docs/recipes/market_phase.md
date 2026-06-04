# Market Phase

## Problem

Trading tools and dashboards repeatedly ask whether the market is pre-open,
open, post-close, or closed. That logic is easy to duplicate incorrectly across
timezones and batch environments.

## Code People Usually Write

```python
local_now = utc_now.astimezone(ZoneInfo("America/New_York"))

if local_now.weekday() >= 5:
    phase = "closed"
elif local_now.time() < time(9, 30):
    phase = "pre_open"
elif local_now.time() < time(16, 0):
    phase = "open"
else:
    phase = "post_close"
```

## asof123 Replacement

```python
from datetime import datetime, timezone

from asof123 import ResolveRequest, XNYSCalendar, resolve

ctx = resolve(
    ResolveRequest(
        perspective="LIVE",
        market="XNYS",
        market_timezone="America/New_York",
    ),
    calendars={"XNYS": XNYSCalendar()},
)

if ctx.market_phase != "MARKET_OPEN":
    raise RuntimeError(f"Not a market-open context: {ctx.market_phase}")
```

Pinned-time test or replay-style check:

```python
ctx = resolve(
    ResolveRequest(
        perspective="PRE_TRADE_INTENT",
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc),
    ),
    calendars={"XNYS": XNYSCalendar()},
)
```

## What The Result Means

`ctx.market_phase` is resolved by the supplied calendar. Downstream code can
branch on the contract value `MARKET_OPEN` instead of reimplementing local
timezone and session logic.

## What asof123 Does Not Do

asof123 does not send orders, start jobs when the market opens, poll exchanges,
or manage early-close production coverage. It resolves the phase from a
calendar object supplied to the resolver.

