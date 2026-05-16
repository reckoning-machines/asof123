# Snapshot Schema Hardening Report

Date: 2026-05-15

`docs/unified_diff.md` does not exist and was not created.

## Changed Files

- `PRODUCT_CONTRACT.md`
- `src/asof123/models.py`
- `src/asof123/snapshot.py`
- `src/asof123/__init__.py`
- `tests/test_models.py`
- `tests/test_snapshot.py`
- `docs/snapshot_schema_version_contract.md`
- `docs/snapshot_schema_hardening_report.md`
- `docs/snapshot_replay_determinism_audit.md`
- `docs/runtime_contract_audit.md`
- `docs/provider_snapshot_report.md`
- `docs/model_skeleton_report.md`
- `docs/examples_quickstart_report.md`
- `docs/minimal_resolver_report.md`
- `examples/snapshot_demo.py`

## Runtime Hardening Changes

Added explicit snapshot contract constants:

- `SNAPSHOT_SCHEMA_VERSION = "asof123.snapshot.v1"`
- `SEMANTIC_CONTRACT_VERSION = "asof123.contract.v1"`
- `SNAPSHOT_HASH_ALGORITHM = "sha256"`

Added `AsOfSnapshot` fields:

- `snapshot_schema_version`
- `semantic_contract_version`
- `hash_algorithm`

Validation now rejects unknown values for those fields. The current runtime
accepts only the v1 schema, v1 semantic contract, and sha256 hash algorithm.

Added `canonicalize_snapshot_payload(context)`, which defines the v1
hash-affecting payload:

- `snapshot_schema_version`
- `semantic_contract_version`
- `context`

`make_snapshot()` now computes `content_hash` from
`canonicalize_snapshot_payload(context)` rather than from the bare context.
This prevents identical context bytes under future schema/semantic versions
from sharing the same semantic content identity.

Audit-only fields remain outside the v1 hash preimage:

- `snapshot_id`
- `captured_at_utc`
- `hash_algorithm`
- `content_hash`

## Tests Added Or Tightened

Model tests now assert:

- default snapshot schema version;
- default semantic contract version;
- default hash algorithm;
- rejection of unknown snapshot schema versions;
- rejection of unknown semantic contract versions;
- rejection of unknown hash algorithms.

Snapshot tests now assert:

- canonical snapshot payload includes versions and context only;
- `snapshot_id` and `captured_at_utc` do not affect `content_hash`;
- `content_hash` equals SHA256 of the canonical versioned payload.

## Behavior Intentionally Not Added

No persistence was added.
No replay engine was added.
No scheduler or background job was added.
No external provider or calendar integration was added.
No canonical authority implementation was added.
No database or storage layer was added.

Calendar, provider, and tzdata version metadata are contract requirements for
future persisted replay but are not implemented in runtime models yet because
there is no persistence or replay execution surface.

## Validation Results

Commands run:

- `python -m pytest tests/test_snapshot.py tests/test_models.py -q`
- `python -m pytest -q`
- `rg -n "content_hash|schema_version|semantic_version|canonicalize_context|json.dumps|sort_keys|datetime.now|ZoneInfo" PRODUCT_CONTRACT.md README.md docs src tests`
- `git diff --check`
- `LC_ALL=C rg -n "[^\\x00-\\x7F]" --glob '*.md'`

Results:

- Targeted snapshot/model tests passed: 49 passed.
- Full test suite passed: 164 passed.
- Targeted grep found the expected snapshot schema/semantic fields,
  canonicalization functions, JSON sorting, UTC capture, and ZoneInfo usage.
- `git diff --check` passed.
- Markdown ASCII check passed with no matches.

## HOLD / WARNING / NOTE Table

| Level | Finding | Status |
| --- | --- | --- |
| WARNING | Calendar, provider, and tzdata version metadata are not yet runtime fields. | Required before persistence/replay execution, intentionally deferred. |
| WARNING | Only v1 schema/semantic versions are accepted. | Safe current behavior; migration support must be designed before accepting v2. |
| NOTE | `captured_at_utc` remains audit-only. | It does not affect semantic content hash. |
| NOTE | `snapshot_id` remains audit record identity. | It does not affect semantic content hash. |

## Final Verdict

PASS WITH WARNINGS.

The immutable v1 snapshot schema contract is now explicit in contract,
runtime model fields, canonical hash payload, and tests. Remaining warnings
are future blockers for persistence/replay execution, not current corruption
risks.
