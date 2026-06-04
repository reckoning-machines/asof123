# UTC Everywhere, ET Nowhere

## Problem

Institutional systems should move machine instants in UTC. Human readers often
want New York market time, but `EST` is not safe as an input because it is an
abbreviation, not an IANA timezone rule.

The institutional problem is not one conversion. It is the same conversion
being copied into Python jobs, SQL transforms, dashboards, browser components,
and report generators until each system has a slightly different answer.

## Code People Usually Write

```python
as_of = "2026-05-12 10:00 EST"
business_date = as_of[:10]
```

```python
local_now = utc_now.astimezone(ZoneInfo("America/New_York"))
```

```sql
SELECT resolved_at_utc AT TIME ZONE 'America/New_York' AS local_time
FROM runs;
```

```js
const local = new Date(resolved_atUtc).toLocaleString("en-US", {
  timeZone: "America/New_York"
});
```

That mixes storage, interpretation, and display. It also breaks across daylight
saving time because New York market time is not always UTC-5.

## asof123 Replacement

```python
from datetime import datetime, timezone

from asof123 import AsOfRequest, XNYSCalendar, resolve

asof = resolve(
    AsOfRequest(
        perspective="PRE_TRADE_INTENT",
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc),
    ),
    calendars={"XNYS": XNYSCalendar()},
)

print(asof.resolved_at_utc)
print(asof.market_timezone)
print(asof.market_datetime)
print(asof.market_date)
print(asof.business_date)
```

CLI:

```bash
asof123 resolve \
  --perspective PRE_TRADE_INTENT \
  --market XNYS \
  --market-timezone America/New_York \
  --as-of-utc 2026-05-12T14:00:00Z
```

## What The Result Means

`resolved_at_utc` is the machine instant. `market_timezone` is the IANA timezone
used for market interpretation. `market_datetime` and `market_date` are
convenience projections derived from `resolved_at_utc` and `market_timezone`.

Store UTC. Transport UTC. Audit UTC. Ask `AsOf` for market-time meaning.

`market_datetime` is not a separate authority. Business logic should use the
resolved fields such as `business_date`, `market_phase`, `price_basis`,
`publication_state`, and `canonical_state`.

## What asof123 Does Not Do

asof123 does not accept `EST` as `market_timezone`, does not infer a market from
local machine time, and does not turn display labels into timezone rules. For
XNYS, pass `America/New_York`.
