# Calendar Provider Timezone Hardening Report

Date: 2026-05-15

`docs/unified_diff.md` does not exist and was not created.

## Changed Files

- `PRODUCT_CONTRACT.md`
- `docs/calendar_provider_timezone_freeze_contract.md`
- `docs/calendar_provider_timezone_hardening_report.md`

## Runtime Hardening Changes

No runtime code or tests were changed in this pass.

The current v1 in-memory snapshot model remains unchanged:

- `snapshot_schema_version`
- `semantic_contract_version`
- `context`

remain the hash-affecting snapshot payload.

Calendar, provider, and timezone freeze metadata were not added to runtime
models because there is still no persistence layer or replay execution
surface. Adding optional non-hash-affecting runtime fields now would weaken
the boundary by making future replay metadata look present before it is
enforced.

## Contract Drift Repaired

The prior snapshot schema contract identified calendar, provider, and tzdata
metadata as future blockers. This pass expands those warnings into concrete
contract requirements:

- calendar identity and version fields;
- timezone rule identity and tzdata drift controls;
- provider identity, version, schema, semantic contract, source artifact, and
  assertion instant requirements;
- a future snapshot freeze envelope definition;
- reproduction versus reinterpretation replay policy;
- persistence guardrails that must exist before persisted replay execution.

## Behavior Intentionally Left Unchanged

No persistence was added.
No replay engine was added.
No database or storage layer was added.
No scheduler or background job was added.
No external provider integration was added.
No canonical authority implementation was added.
No mutable runtime registry was added.
No fin123 integration was added.

Current API, CLI, resolver, provider, calendar, and snapshot behavior remains
unchanged.

## Hash Boundary Decision

Current in-memory v1 snapshots continue to hash only:

- `snapshot_schema_version`;
- `semantic_contract_version`;
- `context`.

For future persisted replay, calendar, provider, and timezone freeze metadata
must be hash-affecting in the persisted replay payload or in a linked
immutable freeze envelope whose own identity is hash-addressed.

## Validation Results

Commands run:

- `python -m pytest -q`
- `rg -n "calendar_version|tzdata|ZoneInfo|provider_version|semantic_contract_version|snapshot_schema_version|content_hash" PRODUCT_CONTRACT.md README.md docs src tests`
- `git diff --check`
- `LC_ALL=C rg -n "[^\\x00-\\x7F]" --glob '*.md'`

Results:

- Full test suite passed: 164 passed.
- Targeted grep found expected contract, doc, code, and test references for
  freeze metadata, timezone validation, snapshot schema version, semantic
  contract version, and content hash.
- `git diff --check` passed.
- Markdown ASCII check passed with no matches.

## HOLD / WARNING / NOTE Table

| Level | Finding | Status |
| --- | --- | --- |
| WARNING | Freeze envelope metadata is not implemented in runtime models. | Required before persistence/replay execution, intentionally deferred. |
| WARNING | Calendar rules, provider facts, and tzdata identity are not version-pinned in current snapshots. | Safe for current in-memory snapshots; not sufficient for persisted replay. |
| NOTE | No runtime behavior changed. | This was a contract/design hardening pass only. |

## Final Verdict

PASS WITH WARNINGS.

The future freeze contract is explicit enough to block unsafe persistence or
replay execution until calendar, provider, and timezone interpretation
metadata are implemented and tested as hash-affecting replay state.
