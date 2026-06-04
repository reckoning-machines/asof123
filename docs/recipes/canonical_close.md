# Canonical Close

## Problem

Reports and official-close consumers often repeat this check:

```python
if official_close_published and official_close_final:
    run_report()
else:
    fail_closed()
```

That code appears in report runners, benchmark loaders, NAV processes,
research pipelines, and dashboards.

## Code People Usually Write

```python
if close_status == "done" and close_file_final:
    canonical = True
else:
    canonical = False
```

The problem is not the file or report workflow. The problem is whether supplied
publication facts prove a canonical read is safe.

## asof123 Replacement

```python
from datetime import datetime, timezone

from asof123 import (
    AsOfRequest,
    SourceFreshness,
    SourceStatus,
    StaticProvider,
    XNYSCalendar,
    resolve,
)

official_close = StaticProvider(
    "official_close",
    SourceStatus(
        provider="official_close",
        freshness=SourceFreshness.FRESH,
        metadata={
            "publication": {
                "publication_state": "PUBLISHED",
                "canonical_state": "CANONICAL",
                "publication_utc": "2026-05-12T21:05:00Z",
                "asserted_at_utc": "2026-05-12T21:06:00Z",
            }
        },
    ),
)

asof = resolve(
    AsOfRequest(
        perspective="CANONICAL",
        market="XNYS",
        market_timezone="America/New_York",
        knowledge_cutoff_utc=datetime(2026, 5, 12, 21, 6, 0, tzinfo=timezone.utc),
    ),
    calendars={"XNYS": XNYSCalendar()},
    providers=[official_close],
)

assert asof.publication_state == "PUBLISHED"
assert asof.canonical_state == "CANONICAL"
```

## What The Result Means

The resolver returns a canonical AsOf only when exactly one supplied
publication assertion validates and proves:

- `publication_state=PUBLISHED`;
- `canonical_state=CANONICAL`;
- required timestamps are present and UTC-valid;
- the assertion is not after the knowledge cutoff;
- unsupported lifecycle metadata is absent.

Otherwise resolution fails closed with an explicit publication readiness
reason.

## What asof123 Does Not Do

asof123 does not publish the official close, poll for files, choose between
competing publication authorities, persist a registry, manage report workflow,
or implement withdrawal/supersession handling. External systems report
publication facts; asof123 resolves readiness from those facts.
