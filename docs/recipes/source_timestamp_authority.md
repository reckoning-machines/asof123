# Source Timestamp Authority

Every source has a different timestamp field. One feed may call it
`vendor_updated_at`, another may call it `publication_time`, and warehouse data
may expose `load_ts` or `warehouse_loaded_at`.

The embarrassingly simple rule is: declare which field is authoritative.

```python
from datetime import datetime, timezone

from asof123 import SourceStatus
from asof123.enums import SourceFreshness

vendor_updated_at = datetime(2026, 5, 12, 13, 44, 58, tzinfo=timezone.utc)
publication_time = datetime(2026, 5, 12, 21, 5, 0, tzinfo=timezone.utc)
load_ts = datetime(2026, 5, 12, 13, 50, 0, tzinfo=timezone.utc)
warehouse_loaded_at = datetime(2026, 5, 12, 13, 55, 0, tzinfo=timezone.utc)

quotes = SourceStatus(
    provider="quotes",
    freshness=SourceFreshness.FRESH,
    timestamp_utc=vendor_updated_at,
    timestamp_name="vendor_updated_at",
)

official_close = SourceStatus(
    provider="official_close",
    freshness=SourceFreshness.FRESH,
    timestamp_utc=publication_time,
    timestamp_name="publication_time",
)

warehouse_load = SourceStatus(
    provider="warehouse_load",
    freshness=SourceFreshness.FRESH,
    timestamp_utc=load_ts,
    timestamp_name="load_ts",
)

warehouse_table = SourceStatus(
    provider="warehouse_table",
    freshness=SourceFreshness.FRESH,
    timestamp_utc=warehouse_loaded_at,
    timestamp_name="warehouse_loaded_at",
)
```

`timestamp_utc` is the timestamp used for freshness and admissibility
evaluation. `timestamp_name` records the source field that produced it.

Freshness policy compares:

```python
now_utc - status.timestamp_utc
```

Replay and historical admissibility compare:

```python
status.timestamp_utc <= knowledge_cutoff_utc
```

asof123 does not decide whether `vendor_updated_at`, `publication_time`,
`load_ts`, or `warehouse_loaded_at` is the correct timestamp for your source.
It makes the choice visible and auditable before any richer timestamp model is
needed.
