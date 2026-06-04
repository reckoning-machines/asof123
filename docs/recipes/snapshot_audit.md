# Snapshot Audit

## Problem

Reports, replay jobs, and model runs need an audit identity for the resolved
AsOf they used. Without a common snapshot helper, teams usually hash ad hoc
JSON or store incomplete as-of fields.

## Code People Usually Write

```python
payload = {
    "business_date": str(business_date),
    "phase": phase,
    "sources": sources,
}
content_hash = hashlib.sha256(json.dumps(payload).encode()).hexdigest()
```

That often misses schema version, semantic contract version, UTC normalization,
or nested metadata determinism.

## asof123 Replacement

```python
from datetime import datetime, timezone

from asof123 import AsOfRequest, XNYSCalendar, make_snapshot, resolve

asof = resolve(
    AsOfRequest(
        perspective="PRE_TRADE_INTENT",
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc),
    ),
    calendars={"XNYS": XNYSCalendar()},
)

snapshot = make_snapshot(asof, snapshot_id="intent-2026-05-12T14:00:00Z")

print(snapshot.snapshot_schema_version)
print(snapshot.semantic_contract_version)
print(snapshot.content_hash)
```

CLI:

```bash
asof123 snapshot \
  --snapshot-id intent-2026-05-12T14:00:00Z \
  --perspective PRE_TRADE_INTENT \
  --market XNYS \
  --market-timezone America/New_York \
  --as-of-utc 2026-05-12T14:00:00Z
```

## What The Result Means

`make_snapshot()` produces an `AsOfSnapshot` with a deterministic content hash
over the semantic payload: schema version, semantic contract version, and the
resolved `AsOf`. Audit-only fields such as `snapshot_id` and
`captured_at_utc` do not change the content hash.

## What asof123 Does Not Do

asof123 does not persist snapshots, run a replay engine, store warehouse rows,
or guarantee production data retention. It gives callers a deterministic audit
artifact they can store in their own systems.
