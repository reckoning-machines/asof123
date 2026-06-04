# Pre-Trade Checks

## Problem

Execution engineers often repeat pre-trade readiness checks across scripts and
tools:

```python
if market_open and quotes_fresh and locates_ready and basket_file_ready:
    build_order_file()
```

The execution platform still owns orders. The duplicated part is temporal
admissibility over required facts.

## Code People Usually Write

```python
if not quotes:
    raise RuntimeError("missing quotes")
if quote_age_seconds > 5:
    raise RuntimeError("stale quotes")
if not locates:
    raise RuntimeError("missing locates")
if not basket_file:
    raise RuntimeError("basket file missing")
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
        timestamp_utc=datetime(2026, 5, 12, 13, 59, 58, tzinfo=timezone.utc),
        timestamp_name="vendor_updated_at",
    ),
    "locates": SourceStatus(
        provider="locates",
        freshness=SourceFreshness.FRESH,
        timestamp_utc=datetime(2026, 5, 12, 13, 55, 0, tzinfo=timezone.utc),
        timestamp_name="publication_time",
    ),
    "basket_file": SourceStatus(
        provider="basket_file",
        freshness=SourceFreshness.FRESH,
        timestamp_utc=datetime(2026, 5, 12, 13, 58, 0, tzinfo=timezone.utc),
        timestamp_name="file_timestamp",
    ),
}

checked = apply_source_policy(
    perspective=Perspective.PRE_TRADE_INTENT,
    knowledge_cutoff_utc=now,
    now_utc=now,
    sources=sources,
    policy=SourcePolicy(
        required_sources={"quotes", "locates", "basket_file"},
        max_age_seconds_by_source={
            "quotes": 5,
            "locates": 900,
            "basket_file": 300,
        },
    ),
)
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
  --required-source locates \
  --required-source basket_file \
  --max-age-source quotes=5 \
  --max-age-source locates=900 \
  --max-age-source basket_file=300
```

## What The Result Means

The checked source map makes missing, stale, failed, and not-published facts
explicit. This is useful before building an intent view, sizing trades, or
handing facts to an execution system.

## What asof123 Does Not Do

asof123 does not send orders, manage child orders, fetch locates, generate
basket files, upload files, route orders, calculate positions, or operate an
OMS/EMS/PMS. It only resolves the temporal meaning of facts supplied by those
systems.
