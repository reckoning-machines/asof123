# Stale Quotes

## Problem

Execution scripts, dashboards, and notebooks often need the same quote
freshness check:

```text
quotes must exist and must be no older than N seconds
```

When every caller writes that logic locally, stale and missing quote behavior
diverges.

## Code People Usually Write

```python
if "quotes" not in sources:
    raise RuntimeError("missing quotes")

age = (now_utc - quotes_timestamp_utc).total_seconds()
if age > 5:
    raise RuntimeError("stale quotes")
```

## asof123 Replacement

```python
from datetime import datetime, timezone

from asof123 import (
    Perspective,
    SourceFreshness,
    SourcePolicy,
    SourceStatus,
    apply_source_policy,
)

now = datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc)

sources = {
    "quotes": SourceStatus(
        provider="quotes",
        freshness=SourceFreshness.FRESH,
        timestamp_utc=datetime(2026, 5, 12, 13, 59, 50, tzinfo=timezone.utc),
        timestamp_name="vendor_updated_at",
    )
}

checked = apply_source_policy(
    perspective=Perspective.PRE_TRADE_INTENT,
    knowledge_cutoff_utc=now,
    now_utc=now,
    sources=sources,
    policy=SourcePolicy(
        required_sources={"quotes"},
        max_age_seconds_by_source={"quotes": 5},
    ),
)

print(checked["quotes"].freshness)
print(checked["quotes"].reason_code)
```

CLI:

```bash
asof123 resolve \
  --perspective PRE_TRADE_INTENT \
  --market XNYS \
  --market-timezone America/New_York \
  --as-of-utc 2026-05-12T14:00:00Z \
  --source-file quotes=examples/source_status_quotes.json \
  --required-source quotes \
  --max-age-source quotes=5
```

File-backed Python integration:

```python
from asof123 import FileProvider

quotes = FileProvider("quotes", "examples/source_status_quotes.json")
asof = resolve(
    request,
    calendars={"XNYS": XNYSCalendar()},
    providers=[quotes],
    policy=SourcePolicy(required_sources={"quotes"}, max_age_seconds=5),
)
```

## What The Result Means

`SourcePolicy` makes missing quotes explicit as `MISSING` and old quotes
explicit as `STALE`. Provider failures remain `FAILED`. The result is a
source map with auditable `SourceStatus` values instead of local exceptions
with incompatible names.

## What asof123 Does Not Do

asof123 does not subscribe to market data, fetch quotes, run a quote cache,
route orders, or retry failed feeds. External systems report quote facts
through `SourceStatus`; asof123 applies the temporal policy.
