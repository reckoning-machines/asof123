# Snapshot Schema Version Contract

Date: 2026-05-15

This document is contract-derived from `PRODUCT_CONTRACT.md`. If it ever
disagrees with `PRODUCT_CONTRACT.md`, the product contract wins and this
document must be corrected.

`docs/unified_diff.md` does not exist and was not created.

## Snapshot Identity Definition

AsOfSnapshot has two identities:

- Record identity: `snapshot_id`. This identifies one materialized audit
  record. It may differ across two captures of identical semantic content.
- Semantic content identity: `hash_algorithm` plus `content_hash`. This
  identifies the versioned semantic payload used for replay comparison,
  audit comparison, and reproducibility checks.

`snapshot_id` is not a semantic identity. Two snapshots with different
`snapshot_id` values may have the same `content_hash` when they contain the
same versioned semantic payload.

## Hash-Affecting Vs Audit-Only Fields

Hash-affecting fields:

- `snapshot_schema_version`
- `semantic_contract_version`
- `context`

Audit-only fields:

- `snapshot_id`
- `captured_at_utc`
- `hash_algorithm`
- `content_hash`

`captured_at_utc` is audit-only. It records when a snapshot record was
materialized and must not change the semantic content hash.

`hash_algorithm` is audit-only because it names how `content_hash` was
computed. Changing the algorithm creates a different kind of content
identity, but the algorithm name is not part of the v1 hash preimage.

## Snapshot Schema Version Rules

Current value:

    asof123.snapshot.v1

`snapshot_schema_version` is hash-affecting. The same `context` serialized
under a different snapshot schema must not share the same semantic
`content_hash`.

Compatibility rules:

- Additive hash-affecting fields require a new snapshot schema version.
- Removed hash-affecting fields require a new snapshot schema version.
- Renamed hash-affecting fields require a new snapshot schema version.
- Reordering JSON object keys must not require a new schema version because
  canonical JSON sorts keys.
- Adding audit-only fields may be compatible only if older readers can ignore
  them without changing the hash preimage.
- Changing canonical serialization rules requires a new snapshot schema
  version.

The current runtime accepts only `asof123.snapshot.v1`.

## Semantic Contract Version Rules

Current value:

    asof123.contract.v1

`semantic_contract_version` is hash-affecting. The same JSON shape under a
different semantic contract must not share the same semantic `content_hash`.

Distinctions:

- Serialization schema changes alter the snapshot wire shape or hash
  preimage and require `snapshot_schema_version` changes.
- Semantic meaning changes alter the interpretation of existing values and
  require `semantic_contract_version` changes.
- Runtime behavior changes that do not alter persisted interpretation may
  not require either version, but must be audited against replay safety.

Replay-safe evolution rules:

- Enum additions require a product contract change and must be assessed for
  replay impact.
- Enum renames, merges, or value reuse are not replay-safe.
- Perspective semantics changes require a semantic contract version change.
- Market phase semantics changes require a semantic contract version change
  unless fully isolated by calendar version metadata.
- CANONICAL semantics must remain fail-closed until an explicit canonical
  authority boundary exists.

The current runtime accepts only `asof123.contract.v1`.

## Calendar Freeze Requirements

Before persisted replay is allowed, snapshots or their replay envelope must
record enough calendar information to reproduce market-relative meaning.

Required future fields or equivalent metadata:

- `calendar_id`
- `calendar_version`
- `market`
- `market_timezone`
- `tzdata_version` or equivalent timezone rule identity when timezone rules
  affect historical interpretation
- market definition or exchange rule publication version when applicable

Future replay must not recompute historical market phase, business date, or
session boundaries from a newer calendar unless the caller explicitly requests
reinterpretation.

## Provider Freeze Requirements

Before provider-backed persisted replay is allowed, snapshots or their replay
envelope must record enough provider information to reproduce source facts.

Required future fields or equivalent metadata:

- `provider_id`
- `provider_version`
- source artifact hash or immutable source version
- assertion or observation instant for freshness claims
- publication assertion metadata when publication state matters

Future replay must not call live providers to decide what a past provider
reported unless the replay mode explicitly declares reinterpretation from
current provider state.

## Deterministic Serialization Contract

The v1 canonical snapshot payload is:

    {
      "context": <TemporalContext JSON-mode dump>,
      "semantic_contract_version": "asof123.contract.v1",
      "snapshot_schema_version": "asof123.snapshot.v1"
    }

Serialization rules:

- Use Pydantic JSON-mode model data.
- Use `json.dumps(..., sort_keys=True, separators=(",", ":"),
  ensure_ascii=False)`.
- Enum values serialize as their pinned string values.
- Datetime fields must already be timezone-aware UTC and are serialized by
  Pydantic JSON mode.
- Object keys are sorted recursively by JSON serialization.
- Null values are included when present in the model dump.
- Metadata must contain only deterministic JSON-compatible primitives,
  lists, and dictionaries.
- Lists and tuples are both serialized as JSON arrays.
- NaN, Infinity, sets, bytes, arbitrary objects, and non-string metadata keys
  are forbidden.

The v1 content hash is:

    sha256(canonical_snapshot_payload_utf8).hexdigest()

## Replay Reinterpretation Policy

Replay has two allowed modes:

- Reproduction mode: use the recorded snapshot schema, semantic contract,
  calendar, timezone, and provider regimes to reproduce the original meaning.
- Explicit reinterpretation mode: declare the newer schema, semantic,
  calendar, timezone, or provider regime being applied and produce a distinct
  result that cannot be mistaken for the original replay.

Silent reinterpretation is forbidden.

## Forbidden Future Behaviors

Future implementations must not:

- Persist snapshots without schema and semantic contract versions.
- Treat `snapshot_id` as semantic content identity.
- Include `captured_at_utc` in v1 semantic content hashes.
- Recompute historical calendars from mutable current calendar state without
  explicit reinterpretation mode.
- Recompute historical provider facts from mutable current provider state
  without explicit reinterpretation mode.
- Change hash-affecting payload shape without changing
  `snapshot_schema_version`.
- Change ontology meaning without changing `semantic_contract_version`.
- Use Python process hash values, random values, UUIDs, localtime, or naive
  datetimes in semantic content hashing.

## Migration / Evolution Rules

Snapshot migration must be explicit:

- A migration from one snapshot schema version to another must define its
  source version, target version, and hash preimage rules.
- Migrations must not overwrite the original snapshot payload.
- Migrations must preserve original `content_hash` for audit.
- Rehashed migrated payloads must carry the target schema and semantic
  versions.
- If a semantic version changes, replay output must identify whether it is
  reproduction under the old semantics or reinterpretation under the new
  semantics.

## HOLD / WARNING / NOTE Table

| Level | Finding | Status |
| --- | --- | --- |
| WARNING | Calendar/provider/tzdata version fields are required before persisted replay, but are not implemented yet. | Future blocker for persistence/replay execution, not current runtime. |
| WARNING | Only v1 snapshot and semantic versions are currently accepted. | Intentional hardening until migration policy exists in code. |
| NOTE | `captured_at_utc` is audit-only and excluded from v1 content hashes. | Intentional; identical semantic content can be captured more than once. |
| NOTE | `snapshot_id` is audit record identity, not semantic identity. | Compare semantic payloads with `hash_algorithm` plus `content_hash`. |

## Final Verdict

PASS WITH WARNINGS.

The v1 immutable snapshot schema and semantic version contract is now
defined. The warnings are future blockers for persistent replay and richer
calendar/provider integration, not current replay corruption risks.
