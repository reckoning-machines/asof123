# Replay Safety

## Problem

Backtests, research notebooks, postmortems, and replay jobs must answer:

```text
What was knowable then?
```

The common failure mode is using a source update that arrived after the replay
cutoff.

## Code People Usually Write

```python
if source_last_update_utc > knowledge_cutoff_utc:
    usable = False
else:
    usable = True
```

Every job then invents a different error, flag, or fallback.

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

cutoff = datetime(2026, 2, 10, 21, 0, 0, tzinfo=timezone.utc)

sources = {
    "warehouse": SourceStatus(
        provider="warehouse",
        freshness=SourceFreshness.FRESH,
        last_update_utc=datetime(2026, 2, 11, 1, 0, 0, tzinfo=timezone.utc),
    )
}

checked = apply_source_policy(
    perspective=Perspective.REPLAY,
    knowledge_cutoff_utc=cutoff,
    now_utc=cutoff,
    sources=sources,
    policy=SourcePolicy(required_sources={"warehouse"}),
)

assert checked["warehouse"].freshness == "NOT_PUBLISHED"
assert checked["warehouse"].reason_code == "SOURCE_NOT_ADMISSIBLE"
```

API:

```json
{
  "request": {
    "perspective": "REPLAY",
    "market": "XNYS",
    "market_timezone": "America/New_York",
    "as_of_utc": "2026-02-10T21:00:00Z",
    "knowledge_cutoff_utc": "2026-02-10T21:00:00Z"
  },
  "policy": {
    "required_sources": ["warehouse"],
    "max_age_seconds": 3600
  }
}
```

## What The Result Means

For `REPLAY` and `HISTORICAL`, `SourcePolicy` marks a source as
`NOT_PUBLISHED` when `last_update_utc` is after `knowledge_cutoff_utc`. Equality
at the cutoff is admissible. This pins replay safety without building a replay
engine.

## What asof123 Does Not Do

asof123 does not store historical data, run backtests, persist replay sessions,
or reconstruct arbitrary warehouse state. It evaluates the source facts and
cutoff timestamps supplied by the caller.

